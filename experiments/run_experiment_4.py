import argparse
import json
import logging
import os
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.state.models import DocumentChunk, SourceDocument
from app.db.state.db import get_session
from app.rag.retriever import retrieve
from evaluation.metrics.retrieval_metrics import precision_at_k, recall_at_k, mrr, ndcg_at_k

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def get_gold_ids_for_strategy(gold_sources: list[dict], strategy: str) -> set[str]:
    """
    Dynamically maps a configuration-independent gold source (doc_id + snippet)
    to the specific chunk_ids in the given strategy's collection.
    """
    gold_ids = set()
    with get_session() as db:
        for gs in gold_sources:
            doc_id = gs["doc_id"]
            snippet = gs.get("snippet", "").lower()
            
            # Read full source doc to find snippet position
            doc_row = db.query(SourceDocument).filter(SourceDocument.doc_id == doc_id).first()
            if not doc_row:
                logger.warning(f"Doc {doc_id} not found in DB")
                continue
                
            try:
                full_text = Path(doc_row.file_path).read_text(encoding="utf-8").lower()
                snippet_start = full_text.find(snippet)
                if snippet_start == -1:
                    logger.warning(f"Snippet not found in doc {doc_id}: {snippet[:30]}...")
                    continue
                snippet_end = snippet_start + len(snippet)
            except Exception as e:
                logger.error(f"Failed to read {doc_row.file_path}: {e}")
                continue
                
            # Find all chunks for this strategy that overlap with the snippet
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.doc_id == doc_id,
                DocumentChunk.chunking_strategy == strategy
            ).all()
            
            for c in chunks:
                # Overlap condition: max(start) < min(end)
                overlap_start = max(snippet_start, c.char_start)
                overlap_end = min(snippet_end, c.char_end)
                if overlap_start < overlap_end:
                    gold_ids.add(c.chunk_id)
                    
    return gold_ids

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Path to evaluation dataset JSON")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    
    import hashlib
    sha256 = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    logger.info(f"Loaded {len(queries)} queries from {dataset_path.name}")
    
    results = []
    
    for q in queries:
        qid = q["query_id"]
        query_text = q["query"]
        gold_sources = q.get("gold_sources", [])
        
        for strategy in ["fixed_size", "semantic"]:
            # 1. Map gold labels
            gold_ids = get_gold_ids_for_strategy(gold_sources, strategy)
            if not gold_ids:
                logger.warning(f"Query {qid}: No gold chunks found for {strategy}")
                
            # 2. Retrieve
            start_t = time.perf_counter()
            retrieved = retrieve(query_text, f"vitian_kb_{strategy}", top_k=10)
            latency = (time.perf_counter() - start_t) * 1000
            
            retrieved_ids = [c.chunk_id for c in retrieved]
            
            # 3. Calculate metrics
            p5 = precision_at_k(retrieved_ids, gold_ids, k=5)
            r5 = recall_at_k(retrieved_ids, gold_ids, k=5)
            m_r_r = mrr(retrieved_ids, gold_ids)
            ndcg10 = ndcg_at_k(retrieved_ids, gold_ids, k=10)
            
            results.append({
                "query_id": qid,
                "configuration": strategy,
                "metric": "Precision@5",
                "metric_value": p5,
                "dataset_version": dataset_path.name,
                "dataset_sha256": sha256
            })
            results.append({
                "query_id": qid,
                "configuration": strategy,
                "metric": "Recall@5",
                "metric_value": r5,
                "dataset_version": dataset_path.name,
                "dataset_sha256": sha256
            })
            results.append({
                "query_id": qid,
                "configuration": strategy,
                "metric": "MRR",
                "metric_value": m_r_r,
                "dataset_version": dataset_path.name,
                "dataset_sha256": sha256
            })
            results.append({
                "query_id": qid,
                "configuration": strategy,
                "metric": "nDCG@10",
                "metric_value": ndcg10,
                "dataset_version": dataset_path.name,
                "dataset_sha256": sha256
            })
            
    # Only save to experiment_4_raw.csv if not a dev run
    if "dev" not in dataset_path.name.lower():
        df = pd.DataFrame(results)
        os.makedirs("results", exist_ok=True)
        df.to_csv("results/experiment_4_raw.csv", index=False)
        logger.info("Saved results to results/experiment_4_raw.csv")
    else:
        logger.info("Dev run complete. Metrics calculated successfully.")
        df = pd.DataFrame(results)
        print(df.groupby(["metric", "configuration"])["metric_value"].mean())

if __name__ == "__main__":
    main()

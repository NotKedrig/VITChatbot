"""
experiments/run_experiment_1.py — Experiment 1 (RAG vs Vanilla LLM).

Runs the RAG-grounded system and Vanilla baseline against a given dataset,
scores them using deterministic fact-matching metrics, computes McNemar's
test and bootstrap CIs, and writes raw CSVs + stats + charts.

Usage:
  python -m experiments.run_experiment_1 --dataset evaluation/datasets/dev/rag_questions_dev.json
"""

import argparse
import csv
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from app.agents.company_research import answer_vanilla, answer_with_rag
from evaluation.metrics.fact_matching import score, is_correct
from evaluation.metrics.stats_utils import mcnemar_test, bootstrap_diff_ci

# Force imports to register config
import app.config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    """Return SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Run Experiment 1 (RAG vs Vanilla).")
    parser.add_argument(
        "--dataset",
        type=str,
        default="evaluation/datasets/dev/rag_questions_dev.json",
        help="Path to the dataset JSON file.",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="vitian_kb_fixed_size",
        help="ChromaDB collection to query for the RAG system.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="LLM sampling temperature (should be 0.0 for reproducible evaluation).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable LLM response caching (forces fresh API calls).",
    )
    args = parser.parse_args()

    ds_path = Path(args.dataset)
    if not ds_path.exists():
        logger.error(f"Dataset not found: {ds_path}")
        sys.exit(1)

    ds_sha = _sha256(ds_path)
    ds_version = ds_path.stem

    logger.info(f"Loading dataset: {ds_path} (SHA256: {ds_sha})")
    with open(ds_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    logger.info(f"Loaded {len(dataset)} questions. Collection: {args.collection}")

    raw_results = []
    
    # -----------------------------------------------------------------------
    # Run predictions and score
    # -----------------------------------------------------------------------
    for i, item in enumerate(dataset, start=1):
        q_id = item["question_id"]
        q_text = item["question"]
        expected_facts = item["expected_facts"]
        gold_doc_ids = item["gold_source_doc_ids"]

        logger.info(f"Processing {i}/{len(dataset)}: {q_id}")

        from app.llm.provider import QuotaExhaustedError
        
        try:
            # --- Vanilla ---
            vanilla_ans = answer_vanilla(
                question=q_text,
                temperature=args.temperature,
                use_cache=not args.no_cache,
            )
            vanilla_score = score(
                answer=vanilla_ans.answer,
                expected_facts=expected_facts,
                gold_source_doc_ids=gold_doc_ids,
                cited_doc_ids=None, # Vanilla has no citations
                source_context="",
            )
            
            # --- RAG ---
            rag_ans = answer_with_rag(
                question=q_text,
                collection_name=args.collection,
                temperature=args.temperature,
                use_cache=not args.no_cache,
            )
            # Reconstruct full retrieved context block for hallucination heuristic
            retrieved_context = "\n".join(c.text for c in rag_ans.retrieved_chunks)
            rag_score = score(
                answer=rag_ans.answer,
                expected_facts=expected_facts,
                gold_source_doc_ids=gold_doc_ids,
                cited_doc_ids=rag_ans.cited_doc_ids,
                source_context=retrieved_context,
            )
        except QuotaExhaustedError as e:
            logger.error(f"Stopping run early: {e}")
            break

        timestamp = datetime.now(timezone.utc).isoformat()

        # Build raw rows
        for system_name, ans_obj, score_obj in [
            ("Vanilla", vanilla_ans, vanilla_score),
            ("RAG", rag_ans, rag_score),
        ]:
            row = {
                "question_id": q_id,
                "system": system_name,
                "answer": ans_obj.answer,
                "factual_accuracy": score_obj.factual_accuracy,
                "hallucinated": score_obj.hallucinated,
                "citation_precision": score_obj.citation_precision if score_obj.citation_precision is not None else "",
                "needs_human_review": score_obj.needs_human_review,
                "model_name": ans_obj.llm_response.model_name,
                "model_version": ans_obj.llm_response.model_version,
                "temperature": ans_obj.llm_response.temperature,
                "timestamp": timestamp,
                "dataset_version": ds_version,
                "dataset_sha256": ds_sha,
            }
            raw_results.append(row)

    # -----------------------------------------------------------------------
    # Write Raw CSV
    # -----------------------------------------------------------------------
    raw_csv_path = Path("results/experiment_1_raw.csv")
    raw_csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    fieldnames = [
        "question_id", "system", "answer", "factual_accuracy", "hallucinated",
        "citation_precision", "needs_human_review", "model_name", "model_version",
        "temperature", "timestamp", "dataset_version", "dataset_sha256"
    ]
    with open(raw_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(raw_results)
    logger.info(f"Raw results written to {raw_csv_path}")

    # -----------------------------------------------------------------------
    # Statistical Analysis
    # -----------------------------------------------------------------------
    df = pd.DataFrame(raw_results)
    
    vanilla_df = df[df["system"] == "Vanilla"].set_index("question_id")
    rag_df = df[df["system"] == "RAG"].set_index("question_id")
    
    # Ensure they align
    assert (vanilla_df.index == rag_df.index).all(), "Mismatched indices"

    n_samples = len(vanilla_df)
    
    # 1. McNemar's Test for Factual Accuracy (Correct/Incorrect)
    vanilla_correct = (vanilla_df["factual_accuracy"] >= 0.5).tolist()
    rag_correct = (rag_df["factual_accuracy"] >= 0.5).tolist()
    acc_mcnemar = mcnemar_test(vanilla_correct, rag_correct)
    
    # Bootstrap CI for Accuracy Difference (RAG - Vanilla)
    acc_ci_lower, acc_ci_upper = bootstrap_diff_ci(
        vanilla_df["factual_accuracy"].tolist(),
        rag_df["factual_accuracy"].tolist(),
        paired=True
    )
    
    # 2. McNemar's Test for Hallucinations
    vanilla_hallucinated = vanilla_df["hallucinated"].tolist()
    rag_hallucinated = rag_df["hallucinated"].tolist()
    halluc_mcnemar = mcnemar_test(vanilla_hallucinated, rag_hallucinated)
    
    # Bootstrap CI for Hallucination Difference (RAG - Vanilla)
    halluc_ci_lower, halluc_ci_upper = bootstrap_diff_ci(
        [float(x) for x in vanilla_hallucinated],
        [float(x) for x in rag_hallucinated],
        paired=True
    )

    pct_needs_review = (df["needs_human_review"].sum() / len(df)) * 100

    stats_results = [
        {
            "metric": "factual_accuracy_>=0.5",
            "sample_size": n_samples,
            "test_statistic": acc_mcnemar["test_statistic"],
            "p_value": acc_mcnemar["p_value"],
            "effect_size_odds_ratio": acc_mcnemar["effect_size"],
            "ci_lower_diff": acc_ci_lower,
            "ci_upper_diff": acc_ci_upper,
            "significant_at_0.05": acc_mcnemar["significant"],
            "pct_needs_human_review": pct_needs_review,
            "dataset_version": ds_version,
            "dataset_sha256": ds_sha,
        },
        {
            "metric": "hallucinated",
            "sample_size": n_samples,
            "test_statistic": halluc_mcnemar["test_statistic"],
            "p_value": halluc_mcnemar["p_value"],
            "effect_size_odds_ratio": halluc_mcnemar["effect_size"],
            "ci_lower_diff": halluc_ci_lower,
            "ci_upper_diff": halluc_ci_upper,
            "significant_at_0.05": halluc_mcnemar["significant"],
            "pct_needs_human_review": pct_needs_review,
            "dataset_version": ds_version,
            "dataset_sha256": ds_sha,
        }
    ]

    stats_csv_path = Path("analysis/experiment_1_statistics.csv")
    stats_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(stats_results[0].keys()))
        writer.writeheader()
        writer.writerows(stats_results)
    
    logger.info(f"Statistics written to {stats_csv_path}")
    logger.info(f"Percentage of items flagged needs_human_review: {pct_needs_review:.1f}%")
    logger.info("NOTE: Automated hallucination detection here is a heuristic, not a perfect or human-equivalent judge.")

    # -----------------------------------------------------------------------
    # Charts
    # -----------------------------------------------------------------------
    charts_dir = Path("analysis/charts")
    charts_dir.mkdir(parents=True, exist_ok=True)
    
    avg_acc = df.groupby("system")["factual_accuracy"].mean()
    avg_hal = df.groupby("system")["hallucinated"].mean()
    avg_cit = rag_df["citation_precision"].mean() if not rag_df["citation_precision"].isna().all() else 0.0

    fig, ax = plt.subplots(1, 3, figsize=(15, 5))
    
    # Plot 1: Factual Accuracy
    ax[0].bar(avg_acc.index, avg_acc.values, color=["blue", "green"])
    ax[0].set_title("Mean Factual Accuracy")
    ax[0].set_ylim(0, 1)
    
    # Plot 2: Hallucination Rate
    ax[1].bar(avg_hal.index, avg_hal.values, color=["blue", "green"])
    ax[1].set_title("Hallucination Rate (Heuristic)")
    ax[1].set_ylim(0, 1)
    
    # Plot 3: Citation Precision (RAG only)
    ax[2].bar(["RAG"], [avg_cit], color=["green"])
    ax[2].set_title("Mean Citation Precision")
    ax[2].set_ylim(0, 1)

    chart_path = charts_dir / "experiment_1_chart.png"
    plt.tight_layout()
    plt.savefig(chart_path)
    logger.info(f"Chart saved to {chart_path}")

    # Output simple text summary
    print("\n" + "="*40)
    print("EXPERIMENT 1 SUMMARY")
    print("="*40)
    print(f"Dataset: {ds_version}")
    print(f"Sample size: {n_samples}")
    print("-" * 40)
    print(f"Vanilla Mean Factual Accuracy : {avg_acc.get('Vanilla', 0):.2f}")
    print(f"RAG Mean Factual Accuracy     : {avg_acc.get('RAG', 0):.2f}")
    print(f"Accuracy Diff 95% CI          : [{acc_ci_lower:.2f}, {acc_ci_upper:.2f}]")
    print(f"McNemar's p-value (Accuracy)  : {acc_mcnemar['p_value']:.4f} (Significant: {acc_mcnemar['significant']})")
    print("-" * 40)
    print(f"Vanilla Hallucination Rate    : {avg_hal.get('Vanilla', 0):.2f}")
    print(f"RAG Hallucination Rate        : {avg_hal.get('RAG', 0):.2f}")
    print(f"Hallucination Diff 95% CI     : [{halluc_ci_lower:.2f}, {halluc_ci_upper:.2f}]")
    print(f"McNemar's p-value (Halluc.)   : {halluc_mcnemar['p_value']:.4f} (Significant: {halluc_mcnemar['significant']})")
    print("-" * 40)
    print(f"RAG Citation Precision        : {avg_cit:.2f}")
    print("="*40)

if __name__ == "__main__":
    main()

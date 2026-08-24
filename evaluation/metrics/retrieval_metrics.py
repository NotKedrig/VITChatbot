import math

def precision_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int = 5) -> float:
    """Proportion of top-k retrieved chunks that are relevant."""
    if not retrieved_ids or not gold_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_retrieved = sum(1 for doc_id in top_k if doc_id in gold_ids)
    return relevant_retrieved / len(top_k)

def recall_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int = 5) -> float:
    """Proportion of gold-relevant chunks that were successfully retrieved in top-k."""
    if not retrieved_ids or not gold_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_retrieved = sum(1 for doc_id in top_k if doc_id in gold_ids)
    return relevant_retrieved / len(gold_ids)

def mrr(retrieved_ids: list[str], gold_ids: set[str]) -> float:
    """Mean Reciprocal Rank: 1 / rank of first relevant chunk."""
    if not retrieved_ids or not gold_ids:
        return 0.0
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in gold_ids:
            return 1.0 / (i + 1)
    return 0.0

def ndcg_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain at k."""
    if not retrieved_ids or not gold_ids:
        return 0.0
    
    top_k = retrieved_ids[:k]
    dcg = 0.0
    for i, doc_id in enumerate(top_k):
        if doc_id in gold_ids:
            # relevance is binary (1 or 0)
            dcg += 1.0 / math.log2(i + 2)  # i is 0-indexed, so rank is i+1, log2(rank+1) = log2(i+2)
            
    # Calculate IDCG (Ideal DCG)
    idcg = 0.0
    ideal_hits = min(len(gold_ids), k)
    for i in range(ideal_hits):
        idcg += 1.0 / math.log2(i + 2)
        
    if idcg == 0.0:
        return 0.0
        
    return dcg / idcg

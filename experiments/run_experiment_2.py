import argparse
import json
import logging
import time
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
from scipy.stats import wilcoxon

from app.config import settings
from app.agents.supervisor import supervisor_node
from app.agents.rule_router import rule_route
from evaluation.metrics.stats_utils import mcnemar_test, benjamini_hochberg
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, required=True, help="Path to evaluation dataset")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        logger.error(f"Dataset not found: {dataset_path}")
        return

    dataset_bytes = dataset_path.read_bytes()
    dataset_sha256 = hashlib.sha256(dataset_bytes).hexdigest()
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    is_dev = "dev" in dataset_path.name
    dataset_version = "dev" if is_dev else dataset_path.stem

    logger.info(f"Loading dataset: {dataset_path} (SHA256: {dataset_sha256})")
    logger.info(f"Loaded {len(queries)} queries.")

    results = []
    
    for i, q in enumerate(queries):
        query_id = q["query_id"]
        utterance = q["utterance"]
        expected_agent = q["expected_agent"]
        
        logger.info(f"Processing {i+1}/{len(queries)}: {query_id}")
        
        # --- LLM Supervisor ---
        state = {"messages": [{"role": "user", "content": utterance}]}
        # We assume supervisor_node handles its own perf_counter but we can also wrap it
        node_result = supervisor_node(state)
        supervisor_prediction = node_result["next_agent"]
        
        # Find latency in metadata if available
        supervisor_latency_ms = 0
        metadata = node_result.get("runtime_metadata", [])
        if metadata and "latency" in metadata[0]:
            supervisor_latency_ms = metadata[0]["latency"] * 1000
        
        # --- Rule Router ---
        rule_start = time.perf_counter()
        rule_prediction = rule_route(utterance)
        rule_latency_ms = (time.perf_counter() - rule_start) * 1000
        
        results.append({
            "query_id": query_id,
            "utterance": utterance,
            "expected_agent": expected_agent,
            "supervisor_prediction": supervisor_prediction,
            "rule_prediction": rule_prediction,
            "supervisor_latency_ms": supervisor_latency_ms,
            "rule_latency_ms": rule_latency_ms,
            "supervisor_correct": supervisor_prediction == expected_agent,
            "rule_correct": rule_prediction == expected_agent,
            "model": settings.llm_model_name,
            "dataset_version": dataset_version,
            "dataset_sha256": dataset_sha256,
        })
        
        time.sleep(2) # rate limit mitigation for flash-lite
        
    df = pd.DataFrame(results)
    
    Path("results").mkdir(exist_ok=True)
    out_csv = Path("results/experiment_2_raw.csv")
    df.to_csv(out_csv, index=False)
    logger.info(f"Raw results written to {out_csv}")
    
    # Statistics
    Path("analysis").mkdir(exist_ok=True)
    Path("analysis/charts").mkdir(exist_ok=True)
    
    # Overall Accuracy
    supervisor_acc = df["supervisor_correct"].mean()
    rule_acc = df["rule_correct"].mean()
    
    mcnemar_res = mcnemar_test(df["rule_correct"].tolist(), df["supervisor_correct"].tolist())
    
    # Latency paired test (Wilcoxon)
    # Only test if differences are not all 0
    latency_diff = df["supervisor_latency_ms"] - df["rule_latency_ms"]
    if np.all(latency_diff == 0):
        wilcoxon_stat, wilcoxon_p = 0.0, 1.0
    else:
        # wilcoxon handles exactly zero differences by discarding them, but if all are zero it raises ValueError
        res = wilcoxon(df["supervisor_latency_ms"], df["rule_latency_ms"])
        wilcoxon_stat, wilcoxon_p = res.statistic, res.pvalue
        
    # Per-agent Precision & Recall
    agents = ["company_research", "planner", "progress", "notification"]
    agent_stats = []
    
    for agent in agents:
        # Supervisor
        sup_tp = ((df["supervisor_prediction"] == agent) & (df["expected_agent"] == agent)).sum()
        sup_fp = ((df["supervisor_prediction"] == agent) & (df["expected_agent"] != agent)).sum()
        sup_fn = ((df["supervisor_prediction"] != agent) & (df["expected_agent"] == agent)).sum()
        
        sup_prec = sup_tp / (sup_tp + sup_fp) if (sup_tp + sup_fp) > 0 else 0
        sup_rec = sup_tp / (sup_tp + sup_fn) if (sup_tp + sup_fn) > 0 else 0
        
        # Rule
        rule_tp = ((df["rule_prediction"] == agent) & (df["expected_agent"] == agent)).sum()
        rule_fp = ((df["rule_prediction"] == agent) & (df["expected_agent"] != agent)).sum()
        rule_fn = ((df["rule_prediction"] != agent) & (df["expected_agent"] == agent)).sum()
        
        rule_prec = rule_tp / (rule_tp + rule_fp) if (rule_tp + rule_fp) > 0 else 0
        rule_rec = rule_tp / (rule_tp + rule_fn) if (rule_tp + rule_fn) > 0 else 0
        
        agent_stats.append({
            "agent": agent,
            "sup_prec": sup_prec,
            "sup_rec": sup_rec,
            "rule_prec": rule_prec,
            "rule_rec": rule_rec,
        })
        
    stats_df = pd.DataFrame([{
        "metric": "overall_accuracy",
        "sample_size": len(df),
        "supervisor": supervisor_acc,
        "rule": rule_acc,
        "test_statistic": mcnemar_res["test_statistic"],
        "p_value": mcnemar_res["p_value"],
        "effect_size": mcnemar_res["effect_size"],
        "significant": mcnemar_res["significant"]
    }, {
        "metric": "paired_latency_ms",
        "sample_size": len(df),
        "supervisor": df["supervisor_latency_ms"].mean(),
        "rule": df["rule_latency_ms"].mean(),
        "test_statistic": wilcoxon_stat,
        "p_value": wilcoxon_p,
        "effect_size": None,
        "significant": wilcoxon_p < 0.05
    }])
    
    out_stats = Path("analysis/experiment_2_statistics.csv")
    stats_df.to_csv(out_stats, index=False)
    
    # Save per-agent stats
    pd.DataFrame(agent_stats).to_csv("analysis/experiment_2_agent_stats.csv", index=False)
    
    # Plotting
    labels = ['Supervisor', 'Rule-Based']
    accs = [supervisor_acc, rule_acc]
    
    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.bar(labels, accs, color=['#2a9d8f', '#e76f51'])
    ax.set_ylabel('Routing Accuracy')
    ax.set_title('Experiment 2: Routing Accuracy Comparison')
    ax.set_ylim(0, 1.1)
    
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.2f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  
                    textcoords="offset points",
                    ha='center', va='bottom')
                    
    chart_path = Path("analysis/charts/experiment_2_chart.png")
    plt.savefig(chart_path)
    plt.close()
    
    logger.info("========================================")
    logger.info("EXPERIMENT 2 SUMMARY")
    logger.info("========================================")
    logger.info(f"Dataset: {dataset_version}")
    logger.info(f"Sample size: {len(df)}")
    logger.info("-" * 40)
    logger.info(f"Supervisor Accuracy : {supervisor_acc:.2f}")
    logger.info(f"Rule-Based Accuracy : {rule_acc:.2f}")
    logger.info(f"McNemar's p-value   : {mcnemar_res['p_value']:.4f} (Significant: {mcnemar_res['significant']})")
    logger.info(f"Supervisor Latency  : {df['supervisor_latency_ms'].mean():.2f} ms")
    logger.info(f"Rule-Based Latency  : {df['rule_latency_ms'].mean():.2f} ms")
    logger.info(f"Wilcoxon p-value    : {wilcoxon_p:.4f} (Significant: {wilcoxon_p < 0.05})")
    logger.info("========================================")

if __name__ == "__main__":
    main()

import pandas as pd
import numpy as np
from scipy import stats
import os
import matplotlib.pyplot as plt

def compute_bootstrap_ci(data, num_bootstraps=10000, alpha=0.05):
    data = np.array(data)
    bootstrapped_means = np.random.choice(data, (num_bootstraps, len(data)), replace=True).mean(axis=1)
    lower_bound = np.percentile(bootstrapped_means, 100 * (alpha / 2))
    upper_bound = np.percentile(bootstrapped_means, 100 * (1 - alpha / 2))
    return lower_bound, upper_bound

def main():
    df = pd.read_csv("results/experiment_4_raw.csv")
    metrics = ["nDCG@10", "Precision@5", "Recall@5", "MRR"]
    
    results = []
    
    os.makedirs("analysis/charts", exist_ok=True)
    plt.figure(figsize=(20, 5))
    
    for i, metric in enumerate(metrics):
        metric_df = df[df["metric"] == metric]
        
        # Pivot to get paired differences
        pivoted = metric_df.pivot(index="query_id", columns="configuration", values="metric_value").dropna()
        
        if len(pivoted) == 0:
            continue
            
        fixed_vals = pivoted["fixed_size"].values
        sem_vals = pivoted["semantic"].values
        diffs = sem_vals - fixed_vals  # Positive means semantic is better
        
        n = len(diffs)
        
        # Normality check
        if np.std(diffs) == 0:
            shapiro_stat, shapiro_p = np.nan, np.nan
            wilcoxon_stat, wilcoxon_p = np.nan, 1.0
        else:
            shapiro_stat, shapiro_p = stats.shapiro(diffs)
            wilcoxon_stat, wilcoxon_p = stats.wilcoxon(diffs)
            
        mean_diff = np.mean(diffs)
        ci_lower, ci_upper = compute_bootstrap_ci(diffs)
        
        designation = "PRIMARY" if metric == "nDCG@10" else "SECONDARY"
        
        results.append({
            "metric": metric,
            "designation": designation,
            "N": n,
            "fixed_size_mean": np.mean(fixed_vals),
            "semantic_mean": np.mean(sem_vals),
            "mean_paired_diff": mean_diff,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "shapiro_p": shapiro_p,
            "wilcoxon_stat": wilcoxon_stat,
            "wilcoxon_p": wilcoxon_p,
            "significant": wilcoxon_p < 0.05 if not np.isnan(wilcoxon_p) else False,
            "dataset_version": metric_df["dataset_version"].iloc[0],
            "dataset_sha256": metric_df["dataset_sha256"].iloc[0]
        })
        
        plt.subplot(1, 4, i+1)
        plt.boxplot([fixed_vals, sem_vals], tick_labels=["Fixed-Size", "Semantic"])
        plt.title(f"{metric} ({designation})")
        plt.ylabel("Score")
        
    plt.tight_layout()
    plt.savefig("analysis/charts/experiment_4_charts.png")
    
    stats_df = pd.DataFrame(results)
    stats_df.to_csv("analysis/experiment_4_statistics.csv", index=False)
    print("Analysis complete. Saved to analysis/experiment_4_statistics.csv and analysis/charts/experiment_4_charts.png")

if __name__ == "__main__":
    main()

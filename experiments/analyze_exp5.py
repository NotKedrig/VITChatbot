import pandas as pd
import numpy as np
from scipy import stats
import os
import matplotlib.pyplot as plt

def compute_bootstrap_ci(data, num_bootstraps=10000, alpha=0.05):
    data = np.array(data)
    if len(data) == 0:
        return np.nan, np.nan
    bootstrapped_means = np.random.choice(data, (num_bootstraps, len(data)), replace=True).mean(axis=1)
    lower_bound = np.percentile(bootstrapped_means, 100 * (alpha / 2))
    upper_bound = np.percentile(bootstrapped_means, 100 * (1 - alpha / 2))
    return lower_bound, upper_bound

def main():
    df = pd.read_csv("results/experiment_5_raw.csv")
    
    metrics = {
        "topic_mastery_rate": "PRIMARY",
        "time_to_competency": "SECONDARY",
        "problem_solving_success_rate": "SECONDARY",
        "weak_topic_improvement": "SECONDARY"
    }
    
    results = []
    
    os.makedirs("analysis/charts", exist_ok=True)
    plt.figure(figsize=(20, 10))
    
    static_df = df[df["condition"] == "static"].set_index("student_id")
    adaptive_df = df[df["condition"] == "adaptive"].set_index("student_id")
    
    # Ensure they align
    common_idx = static_df.index.intersection(adaptive_df.index)
    static_df = static_df.loc[common_idx]
    adaptive_df = adaptive_df.loc[common_idx]
    
    plot_idx = 1
    
    for metric, designation in metrics.items():
        fixed_vals = static_df[metric].values
        sem_vals = adaptive_df[metric].values
        
        diffs = sem_vals - fixed_vals  # Positive means adaptive is higher
        
        n = len(diffs)
        
        if np.std(diffs) == 0:
            wilcoxon_stat, wilcoxon_p = np.nan, 1.0
        else:
            wilcoxon_stat, wilcoxon_p = stats.wilcoxon(diffs)
            
        mean_diff = np.mean(diffs)
        ci_lower, ci_upper = compute_bootstrap_ci(diffs)
        
        results.append({
            "metric": metric,
            "designation": designation,
            "N": n,
            "static_mean": np.mean(fixed_vals),
            "adaptive_mean": np.mean(sem_vals),
            "mean_paired_diff": mean_diff,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "wilcoxon_stat": wilcoxon_stat,
            "wilcoxon_p": wilcoxon_p,
            "significant": wilcoxon_p < 0.05 if not np.isnan(wilcoxon_p) else False,
            "dataset_version": static_df["dataset_version"].iloc[0],
            "dataset_sha256": static_df["dataset_sha256"].iloc[0],
            "simulation_model_version": static_df["simulation_model_version"].iloc[0]
        })
        
        plt.subplot(2, 3, plot_idx)
        plt.boxplot([fixed_vals, sem_vals], tick_labels=["Static", "Adaptive"])
        plt.title(f"{metric}\n(SIMULATED DATA)")
        plt.ylabel(metric)
        plot_idx += 1

    # Plot 5: Per-student mastery comparison (scatter)
    plt.subplot(2, 3, plot_idx)
    plt.scatter(static_df["topic_mastery_rate"], adaptive_df["topic_mastery_rate"], alpha=0.7)
    plt.plot([0, 1], [0, 1], 'r--')
    plt.xlabel("Static Mastery Rate")
    plt.ylabel("Adaptive Mastery Rate")
    plt.title("Per-Student Mastery Comparison\n(SIMULATED DATA)")
    plot_idx += 1
    
    # Plot 6: Replanning events histogram
    plt.subplot(2, 3, plot_idx)
    plt.hist(adaptive_df["replanning_events_count"], bins=range(0, int(adaptive_df["replanning_events_count"].max())+2), align='left')
    plt.xlabel("Replanning Events per Student")
    plt.ylabel("Frequency")
    plt.title("Adaptive Replanning Events\n(SIMULATED DATA)")
    
    plt.tight_layout()
    plt.savefig("analysis/charts/experiment_5_charts.png")
    
    stats_df = pd.DataFrame(results)
    stats_df.to_csv("analysis/experiment_5_statistics.csv", index=False)
    print("Analysis complete. Saved to analysis/experiment_5_statistics.csv and analysis/charts/experiment_5_charts.png")

if __name__ == "__main__":
    main()

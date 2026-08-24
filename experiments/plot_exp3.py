import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import os
import numpy as np

df = pd.read_csv("results/experiment_3_raw.csv")
os.makedirs("analysis/charts", exist_ok=True)

plt.figure(figsize=(15, 5))
systems = ["monolithic", "multi_agent"]

# Plot 1: Task Completion
plt.subplot(1, 3, 1)
completion = df.groupby("system")["task_completion"].mean()
plt.bar(systems, [completion.get(s, 0) for s in systems])
plt.title("Task Completion Rate")
plt.ylim(0, 1.05)

# Plot 2: Latency
plt.subplot(1, 3, 2)
latencies = [df[df["system"] == s]["latency_ms"].dropna() for s in systems]
plt.boxplot(latencies, tick_labels=systems)
plt.title("Latency (ms)")

# Plot 3: Quality Score
plt.subplot(1, 3, 3)
scores = [df[df["system"] == s]["quality_score"].dropna() for s in systems]
plt.boxplot(scores, tick_labels=systems)
plt.title("LLM Judge Quality Score (1-5)")

plt.tight_layout()
plt.savefig("analysis/charts/experiment_3_chart.png")

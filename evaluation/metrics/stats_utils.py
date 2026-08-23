"""
evaluation/metrics/stats_utils.py — Shared statistical utilities (Phase 2).

Implements paired non-parametric tests, bootstrap confidence intervals,
and generic effect-size helpers.  Reused by all experiments (1-5).
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.stats.contingency_tables import mcnemar

# ---------------------------------------------------------------------------
# Paired Binary Tests (McNemar)
# ---------------------------------------------------------------------------

def mcnemar_test(
    condition_a: list[bool],
    condition_b: list[bool],
    alpha: float = 0.05
) -> dict:
    """
    Compute McNemar's test for paired binary data.

    Args:
        condition_a: Boolean outcomes for System A (e.g., baseline).
        condition_b: Boolean outcomes for System B (e.g., treatment).
        alpha: Significance level.

    Returns:
        Dict with test_statistic, p_value, effect_size (odds ratio),
        and significant boolean.
    """
    if len(condition_a) != len(condition_b):
        raise ValueError("Conditions must have equal length for paired tests.")

    # Contingency table:
    # [[both False, B True / A False],
    #  [A True / B False, both True]]
    table = [[0, 0], [0, 0]]
    for a, b in zip(condition_a, condition_b):
        table[int(a)][int(b)] += 1

    # Exact binomial if discordant pairs < 25, else asymptotic chi-square
    b = table[0][1]
    c = table[1][0]
    discordant = b + c
    exact = discordant < 25

    result = mcnemar(table, exact=exact)

    # Effect size: Odds Ratio of discordant pairs
    # If c == 0, add 0.5 to cells (Haldane-Anscombe correction)
    if c == 0:
        odds_ratio = (b + 0.5) / (c + 0.5)
    else:
        odds_ratio = b / c

    return {
        "test_statistic": result.statistic,
        "p_value": result.pvalue,
        "effect_size": odds_ratio,  # Odds ratio of discordant pairs
        "significant": result.pvalue < alpha,
    }

# ---------------------------------------------------------------------------
# Bootstrap Confidence Intervals
# ---------------------------------------------------------------------------

def bootstrap_diff_ci(
    group_a: list[float],
    group_b: list[float],
    paired: bool = True,
    n_resamples: int = 9999,
    alpha: float = 0.05,
    random_seed: int = 42
) -> tuple[float, float]:
    """
    Compute bootstrap confidence interval for the mean difference (B - A).

    Args:
        group_a: Scores for System A.
        group_b: Scores for System B.
        paired: If True, resamples pairs. If False, resamples independently.
        n_resamples: Number of bootstrap iterations.
        alpha: Significance level (0.05 -> 95% CI).
        random_seed: For reproducibility.

    Returns:
        (ci_lower, ci_upper)
    """
    if paired and len(group_a) != len(group_b):
        raise ValueError("Paired bootstrap requires equal length arrays.")

    rng = np.random.default_rng(random_seed)
    a = np.array(group_a)
    b = np.array(group_b)
    n = len(a)

    diffs = []
    for _ in range(n_resamples):
        if paired:
            # Resample indices
            idx = rng.choice(n, size=n, replace=True)
            diff_mean = np.mean(b[idx] - a[idx])
        else:
            # Resample independently
            idx_a = rng.choice(len(a), size=len(a), replace=True)
            idx_b = rng.choice(len(b), size=len(b), replace=True)
            diff_mean = np.mean(b[idx_b]) - np.mean(a[idx_a])
        diffs.append(diff_mean)

    diffs = np.array(diffs)
    lower = np.percentile(diffs, 100 * (alpha / 2))
    upper = np.percentile(diffs, 100 * (1 - alpha / 2))

    return lower, upper

# ---------------------------------------------------------------------------
# Multiple Comparison Correction
# ---------------------------------------------------------------------------

def benjamini_hochberg(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    """
    Apply Benjamini-Hochberg FDR correction.

    Returns:
        List of booleans (True if significant after correction), in original order.
    """
    n = len(p_values)
    if n == 0:
        return []

    # Sort p-values while keeping track of original indices
    sorted_p_with_idx = sorted(enumerate(p_values), key=lambda x: x[1])

    significant = [False] * n
    max_k = -1

    for k, (orig_idx, p) in enumerate(sorted_p_with_idx):
        # Benjamini-Hochberg critical value: (k / n) * alpha, where k is 1-based rank
        rank = k + 1
        critical_value = (rank / n) * alpha
        if p <= critical_value:
            max_k = k

    # Reject null for all tests up to max_k
    if max_k >= 0:
        for k in range(max_k + 1):
            orig_idx = sorted_p_with_idx[k][0]
            significant[orig_idx] = True

    return significant

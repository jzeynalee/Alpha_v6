"""Shared statistical calculations used by research pipelines and scripts."""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


def profit_factor(returns: np.ndarray) -> float:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    gross_profit = float(np.sum(values[values > 0]))
    gross_loss = float(-np.sum(values[values < 0]))
    if gross_loss == 0.0:
        return float("inf") if gross_profit > 0.0 else 0.0
    return gross_profit / gross_loss


def bootstrap_metrics(
    returns: np.ndarray,
    n_bootstrap: int = 2000,
    seed: int = 42,
    confidence: float = 0.95,
) -> Dict[str, Any]:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    n = len(values)
    if n < 10:
        return {
            "p_value": 1.0,
            "ci_lower_95": float("nan"),
            "ci_upper_95": float("nan"),
            "mean": float(np.mean(values)) if n else 0.0,
            "std": float(np.std(values, ddof=1)) if n > 1 else 0.0,
            "n_samples": n,
            "error": "Insufficient data (need >= 10 returns)",
        }

    rng = np.random.default_rng(seed)
    observed_mean = float(np.mean(values))
    bootstrap_means = np.mean(rng.choice(values, size=(n_bootstrap, n), replace=True), axis=1)
    alpha = 1.0 - confidence
    centered = values - observed_mean
    null_means = np.mean(rng.choice(centered, size=(n_bootstrap, n), replace=True), axis=1)
    if observed_mean > 0:
        p_value = float((1 + np.sum(null_means >= observed_mean)) / (n_bootstrap + 1))
    else:
        p_value = float((1 + np.sum(null_means <= observed_mean)) / (n_bootstrap + 1))

    return {
        "p_value": p_value,
        "ci_lower_95": float(np.percentile(bootstrap_means, 100 * alpha / 2)),
        "ci_upper_95": float(np.percentile(bootstrap_means, 100 * (1 - alpha / 2))),
        "mean": observed_mean,
        "std": float(np.std(values, ddof=1)),
        "n_samples": n,
        "n_bootstrap": n_bootstrap,
    }


def outlier_robustness(returns: np.ndarray, trim_pct: float = 0.01) -> Dict[str, Any]:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 20:
        return {
            "pf_full": 0.0,
            "pf_trimmed": 0.0,
            "pf_drop_pct": 100.0,
            "error": "Insufficient data (need >= 20 returns)",
        }
    sorted_values = np.sort(values)
    n_trim = max(1, int(len(values) * trim_pct))
    trimmed = sorted_values[n_trim:-n_trim] if len(values) > 2 * n_trim else values
    pf_full = profit_factor(values)
    pf_trimmed = profit_factor(trimmed)
    drop = abs(pf_full - pf_trimmed) / max(abs(pf_full), 1e-9)
    return {
        "pf_full": round(pf_full, 4),
        "pf_trimmed": round(pf_trimmed, 4),
        "pf_drop_pct": round(drop * 100, 2),
        "n_trimmed_each_side": n_trim,
    }


def regime_stability(returns_by_regime: Dict[str, np.ndarray]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for regime, returns in returns_by_regime.items():
        values = np.asarray(returns, dtype=float)
        values = values[np.isfinite(values)]
        key = regime.lower()
        result[f"{key}_n"] = len(values)
        result[f"{key}_pf"] = float("nan") if len(values) < 5 else round(profit_factor(values), 4)
    result["n_regimes_positive"] = sum(
        1 for key, value in result.items() if key.endswith("_pf") and value > 1.0
    )
    result["total_regimes"] = len(returns_by_regime)
    return result


def classify_regime(closes: pd.Series) -> list[str]:
    momentum = closes.pct_change(20)
    bull = momentum.rolling(60).quantile(0.67)
    bear = momentum.rolling(60).quantile(0.33)
    regimes: list[str] = []
    for index in range(len(closes)):
        value = momentum.iloc[index]
        if pd.isna(value) or pd.isna(bull.iloc[index]) or pd.isna(bear.iloc[index]):
            regimes.append("Neutral")
        elif value > bull.iloc[index]:
            regimes.append("Bull")
        elif value < bear.iloc[index]:
            regimes.append("Bear")
        else:
            regimes.append("Neutral")
    return regimes


__all__ = [
    "bootstrap_metrics",
    "classify_regime",
    "outlier_robustness",
    "profit_factor",
    "regime_stability",
]

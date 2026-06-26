# src/validation/metrics.py
"""Shared backtest metrics and utilities used across all experiment scripts.

Previously duplicated in every experiment script:
  - compute_zscore / map_zscore (Z-score from one timeframe to another)
  - simulate (simple trade simulation with costs and fixed-bar exit)
  - compute_returns (per-trade % returns from signals)

Usage:
    from src.validation.metrics import compute_zscore, simulate, walkforward_split
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# Z-Score
# ═══════════════════════════════════════════════════════════════════════════════

def compute_zscore(closes: np.ndarray, period: int = 200) -> np.ndarray:
    """Compute rolling Z-score on a 1-D array of closes.

    Parameters
    ----------
    closes : np.ndarray
        1-D array of closing prices.
    period : int
        Rolling window length for mean and std.

    Returns
    -------
    np.ndarray
        Z-score values (NaN for first `period-1` elements).
    """
    sma = np.full(len(closes), np.nan)
    std = np.full(len(closes), np.nan)
    for i in range(period - 1, len(closes)):
        sma[i] = np.mean(closes[i - period + 1:i + 1])
        std[i] = np.std(closes[i - period + 1:i + 1], ddof=0)
    z = np.full(len(closes), np.nan)
    valid = ~np.isnan(sma) & ~np.isnan(std) & (std > 0)
    z[valid] = (closes[valid] - sma[valid]) / std[valid]
    return z


def map_to(src_ts: np.ndarray, tgt_vals: np.ndarray, tgt_ts: np.ndarray) -> np.ndarray:
    """Map target values to source timestamps via nearest-prior lookup.

    For each timestamp in src_ts, finds the most recent timestamp in tgt_ts
    that is ≤ src_ts and returns the corresponding tgt_vals value.

    Parameters
    ----------
    src_ts : np.ndarray
        Source timestamps (e.g., 5m bar timestamps).
    tgt_vals : np.ndarray
        Target values to map (e.g., 4h Z-score values).
    tgt_ts : np.ndarray
        Target timestamps corresponding to tgt_vals.

    Returns
    -------
    np.ndarray
        Mapped values, same length as src_ts. NaN where no prior lookup exists.
    """
    result = np.full(len(src_ts), np.nan)
    for j, ts in enumerate(src_ts):
        idx = np.searchsorted(tgt_ts, ts, side="right") - 1
        if 0 <= idx < len(tgt_vals):
            result[j] = tgt_vals[idx]
    return result


# Legacy alias for backward compatibility with existing scripts.
map_zscore = map_to


# ═══════════════════════════════════════════════════════════════════════════════
# Trade Simulation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_returns(
    closes: np.ndarray,
    indices: np.ndarray,
    entries: np.ndarray,
    directions: np.ndarray,
    cost_bps: float,
    exit_bars: int = 10,
) -> np.ndarray:
    """Compute per-trade percentage returns from a list of entry signals.

    Parameters
    ----------
    closes : np.ndarray
        Full close price array for the dataset.
    indices : np.ndarray
        Bar indices of entry signals (int).
    entries : np.ndarray
        Entry prices for each signal.
    directions : np.ndarray
        Trade direction: +1 for long, -1 for short.
    cost_bps : float
        One-way cost in basis points (e.g., 5.0 = 5 bps).
    exit_bars : int
        Number of bars to hold before exit.

    Returns
    -------
    np.ndarray
        Per-trade percentage returns. Empty array if no valid trades.
    """
    rets = []
    n_b = len(closes)
    for j in range(len(indices)):
        idx = int(indices[j])
        if idx + exit_bars >= n_b:
            continue
        entry = entries[j] * (1 + cost_bps / 10000 * directions[j])
        exit_p = closes[idx + exit_bars] * (1 - cost_bps / 10000 * directions[j])
        rets.append(directions[j] * (exit_p - entry) / entries[j] * 100)
    return np.array(rets)


def simulate(
    closes: np.ndarray,
    indices: np.ndarray,
    entries: np.ndarray,
    directions: np.ndarray,
    cost_bps: float,
    exit_bars: int = 10,
) -> dict:
    """Run a simple backtest simulation and return summary metrics.

    Parameters
    ----------
    closes, indices, entries, directions, cost_bps, exit_bars:
        Same as compute_returns.

    Returns
    -------
    dict with keys: n, pf, wr, mean_ret, total_return, best, worst, rets, std.
    """
    rets = compute_returns(closes, indices, entries, directions, cost_bps, exit_bars)
    if len(rets) == 0:
        return {
            "n": 0, "pf": 0, "wr": 0, "mean_ret": 0,
            "total_return": 0, "best": 0, "worst": 0,
            "rets": np.array([]), "std": 0,
        }

    gp = np.sum(rets[rets > 0]) if np.any(rets > 0) else 0
    gl = abs(np.sum(rets[rets < 0])) if np.any(rets < 0) else 1e-9
    return {
        "n": len(rets),
        "pf": float(gp / gl),
        "wr": float(100 * np.mean(rets > 0)),
        "mean_ret": float(np.mean(rets)),
        "total_return": float(np.sum(rets)),
        "best": float(np.max(rets)),
        "worst": float(np.min(rets)),
        "rets": rets,
        "std": float(np.std(rets)),
    }


def monte_carlo_risk(
    rets: np.ndarray,
    n_sims: int = 10_000,
    starting_capital: float = 10_000,
    risk_per_trade: float = 0.005,
    seed: int = 42,
) -> dict:
    """Monte Carlo simulation via trade reshuffling.

    Parameters
    ----------
    rets : np.ndarray
        Per-trade % returns (e.g., +0.5 means +0.5%).
    n_sims : int
        Number of simulation runs.
    starting_capital : float
        Initial equity.
    risk_per_trade : float
        Fraction of capital risked per trade (0.5% = 0.005).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    dict with final_equity, max_drawdown, ruin_probability, etc.
    """
    n_trades = len(rets)
    if n_trades < 5:
        return {"error": f"Need ≥ 5 trades, got {n_trades}"}

    rng = np.random.RandomState(seed)

    final_equities = []
    max_drawdowns = []
    cagrs = []
    max_consecutive_losses = []

    for _ in range(n_sims):
        shuffled = rng.choice(rets, size=n_trades, replace=True)
        equity = starting_capital
        peak = equity
        max_dd = 0.0
        consec_losses = 0
        max_cons = 0

        for r in shuffled:
            trade_pnl = (r / 100.0) * risk_per_trade * equity
            equity += trade_pnl
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
            if trade_pnl < 0:
                consec_losses += 1
                max_cons = max(max_cons, consec_losses)
            else:
                consec_losses = 0

        final_equities.append(equity)
        max_drawdowns.append(max_dd)
        cagrs.append(
            (equity / starting_capital) ** (1 / max(1, n_trades / 10)) - 1
            if equity > 0 else -1.0
        )
        max_consecutive_losses.append(max_cons)

    fe = np.array(final_equities)
    dd_array = np.array(max_drawdowns)
    ca = np.array(cagrs)
    cl = np.array(max_consecutive_losses)

    return {
        "n_trades": n_trades,
        "n_sims": n_sims,
        "final_equity": {
            "mean": float(np.mean(fe)),
            "median": float(np.median(fe)),
            "p5": float(np.percentile(fe, 5)),
            "p95": float(np.percentile(fe, 95)),
        },
        "max_drawdown": {
            "mean": float(np.mean(dd_array)),
            "median": float(np.median(dd_array)),
            "p95": float(np.percentile(dd_array, 95)),
            "worst": float(np.max(dd_array)),
        },
        "cagr": {
            "mean": float(np.mean(ca)),
            "median": float(np.median(ca)),
            "p5": float(np.percentile(ca, 5)),
        },
        "consecutive_losses": {
            "mean": float(np.mean(cl)),
            "median": float(np.median(cl)),
            "p95": float(np.percentile(cl, 95)),
            "max": int(np.max(cl)),
        },
        "ruin_probability": {
            "dd_gt_20pct": float(np.mean(dd_array > 0.20)),
            "dd_gt_30pct": float(np.mean(dd_array > 0.30)),
            "dd_gt_50pct": float(np.mean(dd_array > 0.50)),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Walk-Forward Split Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def find_splits_by_date(path_5m: str) -> dict:
    """Find row indices for standard train/val/holdout splits by date.

    Split boundaries:
      Train:       up to 2024-12-31
      Validation:  2025-01-01 → 2025-12-31
      Holdout:     2026-01-01 → end of data

    Assumes timestamp column is in UNIX seconds.

    Parameters
    ----------
    path_5m : str
        Path to 5m OHLCV CSV with 'timestamp' column.

    Returns
    -------
    dict with keys: total_rows, train_end, val_end.
    """
    ts = pd.read_csv(path_5m, usecols=["timestamp"])["timestamp"].values

    val_start_ts = 1735689600   # 2025-01-01 00:00:00 UTC
    hold_start_ts = 1767225600  # 2026-01-01 00:00:00 UTC

    train_end = int(np.searchsorted(ts, val_start_ts))
    val_end = int(np.searchsorted(ts, hold_start_ts))

    return {
        "total_rows": len(ts),
        "train_end": train_end,
        "val_end": val_end,
        "splits": {
            "train": (0, train_end),
            "val": (train_end, val_end),
            "holdout": (val_end, len(ts)),
        },
    }


def walkforward_report(results: dict, cost_bps: float = 5.0) -> str:
    """Generate a human-readable walk-forward report.

    Parameters
    ----------
    results : dict
        Nested dict: results[split]["r5" or "r10"] -> simulate() output.
    cost_bps : float
        Cost level to report.

    Returns
    -------
    str
        Formatted report string.
    """
    lines = []
    for split, label in [("train", "Train 2023-24"), ("val", "Val 2025"),
                           ("holdout", "Holdout 2026")]:
        r = results.get(split, {})
        r5 = r.get("r5", {})
        r10 = r.get("r10", {})
        n = r5.get("n", 0)
        pf = r5.get("pf", 0)
        pf10 = r10.get("pf", 0)
        wr = r5.get("wr", 0)
        mr = r5.get("mean_ret", 0)

        if n == 0:
            verdict = "NO TRADES"
        elif pf >= 1.5:
            verdict = "SURVIVES"
        elif pf >= 1.0:
            verdict = "MARGINAL"
        else:
            verdict = "FAILS"

        lines.append(
            f"  {label:<16s}  n={n:>4d}  PF({cost_bps}bps)={pf:>6.2f}  "
            f"PF(10bps)={pf10:>6.2f}  WR={wr:>5.1f}%  "
            f"MeanRet={mr:>+8.3f}%  [{verdict}]"
        )
    return "\n".join(lines)

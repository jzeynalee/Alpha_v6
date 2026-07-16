"""
Portfolio-Level Backtest — Combines top strategies with risk-parity allocation.

Strategies included:
  - eth_mom_l1: ETH 1h Momentum (PF=1.71, Sharpe=3.59)
  - sol_mom_l1: SOL 1h Momentum (PF=1.28, Sharpe=1.66)
  - pos_002: BTC 15m OI Divergence (PF=1.08, 96 trades)
  - pos_004: BTC 15m Funding Cross-Asset (PF=1.11, 42 trades)

Allocation methods:
  - Equal weight
  - Risk parity (inverse vol)
  - Evidence-level weighted

Usage:
    python scripts/portfolio_backtest.py --max-bars 5000
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.getLogger("src.risk").setLevel(logging.ERROR)
logging.getLogger("src.risk.trade_journal").setLevel(logging.ERROR)
logging.getLogger("src.risk.risk_manager").setLevel(logging.ERROR)
logging.getLogger("src.backtest.data").setLevel(logging.WARNING)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("portfolio")

from src.core.dataset_registry import registry as data_registry
from src.core.evidence_ladder import EvidenceLadder, HypothesisRecord
from src.core.experiment_manager import ExperimentManager, ExperimentSpec
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.features.positioning_enricher import enrich_ohlcv, clear_cache


# ═══════════════════════════════════════════════════════════════════════════════
# Portfolio Configuration
# ═══════════════════════════════════════════════════════════════════════════════

PORTFOLIO_STRATEGIES = [
    {
        "hypothesis_id": "eth_mom_l1",
        "symbol": "ETHUSDT",
        "timeframe": "1h",
        "needs_enrichment": False,
    },
    {
        "hypothesis_id": "sol_mom_l1",
        "symbol": "SOLUSDT",
        "timeframe": "1h",
        "needs_enrichment": False,
    },
    {
        "hypothesis_id": "pos_002",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "needs_enrichment": True,
    },
    {
        "hypothesis_id": "pos_004",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "needs_enrichment": True,
    },
]


def run_single_strategy(
    hypothesis_id: str,
    symbol: str,
    timeframe: str,
    max_bars: int = 5000,
    needs_enrichment: bool = False,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Run one strategy backtest and return equity curve + metrics."""
    logger.info("Running %s on %s/%s...", hypothesis_id, symbol, timeframe)

    ladder = EvidenceLadder()
    ladder.load()
    record = ladder.get(hypothesis_id)

    if record is None or record.archived:
        logger.warning("Skipping %s: not found or archived", hypothesis_id)
        return np.array([]), {}

    # Load data
    ohlcv = data_registry.get_ohlcv("binance", symbol, timeframe)
    if ohlcv is None:
        logger.warning("No data for %s/%s", symbol, timeframe)
        return np.array([]), {}

    if len(ohlcv) > max_bars:
        ohlcv = ohlcv.iloc[-max_bars:].copy()
    ohlcv = ohlcv.reset_index()

    # Enrich if needed
    if needs_enrichment:
        ohlcv = enrich_ohlcv(ohlcv, symbol)
        ohlcv = ohlcv.reset_index()
        ts_col = [c for c in ohlcv.columns if "time" in c.lower()]
        if ts_col and "timestamp" not in ohlcv.columns:
            ohlcv = ohlcv.rename(columns={ts_col[0]: "timestamp"})

    # Get signal
    signal_fn = ExperimentManager._auto_signal_source(record)
    if signal_fn is None:
        logger.warning("No signal for %s", hypothesis_id)
        return np.array([]), {}

    # Run backtest
    config = BacktestConfig(
        initial_cash=10_000.0,
        fee_pct=0.001,
        slippage_pct=0.0005,
        warmup_bars=100,
        allow_short=True,
    )
    engine = BacktestEngine(signal_source=signal_fn, config=config)
    result = engine.run(ohlcv)

    # Extract equity curve
    equity = np.array([pt.equity for pt in result.equity_curve])

    metrics = {
        "pf": result.profit_factor,
        "sharpe": result.sharpe,
        "win_rate": result.win_rate,
        "trades": result.closed_trades,
        "total_return": result.total_return_pct,
        "max_dd": result.equity_max_drawdown_pct,
    }

    logger.info(
        "  %s: PF=%.3f Sharpe=%.3f Trades=%d DD=%.1f%%",
        hypothesis_id, metrics["pf"], metrics["sharpe"],
        metrics["trades"], metrics["max_dd"],
    )

    return equity, metrics


def compute_portfolio_returns(
    equity_curves: List[np.ndarray],
    weights: np.ndarray,
) -> np.ndarray:
    """Combine equity curves into portfolio returns with given weights."""
    # Align lengths to the shortest curve
    min_len = min(len(eq) for eq in equity_curves if len(eq) > 0)
    if min_len < 2:
        return np.array([])

    aligned = []
    for eq in equity_curves:
        if len(eq) < min_len:
            continue
        aligned.append(eq[-min_len:])

    if not aligned:
        return np.array([])

    # Stack and compute weighted returns
    stacked = np.column_stack(aligned)
    returns = np.diff(stacked, axis=0) / (stacked[:-1] + 1e-9)
    portfolio_returns = returns @ weights[:len(aligned)]
    return portfolio_returns


def compute_metrics(returns: np.ndarray) -> Dict[str, Any]:
    """Compute portfolio-level metrics."""
    if len(returns) < 2:
        return {}

    mean_ret = float(np.mean(returns))
    std_ret = float(np.std(returns, ddof=1))
    sharpe = mean_ret / std_ret * np.sqrt(252 * 96) if std_ret > 0 else 0.0  # annualized (15m bars)

    # Equity curve
    equity = 10000 * np.cumprod(1 + returns)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(np.min(dd) * 100)

    # Profit factor
    gross_profit = float(np.sum(returns[returns > 0]))
    gross_loss = float(abs(np.sum(returns[returns < 0])))
    pf = gross_profit / gross_loss if gross_loss > 0 else 0.0

    # Win rate
    win_rate = float(np.mean(returns > 0))

    # Total return
    total_return = float((equity[-1] / equity[0] - 1) * 100)

    return {
        "sharpe": round(sharpe, 3),
        "profit_factor": round(pf, 3),
        "win_rate": round(win_rate, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "total_return_pct": round(total_return, 2),
        "n_bars": len(returns),
    }


def compute_correlation(equity_curves: List[np.ndarray]) -> np.ndarray:
    """Compute correlation matrix of strategy returns."""
    min_len = min(len(eq) for eq in equity_curves if len(eq) > 1)
    if min_len < 2:
        return np.array([[]])

    returns_list = []
    for eq in equity_curves:
        if len(eq) < min_len:
            continue
        eq = eq[-min_len:]
        ret = np.diff(eq) / (eq[:-1] + 1e-9)
        returns_list.append(ret)

    if len(returns_list) < 2:
        return np.array([[]])

    stacked = np.column_stack(returns_list)
    return np.corrcoef(stacked.T)


def main():
    max_bars = 5000
    if len(sys.argv) > 1 and "--max-bars" in sys.argv:
        idx = sys.argv.index("--max-bars")
        max_bars = int(sys.argv[idx + 1])

    clear_cache()

    print("\n" + "=" * 70)
    print("PORTFOLIO BACKTEST — Multi-Strategy Ensemble")
    print("=" * 70)

    # ── Run individual strategies ──────────────────────────────────────────
    equity_curves = []
    all_metrics = []
    strategy_names = []

    for cfg in PORTFOLIO_STRATEGIES:
        eq, metrics = run_single_strategy(
            hypothesis_id=cfg["hypothesis_id"],
            symbol=cfg["symbol"],
            timeframe=cfg["timeframe"],
            max_bars=max_bars,
            needs_enrichment=cfg["needs_enrichment"],
        )
        if len(eq) > 0 and metrics:
            equity_curves.append(eq)
            all_metrics.append(metrics)
            strategy_names.append(f"{cfg['hypothesis_id']}({cfg['symbol']})")

    if len(equity_curves) < 2:
        print("ERROR: Need at least 2 strategies with valid data")
        return

    # ── Correlation Matrix ─────────────────────────────────────────────────
    print("\n--- Correlation Matrix (Daily Returns) ---")
    corr = compute_correlation(equity_curves)
    if corr.size > 1:
        print(f"{'':>25}", end="")
        for name in strategy_names:
            print(f" {name:>12}", end="")
        print()
        for i, name in enumerate(strategy_names):
            print(f"  {name:>23}", end="")
            for j in range(len(strategy_names)):
                if j < corr.shape[1]:
                    print(f" {corr[i, j]:12.4f}", end="")
            print()

    # ── Allocation Methods ─────────────────────────────────────────────────
    n = len(equity_curves)

    # Equal weight
    eq_weights = np.ones(n) / n
    eq_returns = compute_portfolio_returns(equity_curves, eq_weights)
    eq_metrics = compute_metrics(eq_returns)

    # Risk parity (inverse vol)
    vols = np.array([np.std(np.diff(eq[-min(len(eq) for eq in equity_curves):]) /
                            (eq[-min(len(eq) for eq in equity_curves):-1] + 1e-9))
                     for eq in equity_curves])
    vols = np.where(vols > 0, vols, 1e-6)
    rp_weights = (1.0 / vols) / np.sum(1.0 / vols)
    rp_returns = compute_portfolio_returns(equity_curves, rp_weights)
    rp_metrics = compute_metrics(rp_returns)

    # Sharpe-weighted
    sharpes = np.array([m["sharpe"] for m in all_metrics])
    sharpes = np.where(sharpes > 0, sharpes, 0.01)
    sw_weights = sharpes / np.sum(sharpes)
    sw_returns = compute_portfolio_returns(equity_curves, sw_weights)
    sw_metrics = compute_metrics(sw_returns)

    # ── Print Results ──────────────────────────────────────────────────────
    print("\n--- Individual Strategy Metrics ---")
    for i, (name, m) in enumerate(zip(strategy_names, all_metrics)):
        print(f"  {name}: PF={m['pf']:.3f} Sharpe={m['sharpe']:.3f} "
              f"Trades={m['trades']} DD={m['max_dd']:.1f}%")

    print("\n--- Portfolio Allocation ---")
    print(f"{'Method':<20} {'PF':>8} {'Sharpe':>8} {'MaxDD':>8} {'Return':>8} {'Weights'}")
    print("-" * 70)

    for method_name, w, m in [
        ("Equal Weight", eq_weights, eq_metrics),
        ("Risk Parity", rp_weights, rp_metrics),
        ("Sharpe Weighted", sw_weights, sw_metrics),
    ]:
        weights_str = ", ".join(f"{name.split('(')[0]}={w[i]:.2f}" for i, name in enumerate(strategy_names))
        print(f"  {method_name:<18} {m['profit_factor']:8.3f} {m['sharpe']:8.3f} "
              f"{m['max_drawdown_pct']:7.1f}% {m['total_return_pct']:7.1f}%  [{weights_str}]")

    # ── Best method ────────────────────────────────────────────────────────
    best = max(
        [(eq_metrics, "Equal Weight"), (rp_metrics, "Risk Parity"), (sw_metrics, "Sharpe Weighted")],
        key=lambda x: x[0]["sharpe"],
    )
    print(f"\n🏆 Best Allocation: {best[1]} (Sharpe={best[0]['sharpe']:.3f}, PF={best[0]['profit_factor']:.3f})")

    # ── Improvement over best individual ───────────────────────────────────
    best_individual_sharpe = max(m["sharpe"] for m in all_metrics)
    improvement = (best[0]["sharpe"] - best_individual_sharpe) / max(abs(best_individual_sharpe), 0.01) * 100
    print(f"📈 Portfolio Sharpe improvement over best individual: {improvement:+.1f}%")

    print("=" * 70)


if __name__ == "__main__":
    main()

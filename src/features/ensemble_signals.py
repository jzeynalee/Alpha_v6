"""
EnsembleAlpha — Multi-strategy signal combiners with regime-aware allocation.

Architecture:
  ┌──────────────────────────────────────────────────────────┐
  │                 EnsembleEnricher                          │
  │  Pre-computes all sub-strategy signals into DataFrame    │
  │  columns: sig_mom_eth, sig_mom_sol, sig_oi_div,          │
  │           sig_fund_cross, sig_regime                     │
  └──────────────────────┬───────────────────────────────────┘
                         │
  ┌──────────────────────┴───────────────────────────────────┐
  │  ensemble_001: Regime-Adaptive                            │
  │    Trending (ADX > 25) → 70% momentum / 30% OI           │
  │    Ranging (ADX < 20)  → 30% momentum / 70% OI           │
  │    Mixed                → 50% / 50%                       │
  │                                                           │
  │  ensemble_002: Equal-Weight Blend                         │
  │    25% each: eth_mom + sol_mom + oi_div + fund_cross     │
  └──────────────────────────────────────────────────────────┘

Usage:
    from src.features.ensemble_signals import EnsembleEnricher, get_ensemble_signal
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.backtest.signal_source import BacktestSignal
from src.features.mean_reversion_signals import _compute_adx

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Ensemble Enricher — pre-compute sub-signals into DataFrame columns
# ═══════════════════════════════════════════════════════════════════════════════

class EnsembleEnricher:
    """
    Pre-computes sub-strategy signals and regime classification into a
    DataFrame so the ensemble signal function can do simple column reads.

    Call once before backtest:
        enricher = EnsembleEnricher()
        df = enricher.enrich(btc_15m_df, eth_1h_df, sol_1h_df)
    """

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def enrich(
        self,
        btc_15m: pd.DataFrame,
        eth_1h: Optional[pd.DataFrame] = None,
        sol_1h: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Add sub-signal columns to the BTC 15m DataFrame.

        Columns added:
          sig_mom_eth     — eth_mom_l1 direction (-1/0/+1)
          sig_mom_sol     — sol_mom_l1 direction (-1/0/+1)
          sig_oi_div      — pos_002 direction (-1/0/+1)
          sig_fund_cross  — pos_004 direction (-1/0/+1)
          sig_regime      — regime classification (0=ranging, 1=mixed, 2=trending)
        """
        df = btc_15m.copy()

        # ── Compute OI/funding sub-signals on BTC 15m ──────────────────────
        try:
            from src.features.positioning_signals import (
                signal_pos_002_oi_divergence,
                signal_pos_004_funding_divergence_cross,
            )
            df["sig_oi_div"] = self._vectorize_signal(df, signal_pos_002_oi_divergence, "BTCUSDT")
            df["sig_fund_cross"] = self._vectorize_signal(df, signal_pos_004_funding_divergence_cross, "BTCUSDT")
        except Exception as e:
            logger.warning("OI/funding sub-signals failed: %s", e)
            df["sig_oi_div"] = 0
            df["sig_fund_cross"] = 0

        # ── Compute momentum sub-signals (ETH/SOL 1h → resample to 15m) ───
        try:
            from src.features.momentum_signals import signal_momentum_improved

            if eth_1h is not None and len(eth_1h) > 100:
                eth_signals = self._vectorize_signal(eth_1h, signal_momentum_improved, "ETHUSDT")
                eth_series = pd.Series(eth_signals, index=eth_1h.index[:len(eth_signals)])
                df["sig_mom_eth"] = eth_series.reindex(df.index, method="ffill").fillna(0).values
            else:
                df["sig_mom_eth"] = 0

            if sol_1h is not None and len(sol_1h) > 100:
                sol_signals = self._vectorize_signal(sol_1h, signal_momentum_improved, "SOLUSDT")
                sol_series = pd.Series(sol_signals, index=sol_1h.index[:len(sol_signals)])
                df["sig_mom_sol"] = sol_series.reindex(df.index, method="ffill").fillna(0).values
            else:
                df["sig_mom_sol"] = 0
        except Exception as e:
            logger.warning("Momentum sub-signals failed: %s", e)
            df["sig_mom_eth"] = 0
            df["sig_mom_sol"] = 0

        # ── Compute regime classification ──────────────────────────────────
        df["sig_regime"] = self._classify_regime_vectorized(df)

        return df

    @staticmethod
    def _vectorize_signal(df: pd.DataFrame, signal_fn, symbol: str) -> list:
        """Run a signal function bar-by-bar over the DataFrame vectorized."""
        directions = []
        for i in range(len(df)):
            window = df.iloc[:i + 1]
            sig = signal_fn(symbol, window, i)
            directions.append(sig.direction)
        return directions

    @staticmethod
    def _classify_regime_vectorized(df: pd.DataFrame) -> pd.Series:
        """Classify each bar as 0=ranging, 1=mixed, 2=trending using ADX."""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        adx, plus_di, minus_di = _compute_adx(high, low, close)
        regime = pd.Series(1, index=df.index, dtype=int)  # default: mixed

        # Trending: ADX > 25
        regime[adx > 25] = 2
        # Ranging: ADX < 20
        regime[adx < 20] = 0

        return regime.fillna(1).astype(int)


# ═══════════════════════════════════════════════════════════════════════════════
# ensemble_001: Regime-Adaptive Allocation
#
#   Trending (sig_regime == 2):  70% momentum (35% ETH + 35% SOL) / 30% OI
#   Ranging (sig_regime == 0):   30% momentum / 70% OI (35% oi_div + 35% fund_cross)
#   Mixed (sig_regime == 1):     50% / 50%
#
#   Sub-signals are -1 (short), 0 (flat), +1 (long).
#   Ensemble aggregates by weighted voting then thresholds.
# ═══════════════════════════════════════════════════════════════════════════════

def _get_sub_signals(window: pd.DataFrame) -> Dict[str, float]:
    """Extract latest sub-signal values from the window."""
    result = {}
    for col in ["sig_mom_eth", "sig_mom_sol", "sig_oi_div", "sig_fund_cross"]:
        if col in window.columns:
            val = window[col].iloc[-1]
            result[col] = float(val) if not pd.isna(val) else 0.0
        else:
            result[col] = 0.0
    return result


def signal_ensemble_001_regime_adaptive(
    symbol: str, window: pd.DataFrame, bar_index: int = 0
) -> BacktestSignal:
    """Regime-adaptive ensemble: allocates based on ADX trend strength."""
    if len(window) < 100:
        return BacktestSignal.flat()

    sigs = _get_sub_signals(window)
    regime = int(window["sig_regime"].iloc[-1]) if "sig_regime" in window.columns else 1

    # ── Weight matrix ──────────────────────────────────────────────────────
    if regime == 2:  # Trending → heavy momentum
        w_eth_mom, w_sol_mom = 0.35, 0.35
        w_oi_div, w_fund_cross = 0.15, 0.15
    elif regime == 0:  # Ranging → heavy OI/funding
        w_eth_mom, w_sol_mom = 0.15, 0.15
        w_oi_div, w_fund_cross = 0.35, 0.35
    else:  # Mixed
        w_eth_mom, w_sol_mom = 0.25, 0.25
        w_oi_div, w_fund_cross = 0.25, 0.25

    # ── Weighted vote ──────────────────────────────────────────────────────
    weighted_score = (
        sigs["sig_mom_eth"] * w_eth_mom
        + sigs["sig_mom_sol"] * w_sol_mom
        + sigs["sig_oi_div"] * w_oi_div
        + sigs["sig_fund_cross"] * w_fund_cross
    )

    # ── Threshold ──────────────────────────────────────────────────────────
    if weighted_score > 0.40:
        return BacktestSignal(direction=1, proba_alpha=0.68)
    elif weighted_score < -0.40:
        return BacktestSignal(direction=-1, proba_alpha=0.68)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# ensemble_002: Equal-Weight Blend
#
#   25% each: eth_mom + sol_mom + oi_div + fund_cross
#   No regime awareness — pure diversification play.
# ═══════════════════════════════════════════════════════════════════════════════

def signal_ensemble_002_equal_weight(
    symbol: str, window: pd.DataFrame, bar_index: int = 0
) -> BacktestSignal:
    """Equal-weight ensemble: 25% each strategy, regime-agnostic."""
    if len(window) < 100:
        return BacktestSignal.flat()

    sigs = _get_sub_signals(window)

    # Equal weight: 0.25 each
    weighted_score = (
        sigs["sig_mom_eth"] * 0.25
        + sigs["sig_mom_sol"] * 0.25
        + sigs["sig_oi_div"] * 0.25
        + sigs["sig_fund_cross"] * 0.25
    )

    if weighted_score > 0.40:
        return BacktestSignal(direction=1, proba_alpha=0.63)
    elif weighted_score < -0.40:
        return BacktestSignal(direction=-1, proba_alpha=0.63)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# Signal registry
# ═══════════════════════════════════════════════════════════════════════════════

ENSEMBLE_SIGNALS = {
    "ensemble_001": signal_ensemble_001_regime_adaptive,
    "ensemble_002": signal_ensemble_002_equal_weight,
}


def get_ensemble_signal(hypothesis_id: str):
    """Get the signal function for an EnsembleAlpha hypothesis."""
    return ENSEMBLE_SIGNALS.get(hypothesis_id)

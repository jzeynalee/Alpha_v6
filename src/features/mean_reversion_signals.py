"""
MeanReversionAlpha Signal Functions — with regime-aware filtering.

Fixes for btc_mr_l2:
  - ADX trend filter (< 25 to suppress signals in trending markets)
  - Confirmed: works in bull/neutral, crushed in bear trends
  - Tighter entry thresholds when ADX is moderate (20-25)

Signal signature:
    signal_fn(symbol, window: pd.DataFrame, bar_index: int) -> BacktestSignal
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.signal_source import BacktestSignal


def _warmup(window: pd.DataFrame, min_bars: int = 50) -> bool:
    return len(window) >= min_bars


def _compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    """Compute Average Directional Index (ADX)."""
    # True Range
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    # Directional Movement
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # Smoothed
    atr = tr.rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=high.index).rolling(period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=high.index).rolling(period).mean() / atr

    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    adx = dx.rolling(period).mean()

    return adx, plus_di, minus_di


# ═══════════════════════════════════════════════════════════════════════════════
# btc_mr_l2: BTC Mean-Reversion with ADX Trend Filter
#
#   Key insight from testing: MR works in bull/neutral (2/3 regimes positive)
#   but gets crushed in trending markets.
#
#   Fix: Only trade when ADX < 25 (non-trending / weak trend).
#   When ADX 20-25 (mild trend), use tighter z-score thresholds.
#   When ADX > 25 (strong trend), stay flat.
# ═══════════════════════════════════════════════════════════════════════════════

def signal_btc_mr_l2_adx(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup(window, 50):
        return BacktestSignal.flat()

    close = window["close"]
    high = window["high"]
    low = window["low"]

    # Z-score of close vs 20-bar SMA
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()

    current_close = close.iloc[-1]
    current_sma = sma20.iloc[-1]
    current_std = std20.iloc[-1]

    if pd.isna(current_sma) or pd.isna(current_std) or current_std == 0:
        return BacktestSignal.flat()

    z_score = (current_close - current_sma) / current_std

    # ADX trend filter
    adx, plus_di, minus_di = _compute_adx(high, low, close)
    current_adx = adx.iloc[-1]

    if pd.isna(current_adx):
        return BacktestSignal.flat()

    # ── Trend filter ───────────────────────────────────────────────────────
    # ADX < 20: range-bound → full MR signal strength
    # ADX 20-25: mild trend → tighter thresholds (only strong extremes)
    # ADX > 25: strong trend → NO MR TRADES

    if current_adx > 25:
        return BacktestSignal.flat()

    # Determine threshold based on ADX regime
    if current_adx < 20:
        z_threshold = 1.5  # normal threshold
        proba = 0.70
    else:
        z_threshold = 2.0  # tighter threshold in mild trend
        proba = 0.62

    # ── Directional bias ───────────────────────────────────────────────────
    # In mild uptrend, prefer long MR (buy dips); in mild downtrend, prefer short MR
    current_plus_di = plus_di.iloc[-1]
    current_minus_di = minus_di.iloc[-1]
    trend_bias = 0  # neutral
    if not pd.isna(current_plus_di) and not pd.isna(current_minus_di):
        if current_plus_di > current_minus_di * 1.3:
            trend_bias = 1   # mild uptrend → prefer longs
        elif current_minus_di > current_plus_di * 1.3:
            trend_bias = -1  # mild downtrend → prefer shorts

    # ── Signal generation ──────────────────────────────────────────────────
    if z_score < -z_threshold:
        # Oversold → mean-revert long
        if trend_bias >= 0:  # only long if trend isn't bearish
            return BacktestSignal(direction=1, proba_alpha=proba)
    elif z_score > z_threshold:
        # Overbought → mean-revert short
        if trend_bias <= 0:  # only short if trend isn't bullish
            return BacktestSignal(direction=-1, proba_alpha=proba)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# Signal registry
# ═══════════════════════════════════════════════════════════════════════════════

MEAN_REVERSION_SIGNALS = {
    "btc_mr_l2": signal_btc_mr_l2_adx,
}


def get_mean_reversion_signal(hypothesis_id: str):
    """Get the signal function for a MeanReversionAlpha hypothesis."""
    return MEAN_REVERSION_SIGNALS.get(hypothesis_id, signal_btc_mr_l2_adx)

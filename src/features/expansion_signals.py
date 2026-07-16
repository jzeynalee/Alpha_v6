"""
ExpansionAlpha Signal Functions — one DISTINCT signal per hypothesis.

Fixes the "Ghost Clone" bug where exp_001/002/003/vol_comp_l0 all used
the same vol_signal() function, producing identical backtest results.

Each function has the signature:
    signal_fn(symbol, window: pd.DataFrame, bar_index: int) -> BacktestSignal
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.signal_source import BacktestSignal


def _warmup(window: pd.DataFrame, min_bars: int = 30) -> bool:
    return len(window) >= min_bars


# ═══════════════════════════════════════════════════════════════════════════════
# exp_001: ATR Compression Breakout
#   "ATR at N-period low → expect expansion. Enter on breakout of compression
#    range with volume confirmation."
#   Distinct logic: ATR compression + volume spike + price range breakout
# ═══════════════════════════════════════════════════════════════════════════════

def signal_exp_001_atr_breakout(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup(window, 30):
        return BacktestSignal.flat()

    close = window["close"]
    high = window["high"]
    low = window["low"]
    volume = window["volume"]

    # ATR compression: current ATR < 0.7 * 20-period average ATR
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_ma20 = atr.rolling(20).mean()

    current_atr = atr.iloc[-1]
    current_atr_ma = atr_ma20.iloc[-1]

    if pd.isna(current_atr) or pd.isna(current_atr_ma) or current_atr_ma == 0:
        return BacktestSignal.flat()

    # Compression condition
    compressed = current_atr < 0.7 * current_atr_ma
    if not compressed:
        return BacktestSignal.flat()

    # Volume confirmation: current volume > 1.5x 20-bar average
    vol_ma20 = volume.rolling(20).mean().iloc[-1]
    if pd.isna(vol_ma20) or vol_ma20 == 0:
        return BacktestSignal.flat()
    volume_confirmed = volume.iloc[-1] > 1.5 * vol_ma20

    if not volume_confirmed:
        return BacktestSignal.flat()

    # Breakout: close breaks above recent range high (compression ceiling)
    range_high = high.iloc[-21:-1].max()
    range_low = low.iloc[-21:-1].min()

    if close.iloc[-1] > range_high:
        return BacktestSignal(direction=1, proba_alpha=0.68)
    elif close.iloc[-1] < range_low:
        return BacktestSignal(direction=-1, proba_alpha=0.68)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# exp_002: Bollinger Squeeze with Entropy Filter
#   "BB width at percentile low + low entropy → high-confidence expansion.
#    Direction from regime context."
#   Distinct logic: Bollinger Band width percentile + entropy (close
#   autocorrelation) + regime-aware direction
# ═══════════════════════════════════════════════════════════════════════════════

def signal_exp_002_bollinger_entropy(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup(window, 50):
        return BacktestSignal.flat()

    close = window["close"]
    high = window["high"]
    low = window["low"]

    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = sma20 + 2 * std20
    lower = sma20 - 2 * std20
    bb_width = (upper - lower) / sma20  # normalized width

    current_width = bb_width.iloc[-1]
    if pd.isna(current_width):
        return BacktestSignal.flat()

    # BB squeeze: width below 35th percentile of last 100 bars (relaxed from 20)
    # Use rolling rank for speed instead of apply(lambda)
    width_rank = bb_width.rolling(100, min_periods=50).rank(pct=True).iloc[-1]
    if pd.isna(width_rank) or width_rank > 0.35:
        return BacktestSignal.flat()

    # Entropy filter: relaxed from 0.10 to 0.03
    returns = close.pct_change().dropna()
    if len(returns) < 20:
        return BacktestSignal.flat()
    autocorr = returns.iloc[-20:].autocorr(lag=1)
    if pd.isna(autocorr):
        autocorr = 0
    if abs(autocorr) < 0.03:
        return BacktestSignal.flat()  # too noisy, skip

    # Direction from 50-bar momentum context
    sma50 = close.rolling(50).mean()
    current_sma50 = sma50.iloc[-1]
    if pd.isna(current_sma50):
        return BacktestSignal.flat()

    # Breakout direction confirmation
    range_high = high.iloc[-21:-1].max()
    range_low = low.iloc[-21:-1].min()
    trend_up = close.iloc[-1] > sma50.iloc[-1]

    if close.iloc[-1] > range_high:
        direction = 1 if trend_up else -1  # fade if against trend
        return BacktestSignal(direction=direction, proba_alpha=0.65)
    elif close.iloc[-1] < range_low:
        direction = -1 if not trend_up else 1
        return BacktestSignal(direction=direction, proba_alpha=0.65)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# exp_003: Fractal Dimension Regime Switch
#   "FD crossing threshold → trending ↔ mean-reverting regime change."
#   Distinct logic: approximate fractal dimension via Higuchi-like method
#   using range/step ratio; FD < 0.4 = trending, FD > 0.6 = mean-reverting
# ═══════════════════════════════════════════════════════════════════════════════

def _approx_fractal_dimension(close: pd.Series, lookback: int = 50) -> float:
    """Approximate fractal dimension using range/variance ratio."""
    if len(close) < lookback:
        return 0.5
    window = close.iloc[-lookback:]
    # Range over period
    price_range = window.max() - window.min()
    if price_range == 0:
        return 0.0
    # Sum of absolute step sizes
    steps = window.diff().abs().sum()
    if steps == 0:
        return 0.0
    # FD ≈ log(N) / log(N * L / sum_steps)  (simplified Higuchi)
    N = float(lookback)
    fd = np.log(N) / np.log(N * price_range / max(steps, 1e-12))
    return float(np.clip(fd, 0.0, 1.0))


def signal_exp_003_fractal_dim(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup(window, 60):
        return BacktestSignal.flat()

    close = window["close"]
    high = window["high"]
    low = window["low"]

    # Compute fractal dimension (reduced lookback 50→30 for more signals)
    fd = _approx_fractal_dimension(close, lookback=30)
    fd_prev = _approx_fractal_dimension(close.iloc[:-1], lookback=30)

    # Regime switch detection (relaxed: 0.45/0.55 → 0.40/0.60)
    was_trending = fd_prev < 0.40
    is_mean_reverting = fd > 0.60
    was_mean_reverting = fd_prev > 0.60
    is_trending = fd < 0.40

    # Switch: trending → mean-reverting → fade the move
    if was_trending and is_mean_reverting:
        # Recent direction for fade
        mom_5 = close.iloc[-1] - close.iloc[-6]
        direction = -1 if mom_5 > 0 else 1
        return BacktestSignal(direction=direction, proba_alpha=0.62)

    # Switch: mean-reverting → trending → follow the breakout
    if was_mean_reverting and is_trending:
        range_high = high.iloc[-21:-1].max()
        range_low = low.iloc[-21:-1].min()
        if close.iloc[-1] > range_high:
            return BacktestSignal(direction=1, proba_alpha=0.64)
        elif close.iloc[-1] < range_low:
            return BacktestSignal(direction=-1, proba_alpha=0.64)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# vol_comp_l0: Volatility Compression
#   "Low volatility periods predict expansion."
#   Distinct logic: simple Parkinson vol percentile + breakout entry,
#   simpler than the other three (no entropy, no FD, just vol compression)
# ═══════════════════════════════════════════════════════════════════════════════

def signal_vol_comp_l0(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup(window, 50):
        return BacktestSignal.flat()

    high = window["high"]
    low = window["low"]
    close = window["close"]

    # Parkinson volatility estimator: sqrt(1/(4N*ln2) * sum(ln(H/L)^2))
    log_hl = np.log(high / low)
    parkinson = np.sqrt((log_hl ** 2).rolling(20).mean() / (4 * np.log(2)))

    current_park = parkinson.iloc[-1]
    if pd.isna(current_park) or current_park == 0:
        return BacktestSignal.flat()

    # Volatility percentile: is current vol in bottom 20%? (rank-based, fast)
    vol_rank = parkinson.rolling(100, min_periods=30).rank(pct=True).iloc[-1]

    if pd.isna(vol_rank) or vol_rank > 0.20:
        return BacktestSignal.flat()

    # Enter on breakout from compression range
    range_high = high.iloc[-21:-1].max()
    range_low = low.iloc[-21:-1].min()

    # Add momentum filter: only trade if there's actually a breakout
    if close.iloc[-1] > range_high * 1.002:  # 0.2% buffer to avoid noise
        return BacktestSignal(direction=1, proba_alpha=0.63)
    elif close.iloc[-1] < range_low * 0.998:
        return BacktestSignal(direction=-1, proba_alpha=0.63)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# Signal registry
# ═══════════════════════════════════════════════════════════════════════════════

EXPANSION_SIGNALS = {
    "exp_001": signal_exp_001_atr_breakout,
    "exp_002": signal_exp_002_bollinger_entropy,
    "exp_003": signal_exp_003_fractal_dim,
    "vol_comp_l0": signal_vol_comp_l0,
}


def get_expansion_signal(hypothesis_id: str):
    """Get the signal function for an ExpansionAlpha hypothesis."""
    return EXPANSION_SIGNALS.get(hypothesis_id)

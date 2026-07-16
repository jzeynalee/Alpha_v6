"""
PositioningAlpha Signal Functions — one per hypothesis in Program A.

Each function has the signature required by the backtest engine:
    signal_fn(symbol, window: pd.DataFrame, bar_index: int) -> BacktestSignal

The window DataFrame is expected to be enriched with OI and funding columns
via src.features.positioning_enricher.enrich_ohlcv().

Required columns (beyond OHLCV):
  - sum_open_interest, oi_delta, oi_delta_ma_20, oi_percentile
  - funding_rate, funding_zscore, funding_accel, funding_percentile
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.signal_source import BacktestSignal


def _warmup_check(window: pd.DataFrame, min_bars: int = 30) -> bool:
    """Check if we have enough bars and required columns."""
    return len(window) >= min_bars


# ═══════════════════════════════════════════════════════════════════════════════
# pos_001: OI Expansion Breakout
#   "Rising OI + rising price = trend confirmation"
#   Signal: OI expanding faster than 20-period average AND price breaks N-bar high
# ═══════════════════════════════════════════════════════════════════════════════

def signal_pos_001_oi_expansion(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup_check(window, 30):
        return BacktestSignal.flat()

    close = window["close"]
    oi = window.get("sum_open_interest")
    oi_delta = window.get("oi_delta")
    oi_delta_ma = window.get("oi_delta_ma_20")

    if oi is None or oi_delta is None or oi_delta_ma is None:
        return BacktestSignal.flat()

    current_close = close.iloc[-1]
    current_oi_delta = oi_delta.iloc[-1]
    current_oi_delta_ma = oi_delta_ma.iloc[-1]

    if pd.isna(current_oi_delta) or pd.isna(current_oi_delta_ma):
        return BacktestSignal.flat()

    # OI expanding: delta_OI > mean(delta_OI, 20)  (just need positive expansion)
    oi_expanding = current_oi_delta > 0 and current_oi_delta > current_oi_delta_ma

    # Price breakout: close > max(high, 20 bars)
    high_20 = window["high"].iloc[-21:-1].max()  # exclude current bar
    price_breakout_up = current_close > high_20

    if oi_expanding and price_breakout_up:
        return BacktestSignal(direction=1, proba_alpha=0.72)

    # Short: OI expanding + price breakdown
    low_20 = window["low"].iloc[-21:-1].min()
    price_breakout_down = current_close < low_20

    if oi_expanding and price_breakout_down:
        return BacktestSignal(direction=-1, proba_alpha=0.72)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# pos_002: OI Divergence Reversal
#   "Price up + OI down = weakening trend"
#   Signal: price rising (close > SMA20) but OI falling (OI < SMA_OI_20)
# ═══════════════════════════════════════════════════════════════════════════════

def signal_pos_002_oi_divergence(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup_check(window, 30):
        return BacktestSignal.flat()

    close = window["close"]
    oi = window.get("sum_open_interest")
    oi_ma = window.get("oi_ma_20")

    if oi is None or oi_ma is None:
        return BacktestSignal.flat()

    close_sma20 = close.rolling(20).mean()

    current_close = close.iloc[-1]
    current_sma20 = close_sma20.iloc[-1]
    current_oi = oi.iloc[-1]
    current_oi_ma = oi_ma.iloc[-1]

    if pd.isna(current_sma20) or pd.isna(current_oi_ma):
        return BacktestSignal.flat()

    price_rising = current_close > current_sma20
    price_falling = current_close < current_sma20
    oi_falling = current_oi < current_oi_ma
    oi_rising = current_oi > current_oi_ma

    # Divergence: price up + OI down → positions closing → reversal short
    if price_rising and oi_falling:
        return BacktestSignal(direction=-1, proba_alpha=0.65)

    # Divergence: price down + OI up → accumulation → reversal long
    if price_falling and oi_rising:
        return BacktestSignal(direction=1, proba_alpha=0.65)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# pos_003: Funding Rate Acceleration
#   "2nd derivative of funding rate → squeeze conditions"
#   Signal: funding accelerating positive → crowded long → short
#           funding accelerating negative → crowded short → long
# ═══════════════════════════════════════════════════════════════════════════════

def signal_pos_003_funding_accel(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup_check(window, 50):
        return BacktestSignal.flat()

    funding_accel = window.get("funding_accel")
    if funding_accel is None:
        return BacktestSignal.flat()

    current_accel = funding_accel.iloc[-1]
    if pd.isna(current_accel):
        return BacktestSignal.flat()

    # Normalize acceleration by recent volatility
    accel_std = funding_accel.rolling(50).std().iloc[-1]
    if pd.isna(accel_std) or accel_std == 0:
        return BacktestSignal.flat()

    accel_z = current_accel / accel_std

    # Funding getting more expensive rapidly → crowded longs → short
    if accel_z > 1.0:
        return BacktestSignal(direction=-1, proba_alpha=0.62)

    # Funding getting cheaper rapidly → crowded shorts → long
    if accel_z < -1.0:
        return BacktestSignal(direction=1, proba_alpha=0.62)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# pos_004: Funding Divergence Cross-Asset
#   "BTC-ETH funding spread → relative value signal"
#   Signal: wide funding spread predicts convergence → pair trade
#
#   NOTE: This signal operates on a single symbol but uses pre-computed
#   cross-asset funding spread. The spread is computed during data enrichment
#   and stored as 'funding_spread_btc_eth' column.
# ═══════════════════════════════════════════════════════════════════════════════

def signal_pos_004_funding_divergence_cross(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup_check(window, 50):
        return BacktestSignal.flat()

    # This signal requires the funding spread to be pre-computed
    funding_spread = window.get("funding_spread_btc_eth")
    if funding_spread is None:
        return BacktestSignal.flat()

    current_spread = funding_spread.iloc[-1]
    if pd.isna(current_spread):
        return BacktestSignal.flat()

    spread_mean = funding_spread.rolling(100).mean().iloc[-1]
    spread_std = funding_spread.rolling(100).std().iloc[-1]

    if pd.isna(spread_mean) or pd.isna(spread_std) or spread_std == 0:
        return BacktestSignal.flat()

    spread_z = (current_spread - spread_mean) / spread_std

    # BTC funding much higher than ETH → BTC overpriced relative to ETH
    # Short BTC (if we're testing BTC) or Long ETH (if testing ETH)
    if abs(spread_z) > 2.0:
        # Direction depends on which side of the spread we're on
        if "BTC" in symbol.upper():
            direction = -1 if spread_z > 0 else 1
        else:
            direction = 1 if spread_z > 0 else -1
        return BacktestSignal(direction=direction, proba_alpha=0.63)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# pos_005: Liquidation Cascade Detector
#   "High OI + extreme funding + price near extremes"
#   Signal: OI > 90th percentile AND |funding| > 95th percentile
#           → anticipate cascade; direction from price momentum (contrarian)
# ═══════════════════════════════════════════════════════════════════════════════

def signal_pos_005_liquidation_cascade(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup_check(window, 50):
        return BacktestSignal.flat()

    oi_percentile = window.get("oi_percentile")
    funding_rate = window.get("funding_rate")

    if oi_percentile is None or funding_rate is None:
        return BacktestSignal.flat()

    current_oi_pct = oi_percentile.iloc[-1]
    current_funding = funding_rate.iloc[-1]

    if pd.isna(current_oi_pct) or pd.isna(current_funding):
        return BacktestSignal.flat()

    # Funding extreme check: |funding| above 95th percentile of abs values
    abs_funding = funding_rate.abs()
    funding_threshold = abs_funding.rolling(200).quantile(0.95).iloc[-1]

    if pd.isna(funding_threshold):
        return BacktestSignal.flat()

    oi_extreme = current_oi_pct > 80
    funding_extreme = abs(current_funding) > funding_threshold

    if oi_extreme and funding_extreme:
        # Contrarian: extreme positive funding + high OI → crowded longs → short
        if current_funding > 0:
            return BacktestSignal(direction=-1, proba_alpha=0.70)
        # Extreme negative funding + high OI → crowded shorts → long
        else:
            return BacktestSignal(direction=1, proba_alpha=0.70)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# funding_div_l0: Funding Divergence
#   "Funding rate extreme deviation from mean → mean-reversion"
#   Signal: funding z-score > 2.5 → short (overly positive → mean-revert)
#           funding z-score < -2.5 → long (overly negative → mean-revert)
#
#   NOTE: Originally intended as cross-exchange funding divergence.
#   Since we only have Binance data, this adapted version uses
#   statistical divergence from the rolling mean as a proxy.
# ═══════════════════════════════════════════════════════════════════════════════

def signal_funding_div_l0(symbol: str, window: pd.DataFrame, bar_index: int = 0) -> BacktestSignal:
    if not _warmup_check(window, 50):
        return BacktestSignal.flat()

    funding_z = window.get("funding_zscore")
    if funding_z is None:
        return BacktestSignal.flat()

    current_z = funding_z.iloc[-1]
    if pd.isna(current_z):
        return BacktestSignal.flat()

    # Extreme positive funding → mean-revert short
    if current_z > 2.0:
        return BacktestSignal(direction=-1, proba_alpha=0.58)

    # Extreme negative funding → mean-revert long
    if current_z < -2.0:
        return BacktestSignal(direction=1, proba_alpha=0.58)

    return BacktestSignal.flat()


# ═══════════════════════════════════════════════════════════════════════════════
# Signal registry: maps hypothesis_id → signal function
# ═══════════════════════════════════════════════════════════════════════════════

POSITIONING_SIGNALS = {
    "pos_001": signal_pos_001_oi_expansion,
    "pos_002": signal_pos_002_oi_divergence,
    "pos_003": signal_pos_003_funding_accel,
    "pos_004": signal_pos_004_funding_divergence_cross,
    "pos_005": signal_pos_005_liquidation_cascade,
    "funding_div_l0": signal_funding_div_l0,
}


def get_positioning_signal(hypothesis_id: str):
    """Get the signal function for a PositioningAlpha hypothesis."""
    return POSITIONING_SIGNALS.get(hypothesis_id)

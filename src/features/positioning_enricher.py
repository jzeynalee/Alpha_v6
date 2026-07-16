"""
Positioning Data Enricher — merges OI and funding data into OHLCV DataFrames.

Data sources (data/raw/v3_binance/):
  - metrics/metrics_{symbol}.csv  — OI at 5-min intervals
  - funding/funding_{symbol}.csv  — funding rate at 8h intervals
  - fundingRate/fundingRate_{symbol}.csv — additional funding rate data

Usage:
    from src.features.positioning_enricher import enrich_ohlcv
    enriched = enrich_ohlcv(ohlcv_df, symbol="BTCUSDT")
    # enriched now has: sum_open_interest, oi_value, funding_rate, ls_ratio, taker_vol_ratio
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Path to v3_binance data
_V3_BINANCE = Path("data/raw/v3_binance")

# Cache loaded data to avoid repeated disk reads
_data_cache: dict = {}


def _load_csv(path: Path) -> Optional[pd.DataFrame]:
    """Load a CSV, set datetime index from unix timestamp."""
    if not path.exists():
        logger.warning("File not found: %s", path)
        return None
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.set_index("datetime").drop(columns=["timestamp"])
    df = df.sort_index()
    return df


def load_oi(symbol: str) -> Optional[pd.DataFrame]:
    """Load Open Interest metrics for a symbol."""
    cache_key = f"oi_{symbol}"
    if cache_key in _data_cache:
        return _data_cache[cache_key].copy()

    path = _V3_BINANCE / "metrics" / f"metrics_{symbol.lower()}.csv"
    df = _load_csv(path)
    if df is not None:
        # Keep only OI-relevant columns, drop symbol column
        cols = [c for c in ["sum_open_interest", "sum_open_interest_value",
                             "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]
                if c in df.columns]
        df = df[cols]
        _data_cache[cache_key] = df
        logger.info("Loaded OI data for %s: %d rows", symbol, len(df))
    return df.copy() if df is not None else None


def load_funding(symbol: str) -> Optional[pd.DataFrame]:
    """Load funding rate data for a symbol (combines both funding and fundingRate)."""
    cache_key = f"funding_{symbol}"
    if cache_key in _data_cache:
        return _data_cache[cache_key].copy()

    sym_lower = symbol.lower()
    dfs = []

    # Primary funding data (2020-2026, 8h intervals)
    path1 = _V3_BINANCE / "funding" / f"funding_{sym_lower}.csv"
    df1 = _load_csv(path1)
    if df1 is not None:
        df1.columns = ["funding_rate"]
        dfs.append(df1)

    # Secondary funding rate data (2023-2026, 8h intervals, more precise)
    path2 = _V3_BINANCE / "fundingRate" / f"fundingRate_{sym_lower}.csv"
    df2 = _load_csv(path2)
    if df2 is not None:
        df2.columns = ["funding_rate"]
        dfs.append(df2)

    if not dfs:
        return None

    # Combine: use secondary data (more recent/precise) where available,
    # fall back to primary
    if len(dfs) == 1:
        result = dfs[0]
    else:
        result = dfs[1].combine_first(dfs[0])

    result = result.sort_index()
    result = result[~result.index.duplicated(keep="last")]
    _data_cache[cache_key] = result
    logger.info("Loaded funding data for %s: %d rows", symbol, len(result))
    return result.copy()


def enrich_ohlcv(
    ohlcv: pd.DataFrame,
    symbol: str,
    load_oi_data: bool = True,
    load_funding_data: bool = True,
) -> pd.DataFrame:
    """
    Enrich an OHLCV DataFrame with OI and funding rate data.

    Parameters
    ----------
    ohlcv : pd.DataFrame
        Must have a datetime index or a 'timestamp' column.
    symbol : str
        e.g. "BTCUSDT", "ETHUSDT"
    load_oi_data : bool
    load_funding_data : bool

    Returns
    -------
    pd.DataFrame with additional columns:
        sum_open_interest, oi_value, oi_delta_5, oi_pct_change,
        funding_rate, funding_zscore, ls_ratio, taker_vol_ratio
    """
    # ── Ensure datetime index ───────────────────────────────────────────────
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.copy()
        ohlcv["datetime"] = pd.to_datetime(ohlcv["timestamp"])
        ohlcv = ohlcv.set_index("datetime")
        ohlcv = ohlcv.drop(columns=["timestamp"])
    elif not isinstance(ohlcv.index, pd.DatetimeIndex):
        # Try to convert index
        ohlcv = ohlcv.copy()
        ohlcv.index = pd.to_datetime(ohlcv.index)

    ohlcv = ohlcv.sort_index()

    # Fix: DatasetRegistry stores Unix seconds as datetime64[ns], resulting
    # in 1970 timestamps. Detect and correct (e.g. 1.64e9 ns = 1.64s → 2022).
    if isinstance(ohlcv.index, pd.DatetimeIndex) and len(ohlcv) > 0:
        if ohlcv.index[0].year < 2000:
            corrected = pd.to_datetime(ohlcv.index.astype("int64"), unit="s")
            ohlcv.index = corrected
            logger.info("Corrected OHLCV timestamps (seconds-as-ns → proper datetimes)")

    # ── Merge OI data ───────────────────────────────────────────────────────
    if load_oi_data:
        oi_df = load_oi(symbol)
        if oi_df is not None:
            # OI is 5-min data; resample to the OHLCV timeframe by forward-fill
            # then reindex to match OHLCV index (nearest forward or backward)
            oi_resampled = oi_df.reindex(ohlcv.index, method="ffill")
            for col in oi_resampled.columns:
                ohlcv[col] = oi_resampled[col]

            # Compute derived OI features
            if "sum_open_interest" in ohlcv.columns:
                ohlcv["oi_delta"] = ohlcv["sum_open_interest"].diff()
                ohlcv["oi_delta_pct"] = ohlcv["sum_open_interest"].pct_change()
                ohlcv["oi_ma_20"] = ohlcv["sum_open_interest"].rolling(20).mean()
                ohlcv["oi_delta_ma_20"] = ohlcv["oi_delta"].rolling(20).mean()
                ohlcv["oi_zscore_20"] = (
                    (ohlcv["sum_open_interest"] - ohlcv["oi_ma_20"])
                    / ohlcv["sum_open_interest"].rolling(20).std().clip(lower=1e-9)
                )
                # OI percentile (rolling 100-bar lookback)
                ohlcv["oi_percentile"] = (
                    ohlcv["sum_open_interest"]
                    .rolling(100)
                    .apply(lambda x: (x.iloc[-1] > x.iloc[:-1]).mean() * 100, raw=False)
                )

    # ── Merge funding data ──────────────────────────────────────────────────
    if load_funding_data:
        fund_df = load_funding(symbol)
        if fund_df is not None:
            # Forward-fill funding rate (8h data) to match OHLCV timestamps
            fund_resampled = fund_df.reindex(ohlcv.index, method="ffill")
            ohlcv["funding_rate"] = fund_resampled["funding_rate"]

            # Derived funding features
            if "funding_rate" in ohlcv.columns:
                ohlcv["funding_ma_100"] = ohlcv["funding_rate"].rolling(100).mean()
                ohlcv["funding_std_100"] = ohlcv["funding_rate"].rolling(100).std().clip(lower=1e-9)
                ohlcv["funding_zscore"] = (
                    (ohlcv["funding_rate"] - ohlcv["funding_ma_100"])
                    / ohlcv["funding_std_100"]
                )
                # Funding rate acceleration (2nd derivative)
                ohlcv["funding_delta"] = ohlcv["funding_rate"].diff()
                ohlcv["funding_accel"] = ohlcv["funding_delta"].diff()
                # Funding rate percentile
                ohlcv["funding_percentile"] = (
                    ohlcv["funding_rate"]
                    .rolling(100)
                    .apply(lambda x: (abs(x.iloc[-1]) < abs(x.iloc[:-1])).mean() * 100, raw=False)
                )

    return ohlcv


def load_cross_asset_funding(symbols: list = None) -> dict:
    """Load funding data for multiple symbols for cross-asset comparison."""
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT"]
    result = {}
    for sym in symbols:
        fund_df = load_funding(sym)
        if fund_df is not None:
            result[sym] = fund_df
    return result


def clear_cache():
    """Clear the data cache (useful for testing)."""
    _data_cache.clear()

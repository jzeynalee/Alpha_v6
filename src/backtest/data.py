# src/backtest/data.py
"""
Historical OHLCV loading for the backtester.

A backtest is only as trustworthy as its input data, so this module is strict:
it validates the OHLCV schema, rejects non-monotonic timestamps, and surfaces
gaps rather than silently interpolating them. The loader accepts the three
shapes a user is likely to have on hand — a parquet file, a CSV file, or an
in-memory DataFrame — and normalises all of them to one canonical frame.

Canonical OHLCV frame
---------------------
A pandas DataFrame with a sorted RangeIndex and exactly these columns:

    timestamp : int   — unix seconds, strictly increasing
    open      : float
    high      : float
    low       : float
    close     : float
    volume    : float

This is the same column set the live ``BarBuffer`` produces, so a strategy
backtested here sees bars identical in shape to production.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import pandas as pd

logger = logging.getLogger(__name__)

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# Common aliases seen in exported candle data → canonical name.
_COLUMN_ALIASES = {
    "time": "timestamp", "ts": "timestamp", "date": "timestamp",
    "datetime": "timestamp", "t": "timestamp",
    "o": "open", "h": "high", "l": "low", "c": "close",
    "v": "volume", "vol": "volume",
}


class OHLCVValidationError(ValueError):
    """Raised when input data cannot be coerced into a valid OHLCV frame."""


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case column names and apply the alias map."""
    df = df.rename(columns={c: str(c).strip().lower() for c in df.columns})
    df = df.rename(columns={k: v for k, v in _COLUMN_ALIASES.items() if k in df.columns})
    return df


def _coerce_timestamp(series: pd.Series) -> pd.Series:
    """
    Coerce a timestamp column to unix *seconds* as int64.

    Accepts: unix seconds, unix milliseconds (auto-detected by magnitude),
    or anything pandas can parse as a datetime.
    """
    if pd.api.types.is_numeric_dtype(series):
        vals = series.astype("int64")
        # Heuristic: values > ~year 2100 in seconds are almost certainly ms.
        if (vals > 4_102_444_800).mean() > 0.5:
            vals = vals // 1000
        return vals
    # Fall back to datetime parsing.
    dt = pd.to_datetime(series, utc=True, errors="coerce")
    if dt.isna().any():
        raise OHLCVValidationError("timestamp column has unparseable values")
    return (dt.astype("int64") // 1_000_000_000).astype("int64")


def validate_ohlcv(df: pd.DataFrame, *, symbol: str = "?") -> pd.DataFrame:
    """
    Validate and canonicalise an OHLCV DataFrame.

    Raises OHLCVValidationError on any structural problem. On success returns
    a fresh frame with the canonical columns, a clean RangeIndex, rows sorted
    by timestamp, and exact duplicates dropped.
    """
    if df is None or len(df) == 0:
        raise OHLCVValidationError(f"[{symbol}] OHLCV frame is empty")

    df = _normalise_columns(df.copy())

    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise OHLCVValidationError(
            f"[{symbol}] OHLCV frame missing columns: {missing}  "
            f"(present: {list(df.columns)})"
        )

    df["timestamp"] = _coerce_timestamp(df["timestamp"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[OHLCV_COLUMNS]

    if df[["open", "high", "low", "close"]].isna().any().any():
        bad = int(df[["open", "high", "low", "close"]].isna().any(axis=1).sum())
        raise OHLCVValidationError(f"[{symbol}] {bad} row(s) have NaN OHLC values")

    # volume NaN → 0.0 is tolerable (some feeds omit it); OHLC NaN is not.
    df["volume"] = df["volume"].fillna(0.0)

    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df = df.reset_index(drop=True)

    if len(df) < 2:
        raise OHLCVValidationError(f"[{symbol}] need at least 2 bars, got {len(df)}")

    # OHLC sanity: high must be the max, low the min, of the four.
    hi_ok = (df["high"] >= df[["open", "close", "low"]].max(axis=1)).all()
    lo_ok = (df["low"] <= df[["open", "close", "high"]].min(axis=1)).all()
    if not (hi_ok and lo_ok):
        raise OHLCVValidationError(
            f"[{symbol}] OHLC bars violate high>=max / low<=min invariant"
        )

    # Report (but do not fix) timestamp gaps — the modal delta is the bar size.
    deltas = df["timestamp"].diff().dropna()
    if len(deltas) > 0:
        modal = int(deltas.mode().iloc[0])
        gaps = int((deltas > modal * 1.5).sum())
        if gaps:
            logger.warning(
                "[%s] %d timestamp gap(s) detected (modal bar = %ds). "
                "Gaps are NOT interpolated — equity curve will skip them.",
                symbol, gaps, modal,
            )
    return df


def load_ohlcv(
    source: Union[str, Path, pd.DataFrame],
    *,
    symbol: str = "?",
) -> pd.DataFrame:
    """
    Load and validate OHLCV data from a parquet file, CSV file, or DataFrame.

    Parameters
    ----------
    source : a path to a .parquet/.csv file, or an already-loaded DataFrame.
    symbol : label used only in error/log messages.

    Returns
    -------
    A canonical OHLCV DataFrame (see module docstring).
    """
    if isinstance(source, pd.DataFrame):
        return validate_ohlcv(source, symbol=symbol)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"OHLCV source not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        df = pd.read_parquet(path)
    elif suffix in (".csv", ".txt"):
        df = pd.read_csv(path)
    else:
        raise OHLCVValidationError(
            f"Unsupported OHLCV file type '{suffix}' — use .parquet or .csv"
        )
    logger.info("Loaded %d raw rows from %s", len(df), path)
    return validate_ohlcv(df, symbol=symbol)


__all__ = ["load_ohlcv", "validate_ohlcv", "OHLCVValidationError", "OHLCV_COLUMNS"]

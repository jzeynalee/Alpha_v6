# src/core/dataset_registry.py
"""
Dataset Registry — centralized data access layer (Research Platform v2).

**No module should ever write ``Path("data/raw")`` again.**

Every module asks the registry:

    from src.core.dataset_registry import registry
    df = registry.get_ohlcv(exchange="binance", symbol="BTCUSDT", timeframe="15m")

The registry is the single source of truth for:
  - Where datasets live on disk
  - What symbols, timeframes, and exchanges are available
  - File naming conventions (ohlcv_{symbol_lower}_{timeframe}.csv)
  - Data versioning (v1, v2, v3_binance, etc.)

Design
------
- Scans the data directory tree on first access, builds an inventory.
- Supports multiple exchanges (binance, lbank, nobitex) and data versions.
- ``dataset_metadata.json`` files in each version directory provide hints.
- Falls back to convention-based discovery if metadata is missing.
- Thread-safe reads; writes go through the factory modules (backfill scripts).

Usage
-----
    from src.core.dataset_registry import DatasetRegistry, registry

    # List all available datasets
    for ds in registry.list_datasets():
        print(ds.exchange, ds.symbol, ds.timeframe, ds.path)

    # Load OHLCV data
    df = registry.get_ohlcv("binance", "BTCUSDT", "15m")

    # Check what's available
    symbols = registry.list_symbols("binance")
    timeframes = registry.list_timeframes("binance", "BTCUSDT")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.core.paths import _base as _data_base

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Dataset Descriptor
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DatasetInfo:
    """Descriptor for one discovered dataset on disk."""
    exchange: str           # "binance", "lbank", "nobitex"
    symbol: str             # "BTCUSDT", "ETHUSDT"
    timeframe: str          # "5m", "15m", "1h", "4h", "1d"
    path: Path              # Absolute path to the CSV file
    data_version: str = ""  # e.g. "v3_binance", "v2"
    rows: int = 0           # Approximate row count (from metadata)
    date_range: Tuple[str, str] = ("", "")  # (first_ts, last_ts) if known

    @property
    def key(self) -> str:
        """Unique key: exchange/symbol/timeframe."""
        return f"{self.exchange}/{self.symbol}/{self.timeframe}"

    def __repr__(self) -> str:
        return (
            f"DatasetInfo({self.key}, rows={self.rows}, "
            f"version={self.data_version})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  Dataset Registry
# ═══════════════════════════════════════════════════════════════════════════════

class DatasetRegistry:
    """
    Centralized registry of all market datasets on disk.

    Scans ``data/raw/`` recursively, indexing every OHLCV CSV file
    with known naming conventions. Thread-safe for reads.
    """

    def __init__(self, data_root: Optional[Path] = None) -> None:
        self._data_root = data_root or _data_base() / "raw"
        self._datasets: Dict[str, DatasetInfo] = {}
        self._by_exchange: Dict[str, List[DatasetInfo]] = {}
        self._scanned = False

    # ── Discovery ──────────────────────────────────────────────────────────────

    def scan(self, force: bool = False) -> int:
        """
        Scan the data root directory and index all discovered datasets.

        Returns the number of datasets found.
        Call once at startup; subsequent calls are no-ops unless ``force=True``.
        """
        if self._scanned and not force:
            return len(self._datasets)

        self._datasets.clear()
        self._by_exchange.clear()

        if not self._data_root.exists():
            logger.warning("Data root does not exist: %s", self._data_root)
            self._scanned = True
            return 0

        # Walk all version directories under data/raw/
        for version_dir in sorted(self._data_root.iterdir()):
            if not version_dir.is_dir():
                continue
            version_name = version_dir.name

            # First, try to read dataset_metadata.json for hints
            metadata = self._load_metadata(version_dir)

            # Discover CSV files
            count = self._scan_version_dir(version_dir, version_name, metadata)
            if count > 0:
                logger.info(
                    "DatasetRegistry: found %d datasets in %s",
                    count, version_dir,
                )

        self._scanned = True
        logger.info(
            "DatasetRegistry: scanned %d total datasets across %d exchanges.",
            len(self._datasets), len(self._by_exchange),
        )
        return len(self._datasets)

    def _load_metadata(self, version_dir: Path) -> dict:
        """Load dataset_metadata.json if present."""
        meta_file = version_dir / "dataset_metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _scan_version_dir(
        self, version_dir: Path, version_name: str, metadata: dict
    ) -> int:
        """Scan one version directory for OHLCV CSV files."""
        count = 0
        exchange = self._infer_exchange(version_name, metadata)

        # Known CSV naming patterns
        csv_patterns = [
            "ohlcv_{symbol_lower}_{timeframe}.csv",
        ]

        for csv_file in sorted(version_dir.glob("ohlcv_*.csv")):
            info = self._parse_filename(csv_file, exchange, version_name)
            if info is None:
                continue

            # Enrich with metadata if available
            enriched = self._enrich_from_metadata(info, metadata)
            self._datasets[enriched.key] = enriched
            self._by_exchange.setdefault(enriched.exchange, []).append(enriched)
            count += 1

        return count

    def _infer_exchange(self, version_name: str, metadata: dict) -> str:
        """Infer exchange name from version directory or metadata."""
        # Check metadata first
        source = metadata.get("data_source", "").lower()
        if "binance" in source:
            return "binance"
        if "lbank" in source:
            return "lbank"
        if "nobitex" in source:
            return "nobitex"

        # Fall back to directory naming convention
        if "binance" in version_name.lower():
            return "binance"
        if "lbank" in version_name.lower():
            return "lbank"
        if "nobitex" in version_name.lower():
            return "nobitex"

        # Legacy v1/v2 → assume nobitex
        if version_name in ("v1", "v2"):
            return "nobitex"

        return "unknown"

    def _parse_filename(
        self, csv_file: Path, exchange: str, version_name: str
    ) -> Optional[DatasetInfo]:
        """
        Parse a filename like ``ohlcv_btcusdt_15m.csv`` into a DatasetInfo.

        Expected format: ohlcv_{symbol_lower}_{timeframe}.csv
        Where timeframe is like "5m", "15m", "1h", "4h", "1d".
        """
        name = csv_file.stem  # remove .csv

        # Must start with ohlcv_
        if not name.startswith("ohlcv_"):
            return None

        # Legacy format: ohlcv_{symbol_lower}_{resolution}
        #   e.g. ohlcv_btcusdt_5, ohlcv_btcusdt_15, ohlcv_btcusdt_60
        # New format: ohlcv_{symbol_lower}_{timeframe}
        #   e.g. ohlcv_btcusdt_5m, ohlcv_btcusdt_15m, ohlcv_btcusdt_1h

        remainder = name[len("ohlcv_"):]  # e.g. "btcusdt_15m"

        # Split from the right on the last underscore
        parts = remainder.rsplit("_", 1)
        if len(parts) != 2:
            return None

        symbol_raw, timeframe_raw = parts
        symbol = symbol_raw.upper()

        # Normalize timeframe
        timeframe = self._normalize_timeframe(timeframe_raw)

        return DatasetInfo(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            path=csv_file.resolve(),
            data_version=version_name,
        )

    @staticmethod
    def _normalize_timeframe(raw: str) -> str:
        """Normalize timeframe strings to standard form: 5m, 15m, 1h, 4h, 1d."""
        raw = raw.strip().lower()
        # Legacy numeric-only: "5" → "5m", "15" → "15m", "60" → "1h"
        if raw.isdigit():
            n = int(raw)
            if n < 60:
                return f"{n}m"
            elif n == 60:
                return "1h"
            elif n == 240:
                return "4h"
            elif n == 1440:
                return "1d"
            else:
                return f"{n}m"
        # Already has unit: "5m", "15m", "1h", "4h", "1d"
        if raw.endswith("m") or raw.endswith("h") or raw.endswith("d"):
            return raw
        return raw

    def _enrich_from_metadata(
        self, info: DatasetInfo, metadata: dict
    ) -> DatasetInfo:
        """Add row counts and metadata hints."""
        rows = 0
        date_range = ("", "")

        # Check row_counts in metadata
        row_counts = metadata.get("row_counts", {})
        key_variants = [
            f"{info.symbol}_{info.timeframe}",
            f"{info.symbol}_{info.timeframe.replace('m', '').replace('h', '')}",
        ]
        for key in key_variants:
            if key in row_counts:
                rows = int(row_counts[key])
                break

        # Check files dict (v2 style)
        files = metadata.get("files", {})
        for file_key, file_info in files.items():
            if (
                file_info.get("symbol", "").upper() == info.symbol
                and str(file_info.get("resolution", "")) in (
                    info.timeframe.replace("m", "").replace("h", ""),
                    info.timeframe,
                )
            ):
                rows = file_info.get("rows", rows)
                break

        # Try to get date range from CSV (lazy — only for small files)
        # Omitted for performance; can be added as a separate method.

        return DatasetInfo(
            exchange=info.exchange,
            symbol=info.symbol,
            timeframe=info.timeframe,
            path=info.path,
            data_version=info.data_version,
            rows=rows,
            date_range=date_range,
        )

    # ── Query API ──────────────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        """
        Load OHLCV data for a specific exchange/symbol/timeframe.

        Returns a DataFrame with columns [timestamp, open, high, low, close, volume]
        or None if the dataset is not found.

        Parameters
        ----------
        exchange : str
            Exchange name: "binance", "lbank", "nobitex".
        symbol : str
            Trading pair: "BTCUSDT", "ETHUSDT".
        timeframe : str
            Timeframe: "5m", "15m", "1h", "4h", "1d".

        Returns
        -------
        pd.DataFrame or None
        """
        self.scan()  # ensure index is built
        timeframe = self._normalize_timeframe(timeframe)
        key = f"{exchange.lower()}/{symbol.upper()}/{timeframe}"

        info = self._datasets.get(key)
        if info is None:
            # Try fallback: search any exchange
            for k, v in self._datasets.items():
                if (
                    v.symbol == symbol.upper()
                    and v.timeframe == timeframe
                ):
                    info = v
                    logger.debug(
                        "DatasetRegistry: fallback from '%s' to '%s' for %s/%s",
                        exchange, v.exchange, symbol, timeframe,
                    )
                    break

        if info is None:
            available = [
                k for k in self._datasets
                if symbol.upper() in k
            ]
            logger.warning(
                "Dataset not found: %s. Available for %s: %s",
                key, symbol, available,
            )
            return None

        return self._load_csv(info.path)

    @staticmethod
    def _load_csv(path: Path) -> Optional[pd.DataFrame]:
        """Load an OHLCV CSV into a standardized DataFrame."""
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            logger.error("Failed to load %s: %s", path, exc)
            return None

        # Standardize column names
        df.columns = [c.strip().lower() for c in df.columns]

        # Identify timestamp column
        time_col = None
        for candidate in ("timestamp", "datetime", "date", "time", "open_time"):
            if candidate in df.columns:
                time_col = candidate
                break

        if time_col:
            df[time_col] = pd.to_datetime(df[time_col])
            df.set_index(time_col, inplace=True)

        # Standardize OHLCV column names
        col_map = {}
        for std_name in ("open", "high", "low", "close", "volume"):
            for actual in df.columns:
                if actual.lower() == std_name.lower():
                    col_map[actual] = std_name
                    break
        if col_map:
            df.rename(columns=col_map, inplace=True)

        # Ensure we have the core columns
        required = {"open", "high", "low", "close"}
        if not required.issubset(set(c.lower() for c in df.columns)):
            logger.warning(
                "CSV at %s missing required OHLC columns. Columns: %s",
                path, list(df.columns),
            )

        return df

    # ── Discovery / Inventory ──────────────────────────────────────────────────

    def list_datasets(self) -> List[DatasetInfo]:
        """Return all discovered datasets."""
        self.scan()
        return sorted(self._datasets.values(), key=lambda d: d.key)

    def list_exchanges(self) -> List[str]:
        """Return list of known exchanges."""
        self.scan()
        return sorted(self._by_exchange.keys())

    def list_symbols(self, exchange: Optional[str] = None) -> List[str]:
        """Return symbols for a given exchange, or all symbols across exchanges."""
        self.scan()
        if exchange:
            datasets = self._by_exchange.get(exchange.lower(), [])
        else:
            datasets = list(self._datasets.values())
        return sorted(set(d.symbol for d in datasets))

    def list_timeframes(
        self, exchange: Optional[str] = None, symbol: Optional[str] = None
    ) -> List[str]:
        """Return available timeframes, optionally filtered by exchange/symbol."""
        self.scan()
        if exchange:
            datasets = self._by_exchange.get(exchange.lower(), [])
        else:
            datasets = list(self._datasets.values())

        if symbol:
            datasets = [d for d in datasets if d.symbol == symbol.upper()]

        return sorted(set(d.timeframe for d in datasets), key=_timeframe_sort_key)

    def resolve(
        self,
        symbol: str,
        timeframe: str,
        exchange: Optional[str] = None,
    ) -> Optional[DatasetInfo]:
        """
        Find the best matching dataset for the given criteria.

        Tries exact exchange match first, then falls back to any exchange.
        """
        self.scan()
        timeframe = self._normalize_timeframe(timeframe)
        symbol = symbol.upper()

        if exchange:
            key = f"{exchange.lower()}/{symbol}/{timeframe}"
            if key in self._datasets:
                return self._datasets[key]

        # Fallback: any exchange
        for info in self._datasets.values():
            if info.symbol == symbol and info.timeframe == timeframe:
                return info

        return None

    # ── Inventory summary ──────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Return a structured inventory summary."""
        self.scan()
        exchanges_info = {}
        for ex, datasets in self._by_exchange.items():
            symbols = sorted(set(d.symbol for d in datasets))
            timeframes = sorted(set(d.timeframe for d in datasets), key=_timeframe_sort_key)
            versions = sorted(set(d.data_version for d in datasets))
            exchanges_info[ex] = {
                "n_datasets": len(datasets),
                "symbols": symbols,
                "timeframes": timeframes,
                "data_versions": versions,
            }
        return {
            "data_root": str(self._data_root),
            "n_datasets": len(self._datasets),
            "exchanges": exchanges_info,
        }

    def render_summary(self) -> str:
        """Human-readable inventory display."""
        s = self.summary()
        lines = [
            "═══ Dataset Registry ═══",
            f"  Data root: {s['data_root']}",
            f"  Total datasets: {s['n_datasets']}",
            f"  Exchanges: {len(s['exchanges'])}",
        ]
        for ex, info in s["exchanges"].items():
            lines.append(f"\n  [{ex}]")
            lines.append(f"    Datasets: {info['n_datasets']}")
            lines.append(f"    Symbols: {', '.join(info['symbols'][:10])}")
            lines.append(f"    Timeframes: {', '.join(info['timeframes'])}")
            lines.append(f"    Versions: {', '.join(info['data_versions'])}")
        return "\n".join(lines)


def _timeframe_sort_key(tf: str) -> int:
    """Sort key for timeframes: 5m < 15m < 1h < 4h < 1d."""
    if tf.endswith("m"):
        return int(tf[:-1])
    elif tf.endswith("h"):
        return int(tf[:-1]) * 60
    elif tf.endswith("d"):
        return int(tf[:-1]) * 1440
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
#  Module-level singleton
# ═══════════════════════════════════════════════════════════════════════════════

registry = DatasetRegistry()

__all__ = [
    "DatasetRegistry",
    "DatasetInfo",
    "registry",
]

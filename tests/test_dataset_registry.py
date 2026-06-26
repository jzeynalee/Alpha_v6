# tests/test_dataset_registry.py
"""Tests for Dataset Registry."""

from pathlib import Path
import tempfile

import pytest

from src.core.dataset_registry import (
    DatasetRegistry,
    DatasetInfo,
    registry,
)


class TestDatasetInfo:
    def test_create(self):
        info = DatasetInfo(
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="15m",
            path=Path("/data/ohlcv_btcusdt_15m.csv"),
            data_version="v3_binance",
        )
        assert info.key == "binance/BTCUSDT/15m"
        assert info.exchange == "binance"

    def test_repr(self):
        info = DatasetInfo(
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="5m",
            path=Path("/data/ohlcv_btcusdt_5m.csv"),
            rows=50000,
        )
        assert "50000" in repr(info)


class TestDatasetRegistry:
    def test_create(self):
        reg = DatasetRegistry()
        assert reg._scanned is False

    def test_scan_empty_dir(self, tmp_path):
        reg = DatasetRegistry(data_root=tmp_path)
        n = reg.scan()
        assert n == 0
        assert reg._scanned is True

    def test_normalize_timeframe(self):
        reg = DatasetRegistry()
        assert reg._normalize_timeframe("5m") == "5m"
        assert reg._normalize_timeframe("15m") == "15m"
        assert reg._normalize_timeframe("1h") == "1h"
        assert reg._normalize_timeframe("4h") == "4h"
        assert reg._normalize_timeframe("1d") == "1d"
        # Legacy numeric
        assert reg._normalize_timeframe("5") == "5m"
        assert reg._normalize_timeframe("15") == "15m"
        assert reg._normalize_timeframe("60") == "1h"
        assert reg._normalize_timeframe("240") == "4h"
        assert reg._normalize_timeframe("1440") == "1d"

    def test_scan_with_csv_files(self, tmp_path):
        """Create fake OHLCV files and verify scanning."""
        # Create directory structure
        v3 = tmp_path / "v3_binance"
        v3.mkdir()
        # Create metadata
        import json
        meta = {
            "data_source": "binance_perpetual_futures_public_cdn",
            "data_version": "v3_binance",
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "timeframes": ["5m", "15m"],
        }
        with open(v3 / "dataset_metadata.json", "w") as f:
            json.dump(meta, f)

        # Create CSV files (just headers)
        for symbol, tf in [("btcusdt", "15m"), ("ethusdt", "5m")]:
            path = v3 / f"ohlcv_{symbol}_{tf}.csv"
            path.write_text("timestamp,open,high,low,close,volume\n")

        reg = DatasetRegistry(data_root=tmp_path)
        n = reg.scan()
        assert n == 2

        # Query
        info = reg.resolve("BTCUSDT", "15m")
        assert info is not None
        assert info.exchange == "binance"

    def test_list_exchanges(self, tmp_path):
        v3 = tmp_path / "v3_binance"
        v3.mkdir()
        import json
        with open(v3 / "dataset_metadata.json", "w") as f:
            json.dump({"data_source": "binance"}, f)
        (v3 / "ohlcv_btcusdt_15m.csv").write_text("timestamp,open,high,low,close,volume\n")

        reg = DatasetRegistry(data_root=tmp_path)
        reg.scan()
        exchanges = reg.list_exchanges()
        assert "binance" in exchanges

    def test_list_symbols(self, tmp_path):
        v3 = tmp_path / "v3_binance"
        v3.mkdir()
        (v3 / "ohlcv_btcusdt_15m.csv").write_text("timestamp,open,high,low,close,volume\n")
        (v3 / "ohlcv_ethusdt_5m.csv").write_text("timestamp,open,high,low,close,volume\n")

        reg = DatasetRegistry(data_root=tmp_path)
        reg.scan()
        symbols = reg.list_symbols("binance")
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

    def test_list_timeframes(self, tmp_path):
        v3 = tmp_path / "v3_binance"
        v3.mkdir()
        (v3 / "ohlcv_btcusdt_15m.csv").write_text("timestamp,open,high,low,close,volume\n")
        (v3 / "ohlcv_btcusdt_5m.csv").write_text("timestamp,open,high,low,close,volume\n")

        reg = DatasetRegistry(data_root=tmp_path)
        reg.scan()
        tfs = reg.list_timeframes("binance", "BTCUSDT")
        assert "5m" in tfs
        assert "15m" in tfs

    def test_get_ohlcv_with_data(self, tmp_path):
        import pandas as pd
        v3 = tmp_path / "v3_binance"
        v3.mkdir()
        import json
        with open(v3 / "dataset_metadata.json", "w") as f:
            json.dump({"data_source": "binance"}, f)

        # Create actual OHLCV data
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="15min"),
            "open": range(100),
            "high": range(1, 101),
            "low": range(0, 100),
            "close": range(1, 101),
            "volume": [1000] * 100,
        })
        df.to_csv(v3 / "ohlcv_btcusdt_15m.csv", index=False)

        reg = DatasetRegistry(data_root=tmp_path)
        reg.scan()
        loaded = reg.get_ohlcv("binance", "BTCUSDT", "15m")
        assert loaded is not None
        assert len(loaded) == 100
        assert "open" in loaded.columns or "Open" in [c.lower() for c in loaded.columns]

    def test_summary(self, tmp_path):
        v3 = tmp_path / "v3_binance"
        v3.mkdir()
        (v3 / "ohlcv_btcusdt_15m.csv").write_text("timestamp,open,high,low,close,volume\n")

        reg = DatasetRegistry(data_root=tmp_path)
        reg.scan()
        s = reg.summary()
        assert s["n_datasets"] == 1

    def test_render_summary(self, tmp_path):
        v3 = tmp_path / "v3_binance"
        v3.mkdir()
        (v3 / "ohlcv_btcusdt_15m.csv").write_text("timestamp,open,high,low,close,volume\n")

        reg = DatasetRegistry(data_root=tmp_path)
        reg.scan()
        text = reg.render_summary()
        assert "Dataset Registry" in text

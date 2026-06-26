# src/backtest/__init__.py
"""
Alpha Factory V3 — strategy backtesting module.

An event-driven backtester that reuses production code for every decision
that affects strategy performance, and simulates only what cannot exist
without a live exchange:

  * RiskManager  — real position sizing, SL/TP, exposure & daily limits.
  * TradeJournal — real win-rate / profit-factor / Sharpe / drawdown metrics.
  * Simulated    — fills, fees, slippage, cash/equity (no exchange exists).

Quick start
-----------
    from src.backtest import BacktestEngine, BacktestConfig

    def sma_cross(symbol, window, bar_index):
        # window = all bars up to and including the current one
        if len(window) < 30:
            return 0
        fast = window["close"].iloc[-10:].mean()
        slow = window["close"].iloc[-30:].mean()
        return 1 if fast > slow else -1

    engine = BacktestEngine(sma_cross, BacktestConfig(initial_cash=10_000))
    result = engine.run("data/ohlcv/BTCUSDT_1h.parquet", symbol="BTCUSDT")
    print(result.render())

Backtesting the real pipeline
-----------------------------
    from src.backtest import BacktestEngine, AlphaFactorySignalSource
    from src.core.alpha_factory import AlphaFactory

    factory = AlphaFactory(config_path="src/config/alpha_factory_config.yml")
    engine  = BacktestEngine(AlphaFactorySignalSource(factory))
    result  = engine.run(df, symbol="BTCUSDT")

Public API
----------
    BacktestEngine            — the event loop.
    BacktestConfig            — run tuning (cash, fees, slippage, warmup…).
    BacktestResult            — structured outcome + metrics + export.
    BacktestSignal            — a strategy's per-bar decision.
    SignalSource              — the structural interface for a signal source.
    CallableSignalSource      — wrap any function as a signal source.
    AlphaFactorySignalSource  — drive the real six-layer pipeline.
    load_ohlcv                — validated OHLCV loader (parquet/csv/DataFrame).
"""

from .data import OHLCVValidationError, load_ohlcv, validate_ohlcv
from .engine import BacktestConfig, BacktestEngine
from .portfolio import EquityPoint, OpenPosition, Portfolio
from .result import BacktestResult
from .signal_source import (
    AlphaFactorySignalSource,
    BacktestSignal,
    CallableSignalSource,
    SignalSource,
)

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "BacktestSignal",
    "SignalSource",
    "CallableSignalSource",
    "AlphaFactorySignalSource",
    "load_ohlcv",
    "validate_ohlcv",
    "OHLCVValidationError",
    "Portfolio",
    "OpenPosition",
    "EquityPoint",
]


import pandas as pd
import numpy as np
from src.validation.event_study import EventStudy
from src.backtest.engine import BacktestEngine, BacktestConfig
from src.backtest.signal_source import CallableSignalSource, BacktestSignal

def get_baseline_signal(symbol, window, bar_index):
    if len(window) < 20: return BacktestSignal.flat()
    sma20 = window["close"].rolling(20).mean().iloc[-1]
    return BacktestSignal(direction=1) if window["close"].iloc[-1] > sma20 else BacktestSignal.flat()

def get_improved_signal(symbol, window, bar_index):
    from src.features.momentum_signals import signal_momentum_improved
    return signal_momentum_improved(symbol, window, bar_index)

def run_backtest(ohlcv, signal_fn, name):
    if "timestamp" not in ohlcv.columns:
        ohlcv = ohlcv.reset_index()
    config = BacktestConfig(initial_cash=10000, warmup_bars=100)
    engine = BacktestEngine(signal_source=signal_fn, config=config)
    result = engine.run(ohlcv)
    print(f"Strategy: {name:<20} | Profit Factor: {result.profit_factor:.3f} | Win Rate: {result.win_rate:.2%}")

def get_component_signals(name, symbol, window, bar_index):
    if len(window) < 100: return BacktestSignal.flat()
    
    close = window["close"]
    volume = window["volume"]
    atr = window.get("atr_percentile", pd.Series(0.5, index=window.index))
    
    # 1. Base Components
    sma10 = close.rolling(10).mean().iloc[-1]
    sma30 = close.rolling(30).mean().iloc[-1]
    roc5 = (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6]
    vol_median = volume.rolling(20).median().iloc[-1]
    vol_ok = volume.iloc[-1] > vol_median * 0.8
    
    # Alternative Regimes
    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma100 = close.rolling(100).mean().iloc[-1]
    
    # 2. Logic construction per name
    signal = 0
    # Core signal (Crossover + ROC + Vol)
    core_signal = 0
    if sma10 > sma30 and roc5 > 0 and vol_ok: core_signal = 1
    elif sma10 < sma30 and roc5 < 0 and vol_ok: core_signal = -1
    
    if core_signal == 0: return BacktestSignal.flat()

    if name == "Crossover+ROC+Vol":
        signal = core_signal
    elif name == "Regime:SMA50/100":
        if (core_signal == 1 and sma50 > sma100) or (core_signal == -1 and sma50 < sma100):
            signal = core_signal
    elif name == "Regime:SMA20/50":
        if (core_signal == 1 and sma20 > sma50) or (core_signal == -1 and sma20 < sma50):
            signal = core_signal
    elif name == "Regime:LowVol":
        if (core_signal == 1 and atr.iloc[-1] < 0.5) or (core_signal == -1 and atr.iloc[-1] < 0.5):
            signal = core_signal
        
    return BacktestSignal(direction=signal) if signal != 0 else BacktestSignal.flat()

def decompose_m002(symbol="BTCUSDT", timeframe="4h"):
    study = EventStudy(symbol, timeframe, max_bars=50000)
    ohlcv = study.load_data()
    ohlcv = study.compute_features(ohlcv)
    
    print(f"Auditing M002 Regime Filters for {symbol}/{timeframe}...")
    
    components = ["Crossover+ROC+Vol", "Regime:SMA50/100", "Regime:SMA20/50", "Regime:LowVol"]
    
    for comp in components:
        run_backtest(ohlcv, lambda s, w, b: get_component_signals(comp, s, w, b), comp)

if __name__ == "__main__":
    decompose_m002()

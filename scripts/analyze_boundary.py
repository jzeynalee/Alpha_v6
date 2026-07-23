import pandas as pd
import numpy as np
import logging
from src.core.dataset_registry import registry as data_registry
from src.features.positioning_enricher import enrich_ohlcv
from src.validation.event_study import EventStudy
from src.backtest.engine import BacktestEngine, BacktestConfig
from src.backtest.signal_source import CallableSignalSource, BacktestSignal

logging.basicConfig(level=logging.ERROR)

def run_backtest_simulation(ohlcv, trigger_fn, horizon=5):
    """Simple backtester to calculate Profit Factor of a trigger."""
    study = EventStudy("TEMP", "4h")
    # Generate events
    df = study.compute_features(ohlcv)
    events = trigger_fn(df)
    
    if events.sum() < 5:
        return 0.0, 0
        
    # Forward returns
    fwd_returns = []
    indices = df[events].index
    for idx in indices:
        pos = df.index.get_loc(idx)
        if pos + horizon < len(df):
            ret = (df['close'].iloc[pos + horizon] / df['close'].iloc[pos] - 1)
            fwd_returns.append(ret)
            
    if not fwd_returns:
        return 0.0, 0
        
    fwd_returns = np.array(fwd_returns)
    gross_wins = fwd_returns[fwd_returns > 0].sum()
    gross_losses = abs(fwd_returns[fwd_returns < 0].sum())
    
    pf = gross_wins / gross_losses if gross_losses > 0 else 1.0
    return pf, len(fwd_returns)

def sweep_m003():
    print("==================================================")
    print("SWEEPING M003 (Position Unwind) PARAMETERS")
    print("==================================================")
    
    assets = ["BTCUSDT", "ETHUSDT"]
    timeframes = ["15m", "1h", "4h"]
    lookbacks = [3, 5, 10]
    price_thresholds = [0.002, 0.005, 0.010]
    oi_thresholds = [-0.002, -0.005, -0.010]
    
    results = []
    for sym in assets:
        for tf in timeframes:
            ohlcv = data_registry.get_ohlcv("binance", sym, tf)
            if ohlcv is None: continue
            df_enriched = enrich_ohlcv(ohlcv, sym)
            
            for l in lookbacks:
                for pt in price_thresholds:
                    for ot in oi_thresholds:
                        # Price rise + OI drop (Short Reversal)
                        # Price drop + OI rise (Long Reversal)
                        trigger_fn = lambda df, l=l, pt=pt, ot=ot: (
                            ((df['close'].pct_change(l) > pt) & (df['sum_open_interest'].pct_change(l) < ot)) |
                            ((df['close'].pct_change(l) < -pt) & (df['sum_open_interest'].pct_change(l) > -ot))
                        )
                        pf, n = run_backtest_simulation(df_enriched, trigger_fn)
                        if pf > 1.05 and n >= 15:
                            results.append({
                                "Asset": sym, "Timeframe": tf, "Lookback": l,
                                "PriceThresh": pt, "OIThresh": ot, "PF": pf, "Trades": n
                            })
                            
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        print(df_res.sort_values(by="PF", ascending=False).head(15).to_string(index=False))
    else:
        print("No profitable M003 configurations found.")

def sweep_m004():
    print("\n==================================================")
    print("SWEEPING M004 (Funding Rotation) PARAMETERS")
    print("==================================================")
    
    assets = ["BTCUSDT", "ETHUSDT"]
    timeframes = ["15m", "1h", "4h"]
    funding_thresholds = [0.0002, 0.0005, 0.0010, 0.0015]
    
    results = []
    for sym in assets:
        for tf in timeframes:
            ohlcv = data_registry.get_ohlcv("binance", sym, tf)
            if ohlcv is None: continue
            df_enriched = enrich_ohlcv(ohlcv, sym)
            
            for ft in funding_thresholds:
                trigger_fn = lambda df, ft=ft: (df['funding_rate'] > ft) | (df['funding_rate'] < -ft)
                pf, n = run_backtest_simulation(df_enriched, trigger_fn)
                if pf > 1.05 and n >= 15:
                    results.append({
                        "Asset": sym, "Timeframe": tf, "FundingThresh": ft, "PF": pf, "Trades": n
                    })
                            
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        print(df_res.sort_values(by="PF", ascending=False).head(15).to_string(index=False))
    else:
        print("No profitable M004 configurations found.")

if __name__ == "__main__":
    sweep_m003()
    sweep_m004()

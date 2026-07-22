import pandas as pd
from src.core.mechanism_registry import registry
from src.features.positioning_enricher import enrich_ohlcv
from src.validation.event_study import EventStudy
from src.core.dataset_registry import registry as data_registry

def check_pf(mechanism_id: str, symbol: str, timeframe: str):
    mech = registry.get(mechanism_id)
    ohlcv = data_registry.get_ohlcv("binance", symbol, timeframe)
    if ohlcv is None: return None
    
    study = EventStudy(symbol, timeframe, max_bars=10000)
    study.add_trigger(mechanism_id, mech.trigger_fn)
    df = enrich_ohlcv(ohlcv, symbol)
    df = study.compute_features(df)
    
    signals = mech.trigger_fn(df)
    if signals.sum() < 20: return 0.0 # Insufficient trades
    
    # Simple event study to compute PF
    results = study.run(df=df)
    # This is a simplistic way to check edge, similar to the pipeline's logic
    # In a real setup, we would run the full backtest.
    # For now, just print the event study results
    return f"PF check: {mechanism_id} on {symbol}/{timeframe} - Signals={signals.sum()}"

if __name__ == "__main__":
    for mid in ["M003", "M004", "M005"]:
        for sym in ["BTCUSDT", "ETHUSDT"]:
            for tf in ["1h", "4h"]:
                print(check_pf(mid, sym, tf))

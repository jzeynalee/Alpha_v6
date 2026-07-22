import pandas as pd
from src.core.mechanism_registry import registry
from src.features.positioning_enricher import enrich_ohlcv
from src.validation.event_study import EventStudy
from src.core.dataset_registry import registry as data_registry

def analyze_mechanism_horizons(mechanism_id: str, symbol: str, timeframe: str):
    mech = registry.get(mechanism_id)
    ohlcv = data_registry.get_ohlcv("binance", symbol, timeframe)
    if ohlcv is None: return
    
    study = EventStudy(symbol, timeframe, max_bars=10000)
    study.add_trigger(mechanism_id, mech.trigger_fn)
    df = enrich_ohlcv(ohlcv, symbol)
    df = study.compute_features(df)
    
    # Run event study
    results = study.run(df=df)
    
    # Analyze horizons
    for res in results:
        print(f"--- {mechanism_id} | {symbol}/{timeframe} ---")
        for h in res.horizons:
            mean_ret = res.mean_return.get(h, 0.0) * 10000
            pf = 1.0 + (mean_ret / 100) # Simplistic PF proxy for diagnostic
            print(f"Horizon={h}: Mean_bp={mean_ret:.2f}, Est_PF={pf:.3f}")

if __name__ == "__main__":
    for mid in ["M003", "M004", "M005"]:
        for sym in ["BTCUSDT"]:
            for tf in ["4h"]:
                analyze_mechanism_horizons(mid, sym, tf)

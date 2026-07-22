import pandas as pd
from src.core.mechanism_registry import registry
from src.features.positioning_enricher import enrich_ohlcv
from src.validation.event_study import EventStudy

def verify_signals(mechanism_id: str, symbol: str = "BTCUSDT", timeframe: str = "4h"):
    mech = registry.get(mechanism_id)
    if not mech or not mech.trigger_fn:
        print(f"{mechanism_id}: No trigger function.")
        return

    study = EventStudy(symbol, timeframe, max_bars=1000)
    df = study.load_data()
    # Enrich data
    df = enrich_ohlcv(df, symbol)
    df = study.compute_features(df)
    
    try:
        signals = mech.trigger_fn(df)
        n_signals = signals.sum()
        print(f"{mechanism_id}: Generated {n_signals} signals on {symbol}/{timeframe}")
    except Exception as e:
        print(f"{mechanism_id}: Error generating signals: {e}")

if __name__ == "__main__":
    for mid in ["M003", "M004", "M005"]:
        verify_signals(mid)

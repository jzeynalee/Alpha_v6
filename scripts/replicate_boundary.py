import pandas as pd
import numpy as np
from scipy.stats import ttest_1samp
from src.features.mean_reversion_signals import signal_btc_mr_l2_adx
from src.validation.event_study import EventStudy

def bootstrap_ci(data, n_boot=1000, alpha=0.05):
    if len(data) < 2: return [0, 0]
    boot_means = [np.mean(np.random.choice(data, size=len(data), replace=True)) for _ in range(n_boot)]
    return np.percentile(boot_means, [alpha/2 * 100, (1 - alpha/2) * 100])

def cohens_d(group):
    return group.mean() / (group.std() + 1e-9)

def analyze_cross_asset(mechanism_id, boundary_frozen, symbol, timeframe="4h"):
    print(f"--- Running Cross-Asset Replication: {mechanism_id} | {symbol} | Frozen B01 ---")
    study = EventStudy(symbol, timeframe, max_bars=50000)
    ohlcv = study.load_data()
    ohlcv = study.compute_features(ohlcv)
    
    # 1. Generate signals
    signals = []
    for i in range(len(ohlcv)):
        window = ohlcv.iloc[:i+1]
        sig = signal_btc_mr_l2_adx(symbol, window, i)
        
        # Apply Frozen Boundary B01
        atr = window["atr_percentile"].iloc[-1]
        if not (boundary_frozen['atr_lower'] <= atr <= boundary_frozen['atr_upper']):
            signals.append(0)
        else:
            signals.append(sig.direction)
            
    ohlcv["signal"] = signals
    entries = ohlcv[ohlcv["signal"] != 0].copy()
    
    # 2. Measure Returns (bp)
    entries[f"fwd_5"] = (ohlcv["close"].shift(-5) / ohlcv["close"] - 1) * 10000
    
    # 3. Aggregate Diagnostics
    returns = entries[f"fwd_5"]
    if len(returns) < 10:
        print(f"Insufficient events: {len(returns)}")
        return
        
    ci = bootstrap_ci(returns)
    
    report = {
        "Events": len(entries),
        "Mean_bp": returns.mean(),
        "Win_Rate": (returns > 0).mean(),
        "Cohen_d": cohens_d(returns),
        "CI_Low": ci[0],
        "CI_High": ci[1],
        "p_value": ttest_1samp(returns, 0.0, alternative="greater")[1]
    }
    
    print(pd.DataFrame([report]).to_string(index=False))

if __name__ == "__main__":
    boundary_b01 = {
        "atr_lower": 0.345,
        "atr_upper": 0.608
    }
    
    for sym in ["ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]:
        analyze_cross_asset("M001", boundary_b01, sym)

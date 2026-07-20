import pandas as pd
import numpy as np
from scipy.stats import ttest_1samp
from src.features.mean_reversion_signals import signal_btc_mr_l2_adx
from src.validation.event_study import EventStudy

def bootstrap_ci(data, n_boot=1000, alpha=0.05):
    boot_means = [np.mean(np.random.choice(data, size=len(data), replace=True)) for _ in range(n_boot)]
    return np.percentile(boot_means, [alpha/2 * 100, (1 - alpha/2) * 100])

def cohens_d(group):
    # Standardized mean difference
    return group.mean() / (group.std() + 1e-9)

def analyze_boundary(mechanism_id, boundary_var, horizon=5, symbol="BTCUSDT", timeframe="4h"):
    study = EventStudy(symbol, timeframe, max_bars=50000)
    ohlcv = study.load_data()
    ohlcv = study.compute_features(ohlcv)
    
    # 1. Generate actual signals
    signals = []
    for i in range(len(ohlcv)):
        window = ohlcv.iloc[:i+1]
        sig = signal_btc_mr_l2_adx(symbol, window, i)
        signals.append(sig.direction)
    
    ohlcv["signal"] = signals
    entries = ohlcv[ohlcv["signal"] != 0].copy()
    
    # 2. Determine boundary variable
    if boundary_var == "atr":
        entries["boundary_val"] = entries["atr_percentile"]
    elif boundary_var == "volume":
        entries["boundary_val"] = entries["volume"].rank(pct=True)
    else:
        print(f"Unknown boundary variable: {boundary_var}")
        return
        
    # 3. Percentile-based bucketing
    entries["regime"] = pd.qcut(entries["boundary_val"], q=5, labels=["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"])
    
    # 4. Measure forward returns (in bp)
    entries[f"fwd_{horizon}"] = (ohlcv["close"].shift(-horizon) / ohlcv["close"] - 1) * 10000
    
    # 5. Aggregate with Rich Diagnostics
    results = []
    for regime, grp in entries.groupby("regime", observed=False):
        if len(grp) < 10: continue
        
        returns = grp[f"fwd_{horizon}"]
        ci = bootstrap_ci(returns)
        
        results.append({
            "Regime": regime,
            "Events": len(grp),
            "Mean_bp": returns.mean(),
            "Median_bp": returns.median(),
            "Win_Rate": (returns > 0).mean(),
            "Cohen_d": cohens_d(returns),
            "CI_Low": ci[0],
            "CI_High": ci[1],
            "p_value": ttest_1samp(returns, 0.0, alternative="greater")[1]
        })
        
    summary_df = pd.DataFrame(results)
    print(f"--- Boundary Analysis: {mechanism_id} | {boundary_var} | {symbol} ---")
    print(summary_df.to_string(index=False))

if __name__ == "__main__":
    for var in ["atr", "volume"]:
        analyze_boundary("M001", var, horizon=5, symbol="BTCUSDT")

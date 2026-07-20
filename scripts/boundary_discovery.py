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

def analyze_boundary_temporal(mechanism_id, boundary_var, buckets, horizon=5, symbol="BTCUSDT"):
    study = EventStudy(symbol, "4h", max_bars=50000)
    ohlcv = study.load_data()
    print(f"DEBUG: Columns: {ohlcv.columns}")
    print(f"DEBUG: Index: {ohlcv.index}")
    ohlcv = study.compute_features(ohlcv)
    
    # 1. Generate signals
    signals = []
    for i in range(len(ohlcv)):
        signals.append(signal_btc_mr_l2_adx(symbol, ohlcv.iloc[:i+1], i).direction)
    ohlcv["signal"] = signals
    
    # 2. Add Boundary Var
    if boundary_var == "atr":
        ohlcv["boundary_val"] = ohlcv["atr_percentile"]
    
    print(f"Data range: {ohlcv.index.min()} to {ohlcv.index.max()}")
    
    # 3. Temporal Split
    split_idx = int(len(ohlcv) * 0.7)
    train = ohlcv.iloc[:split_idx].copy()
    test = ohlcv.iloc[split_idx:].copy()
    
    # 4. Measure Returns
    def get_returns(df):
        entries = df[df["signal"] != 0].copy()
        entries[f"fwd_{horizon}"] = (df["close"].shift(-horizon) / df["close"] - 1) * 10000
        entries["regime"] = pd.qcut(entries["boundary_val"], q=5, duplicates="drop")
        return entries

    train_entries = get_returns(train)
    test_entries = get_returns(test)
    
    def report(df, name):
        results = []
        for regime, grp in df.groupby("regime", observed=False):
            if len(grp) < 10: continue
            returns = grp[f"fwd_{horizon}"]
            ci = bootstrap_ci(returns)
            results.append({
                "Regime": regime, "Events": len(grp), "Mean_bp": returns.mean(),
                "Win_Rate": (returns > 0).mean(), "Cohen_d": cohens_d(returns),
                "CI_Low": ci[0], "CI_High": ci[1]
            })
        print(f"--- {name} ---")
        print(pd.DataFrame(results).to_string(index=False))

    report(train_entries, "TRAIN (2022-2023)")
    report(test_entries, "TEST (2024-2026)")

if __name__ == "__main__":
    analyze_boundary_temporal("M001", "atr", [0, 0.2, 0.4, 0.6, 0.8, 1.0])

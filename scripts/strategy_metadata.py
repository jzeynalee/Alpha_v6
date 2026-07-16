"""
Strategy Metadata Registry — maps each hypothesis to its implementation details.

Used by regenerate_reports.py to produce consistent, complete documentation.
"""
from __future__ import annotations

STRATEGY_METADATA = {
    # ── MeanReversionAlpha ──────────────────────────────────────────────────
    "btc_mr_l2": {
        "signal_method": """
**Signal Logic**: Z-score mean-reversion with ADX trend filter.
- Compute z-score of close price vs 20-bar SMA: `z = (close - sma20) / std20`
- **ADX < 20** (range-bound): full signal, entry at |z| > 1.5, proba=0.70
- **ADX 20-25** (mild trend): tightened entry at |z| > 2.0, proba=0.62
- **ADX > 25** (strong trend): NO trades — mean-reversion gets crushed
- DI directional bias: prefer long MR in mild uptrends, short MR in mild downtrends
- Stop-loss: 1.5× ATR, Take-profit: 3.0× ATR
- Kelly sizing: 2% risk per trade
""",
        "source_files": [
            "src/features/mean_reversion_signals.py — signal_btc_mr_l2_adx()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 15m (154,368 bars, 2022-01 to 2026-05)",
        "calibration": {
            "z_score_threshold_ranging": 1.5,
            "z_score_threshold_mild_trend": 2.0,
            "adx_period": 14,
            "adx_ranging_max": 20,
            "adx_trending_min": 25,
            "sma_period": 20,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    # ── MomentumAlpha ───────────────────────────────────────────────────────
    "eth_mom_l1": {
        "signal_method": """
**Signal Logic**: Multi-factor momentum with HTF regime filter.
- **SMA Crossover (10/30)**: Golden cross (SMA10 ↑ SMA30) → long; Death cross → short
- **5-bar Rate of Change**: Confirms momentum strength (> ±0.2% required)
- **Volume Confirmation**: Current volume > 80% of 20-bar median volume
- **HTF Regime Filter**: SMA50 vs SMA100 — only long in bull regime, only short in bear
- No counter-trend signals — filter eliminates 30-50% of false entries
- Stop-loss: 1.5× ATR, Take-profit: 3.0× ATR
""",
        "source_files": [
            "src/features/momentum_signals.py — signal_momentum_improved()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 1h (38,592 bars, 2022-01 to 2026-05)",
        "calibration": {
            "sma_fast": 10,
            "sma_slow": 30,
            "roc_period": 5,
            "roc_threshold": 0.002,
            "htf_sma_fast": 50,
            "htf_sma_slow": 100,
            "vol_median_period": 20,
            "vol_threshold": 0.8,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "sol_mom_l1": {
        "signal_method": """
**Signal Logic**: Same multi-factor momentum as eth_mom_l1, applied to SOL.
- **SMA Crossover (10/30)** + **ROC(5)** + **Volume confirmation** + **HTF regime filter**
- SOL's higher volatility produces fewer but larger-magnitude signals
- Stop-loss: 1.5× ATR, Take-profit: 3.0× ATR
""",
        "source_files": [
            "src/features/momentum_signals.py — signal_momentum_improved()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 1h (38,616 bars, 2022-01 to 2026-05)",
        "calibration": {
            "sma_fast": 10,
            "sma_slow": 30,
            "roc_period": 5,
            "roc_threshold": 0.002,
            "htf_sma_fast": 50,
            "htf_sma_slow": 100,
            "vol_median_period": 20,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    # ── ExpansionAlpha ──────────────────────────────────────────────────────
    "exp_001": {
        "signal_method": """
**Signal Logic**: ATR Compression Breakout with volume confirmation.
- **ATR Compression**: Current ATR(14) < 0.7 × 20-period average ATR → compression detected
- **Volume Confirmation**: Current volume > 1.5 × 20-bar average volume
- **Breakout Entry**: Close above 20-bar range high → long; below range low → short
- Distinct from old generic signal — added volume spike filter to reduce false breakouts
""",
        "source_files": [
            "src/features/expansion_signals.py — signal_exp_001_atr_breakout()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 15m (154,368 bars, 2022-01 to 2026-05)",
        "calibration": {
            "atr_period": 14,
            "atr_compression_ratio": 0.7,
            "atr_ma_period": 20,
            "volume_ma_period": 20,
            "volume_threshold": 1.5,
            "breakout_lookback": 20,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "exp_002": {
        "signal_method": """
**Signal Logic**: Bollinger Band Squeeze with entropy filter.
- **BB Squeeze**: Normalized BB width (4σ / SMA20) below 35th percentile of 100 bars
- **Entropy Filter**: |lag-1 autocorrelation of returns| > 0.03 → market has directionality
- **Regime Direction**: 50-bar SMA context determines breakout direction bias
- **Breakout Entry**: Close above/below 20-bar range with regime confirmation
- Uses rolling rank (O(1)) instead of apply(lambda) for speed
""",
        "source_files": [
            "src/features/expansion_signals.py — signal_exp_002_bollinger_entropy()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 15m (154,368 bars, 2022-01 to 2026-05)",
        "calibration": {
            "bb_period": 20,
            "bb_std_mult": 2.0,
            "width_percentile_max": 0.35,
            "width_lookback": 100,
            "entropy_autocorr_min": 0.03,
            "regime_sma": 50,
            "breakout_lookback": 20,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "exp_003": {
        "signal_method": """
**Signal Logic**: Fractal Dimension regime switch.
- **Fractal Dimension**: Approximated via Higuchi-like method: FD ≈ log(N) / log(N·L/Σsteps)
- **Regime Detection**: FD < 0.40 = trending, FD > 0.60 = mean-reverting
- **Switch Signal**: Trending→MR → fade the recent move. MR→Trending → follow breakout
- **Lookback**: 30 bars (reduced from 50 for more signal frequency)
""",
        "source_files": [
            "src/features/expansion_signals.py — signal_exp_003_fractal_dim()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 15m (154,368 bars, 2022-01 to 2026-05)",
        "calibration": {
            "fd_lookback": 30,
            "fd_trending_max": 0.40,
            "fd_mr_min": 0.60,
            "breakout_lookback": 20,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "vol_comp_l0": {
        "signal_method": """
**Signal Logic**: Volatility Compression (Parkinson estimator).
- **Parkinson Volatility**: σ² = (1/(4N·ln2)) · Σ(ln(H/L))² over 20 bars
- **Compression Detection**: Current Parkinson vol in bottom 20% of 100-bar distribution
- **Breakout Entry**: Close > 0.2% above 20-bar range high → long; < 0.2% below → short
- Uses rolling rank (fast) for percentile calculation
""",
        "source_files": [
            "src/features/expansion_signals.py — signal_vol_comp_l0()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 15m (154,368 bars, 2022-01 to 2026-05)",
        "calibration": {
            "parkinson_period": 20,
            "vol_percentile_max": 0.20,
            "vol_lookback": 100,
            "breakout_buffer": 0.002,
            "breakout_lookback": 20,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    # ── PositioningAlpha ────────────────────────────────────────────────────
    "pos_001": {
        "signal_method": """
**Signal Logic**: OI Expansion Breakout.
- **OI Expansion**: OI delta > 0 AND OI delta > 20-bar mean OI delta
- **Price Breakout**: Close > 20-bar high (long) or close < 20-bar low (short)
- Both conditions must be true simultaneously
- Data enriched via positioning_enricher.py: 5-min OI resampled to 15m
""",
        "source_files": [
            "src/features/positioning_signals.py — signal_pos_001_oi_expansion()",
            "src/features/positioning_enricher.py — enrich_ohlcv()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
            "src/backtest/data.py — patched for enriched column preservation",
        ],
        "data_sources": (
            "Binance OHLCV 15m (154,368 bars) + "
            "metrics/metrics_btcusdt.csv OI 5m (366,203 rows) + "
            "funding/funding_btcusdt.csv (7,029 rows, 8h)"
        ),
        "calibration": {
            "oi_delta_period": 20,
            "breakout_lookback": 20,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "pos_002": {
        "signal_method": """
**Signal Logic**: OI Divergence Reversal.
- **Bullish Divergence**: Price falling (close < SMA20) + OI rising (OI > OI_MA20) → long
- **Bearish Divergence**: Price rising (close > SMA20) + OI falling (OI < OI_MA20) → short
- Divergence = existing positions closing without conviction → reversal
- 96 trades in 3000 bars (most active PositioningAlpha strategy)
""",
        "source_files": [
            "src/features/positioning_signals.py — signal_pos_002_oi_divergence()",
            "src/features/positioning_enricher.py — enrich_ohlcv()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
            "src/backtest/data.py — patched for enriched column preservation",
        ],
        "data_sources": (
            "Binance OHLCV 15m + metrics/metrics_btcusdt.csv OI 5m + "
            "funding/funding_btcusdt.csv"
        ),
        "calibration": {
            "sma_period": 20,
            "oi_ma_period": 20,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "pos_003": {
        "signal_method": """
**Signal Logic**: Funding Rate Acceleration.
- **Funding Acceleration**: 2nd derivative of funding rate (funding_rate.diff().diff())
- **Signal**: Acceleration z-score > 1.0 → crowded longs → short
- **Signal**: Acceleration z-score < -1.0 → crowded shorts → long
- Funding rate forward-filled from 8h to 15m intervals
""",
        "source_files": [
            "src/features/positioning_signals.py — signal_pos_003_funding_accel()",
            "src/features/positioning_enricher.py — enrich_ohlcv()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 15m + funding/funding_btcusdt.csv (8h→15m ffill)",
        "calibration": {
            "accel_z_threshold": 1.0,
            "accel_std_period": 50,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "pos_004": {
        "signal_method": """
**Signal Logic**: Funding Rate Cross-Asset Divergence (BTC-ETH spread).
- Compute `spread = BTC_funding_rate - ETH_funding_rate`
- **Wide spread** (|z-score| > 2.0): capital rotates → convergence trade
- Direction: if BTC funding > ETH funding → short BTC / long ETH
- Uses pre-computed spread column during data enrichment
- Best Sharpe in PositioningAlpha (0.89), 42 trades in 3000 bars
""",
        "source_files": [
            "src/features/positioning_signals.py — signal_pos_004_funding_divergence_cross()",
            "src/features/positioning_enricher.py — enrich_ohlcv(), load_funding()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
            "scripts/evaluate_strategies.py — cross-asset spread pre-computation",
        ],
        "data_sources": (
            "Binance OHLCV 15m + funding/funding_btcusdt.csv + "
            "funding/funding_ethusdt.csv (cross-asset spread)"
        ),
        "calibration": {
            "spread_z_threshold": 2.0,
            "spread_ma_period": 100,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "pos_005": {
        "signal_method": """
**Signal Logic**: Liquidation Cascade Detector.
- **OI Extreme**: OI percentile > 80 (100-bar rolling)
- **Funding Extreme**: |funding_rate| > 95th percentile of abs values (200-bar)
- **Signal**: Both extreme → contrarian entry (positive funding → short, negative → long)
- Low signal frequency (9 trades / 3000 bars) due to strict dual-extreme condition
""",
        "source_files": [
            "src/features/positioning_signals.py — signal_pos_005_liquidation_cascade()",
            "src/features/positioning_enricher.py — enrich_ohlcv()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": (
            "Binance OHLCV 15m + metrics OI + funding data"
        ),
        "calibration": {
            "oi_percentile_threshold": 80,
            "oi_lookback": 100,
            "funding_percentile_threshold": 95,
            "funding_lookback": 200,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "funding_div_l0": {
        "signal_method": """
**Signal Logic**: Funding Rate Statistical Divergence.
- **Funding Z-score**: (funding_rate - mean_100) / std_100
- **Signal**: |z| > 2.0 → mean-reversion (positive z → short, negative z → long)
- Adapted from cross-exchange divergence concept using statistical deviation proxy
- Note: Original design required multi-exchange data; Binance-only version uses rolling z-score
""",
        "source_files": [
            "src/features/positioning_signals.py — signal_funding_div_l0()",
            "src/features/positioning_enricher.py — enrich_ohlcv()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
        ],
        "data_sources": "Binance OHLCV 15m + funding/funding_btcusdt.csv",
        "calibration": {
            "funding_z_threshold": 2.0,
            "z_ma_period": 100,
            "fee": "0.1% + 0.05% slippage",
        },
    },

    # ── EnsembleAlpha ───────────────────────────────────────────────────────
    "ensemble_001": {
        "signal_method": """
**Signal Logic**: Regime-Adaptive Multi-Strategy Ensemble.
- **Sub-strategies**: eth_mom_l1 (ETH 1h), sol_mom_l1 (SOL 1h), pos_002 (BTC 15m OI), pos_004 (BTC 15m Funding)
- **Regime Sensor**: ADX(14) on BTC 15m. 0=ranging (ADX<20), 1=mixed, 2=trending (ADX>25)
- **Trending (ADX>25)**: 70% momentum (35% ETH + 35% SOL) / 30% OI (15% pos_002 + 15% pos_004)
- **Ranging (ADX<20)**: 30% momentum / 70% OI
- **Mixed**: 50% / 50% (25% each)
- **Ensemble Signal**: Weighted vote of 4 sub-signals. Entry at |weighted_score| > 0.40
- All sub-signals pre-computed by EnsembleEnricher into DataFrame columns (O(1) evaluation)
""",
        "source_files": [
            "src/features/ensemble_signals.py — EnsembleEnricher + signal_ensemble_001_regime_adaptive()",
            "src/features/momentum_signals.py — signal_momentum_improved()",
            "src/features/positioning_signals.py — signal_pos_002_oi_divergence(), signal_pos_004_funding_divergence_cross()",
            "src/features/mean_reversion_signals.py — _compute_adx()",
            "src/features/positioning_enricher.py — enrich_ohlcv()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
            "scripts/evaluate_strategies.py — ensemble data enrichment",
        ],
        "data_sources": (
            "BTC 15m OHLCV + OI + funding (primary). "
            "ETH 1h + SOL 1h OHLCV (momentum sub-signals, resampled to 15m). "
            "4 sub-signal columns + regime column pre-computed into DataFrame"
        ),
        "calibration": {
            "adx_period": 14,
            "trending_weight_momentum": 0.70,
            "trending_weight_oi": 0.30,
            "ranging_weight_momentum": 0.30,
            "ranging_weight_oi": 0.70,
            "ensemble_threshold": 0.40,
            "adx_trending_min": 25,
            "adx_ranging_max": 20,
            "sub_strategies": "eth_mom_l1, sol_mom_l1, pos_002, pos_004",
            "fee": "0.1% + 0.05% slippage",
        },
    },

    "ensemble_002": {
        "signal_method": """
**Signal Logic**: Equal-Weight Multi-Strategy Blend.
- **Sub-strategies**: eth_mom_l1 (25%), sol_mom_l1 (25%), pos_002 (25%), pos_004 (25%)
- **No regime awareness** — pure diversification play
- **Ensemble Signal**: Weighted vote of 4 sub-signals. Entry at |weighted_score| > 0.40
- Exploits near-zero correlation (~0.001) between momentum and OI signals
- All sub-signals pre-computed by EnsembleEnricher
""",
        "source_files": [
            "src/features/ensemble_signals.py — EnsembleEnricher + signal_ensemble_002_equal_weight()",
            "src/features/momentum_signals.py — signal_momentum_improved()",
            "src/features/positioning_signals.py — signal_pos_002_oi_divergence(), signal_pos_004_funding_divergence_cross()",
            "src/core/experiment_manager.py — _auto_signal_source() dispatcher",
            "scripts/evaluate_strategies.py — ensemble data enrichment",
        ],
        "data_sources": (
            "BTC 15m OHLCV + OI + funding. ETH 1h + SOL 1h for momentum. "
            "4 sub-signal columns pre-computed into DataFrame"
        ),
        "calibration": {
            "weight_per_strategy": 0.25,
            "ensemble_threshold": 0.40,
            "sub_strategies": "eth_mom_l1, sol_mom_l1, pos_002, pos_004",
            "fee": "0.1% + 0.05% slippage",
        },
    },
}

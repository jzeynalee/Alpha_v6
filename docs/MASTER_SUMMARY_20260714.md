# Alpha_v6 Strategy Evaluation — Master Summary

**Date**: 2026-07-13  
**Evaluator**: DeepCode (deepseek-v4-pro)  
**Data Source**: Binance real OHLCV from `data/raw/v3_binance/`  
**Test Infrastructure**: 171 tests all passing  
**Total Candidate Strategies**: 36 (5 archived, 31 active)

---

## Executive Summary

**All 7 auto-testable strategies FAILED the pipeline. No strategy passed more than 2/10 stages.**

The core finding is stark: the auto-generated signal functions (z-score mean-reversion, SMA momentum, ATR compression) produce **consistently negative performance** on recent Binance data across BTC, ETH, and SOL. This confirms the project's own discoveries (D005, D006, D009) but in a more severe form — even in-sample performance is now negative.

**26 of 31 active strategies cannot be auto-tested** because they require custom signal implementations that have not been built for their respective research programs. These represent the bulk of the value proposition of Alpha_v6.

---

## Part 1: Tested Strategies (7/31 Active)

| # | ID | Name | Family | PF | Sharpe | WF DSR | Stages | Result |
|---|-----|------|--------|-----|--------|--------|--------|--------|
| 1 | `btc_mr_l2` | BTC Mean-Reversion | MeanReversionAlpha | 0.444 | -6.29 | -23.19 | 2/10 | **FAILED** |
| 2 | `eth_mom_l1` | ETH Momentum Continuation | MomentumAlpha | 0.000 | -59.08 | -14.81 | 1/10 | **FAILED** |
| 3 | `sol_mom_l1` | SOL Momentum Continuation | MomentumAlpha | 0.000 | -61.67 | -10.29 | 1/10 | **FAILED** |
| 4 | `exp_001` | ATR Compression Breakout | ExpansionAlpha | 0.708 | -2.53 | nan | 2/10 | **FAILED** |
| 5 | `exp_002` | Bollinger Squeeze + Entropy | ExpansionAlpha | 0.708 | -2.53 | nan | 2/10 | **FAILED** |
| 6 | `exp_003` | Fractal Dimension Regime Switch | ExpansionAlpha | 0.708 | -2.53 | nan | 2/10 | **FAILED** |
| 7 | `vol_comp_l0` | Volatility Compression | ExpansionAlpha | 0.708 | -2.53 | nan | 2/10 | **FAILED** |

### Key Observations

1. **ExpansionAlpha strategies (exp_001/002/003, vol_comp_l0)** all produce identical results (PF=0.708) because they share the same auto-generated signal function (ATR compression with momentum direction). The signal function does not differentiate between the nuanced hypotheses.

2. **Momentum strategies (eth_mom_l1, sol_mom_l1)** produced PF=0.000 — not a single profitable trade on 3000 bars. The simple "price > 20-SMA" rule is completely ineffective.

3. **BTC Mean-Reversion (btc_mr_l2)** confirms D009: the edge is non-existent in recent data. PF=0.444 with DSR=-23.19 shows the strategy is systematically losing.

4. **Cross-asset validation**: Only SOLUSDT passed for ExpansionAlpha (PF=1.035). All other cross-asset tests failed for all strategies.

---

## Part 2: Un-Testable Strategies (26/31 Active) — Require Custom Signal Implementation

These strategies cannot be auto-tested because `ExperimentManager._auto_signal_source()` returns `None` for their families. Each requires a dedicated signal function.

### Program A: PositioningAlpha (6 strategies) — HIGHEST PRIORITY
| ID | Name | What's Needed |
|----|------|--------------|
| `pos_001` | OI Expansion Breakout | OI data loading + OI/price correlation signal |
| `pos_002` | OI Divergence Reversal | OI divergence detection from price |
| `pos_003` | Funding Rate Acceleration | Funding rate data + 2nd derivative signal |
| `pos_004` | Funding Divergence Cross-Asset | Cross-asset funding spread calculation |
| `pos_005` | Liquidation Cascade Detector | OI + funding + price cascade detection |
| `funding_div_l0` | Funding Divergence | Exchange-level funding rate comparison |

**Data available**: `funding_btcusdt.csv`, `funding_ethusdt.csv`, etc. in `data/raw/v3_binance/funding/`

### Program B: CrossSectionAlpha (4 strategies)
| ID | Name | What's Needed |
|----|------|--------------|
| `cs_001` | Cross-Sectional Relative Strength | Multi-asset ranking engine (30+ assets) |
| `cs_002` | Sector Rotation Detector | Sector classification + lead-lag detection |
| `cs_003` | Market Breadth Indicator | % assets above MA (requires 8+ symbols) |
| `cs_004` | Cross-Sectional Dispersion | Return dispersion across assets |

### Program C: ExpansionAlpha — ALL TESTED (see Part 1)

### Program D: LiquidationAlpha (3 strategies)
| ID | Name | What's Needed |
|----|------|--------------|
| `liq_001` | Liquidation Cluster Bounce | Liquidation data feed (Hyblock/CoinGlass) |
| `liq_002` | Long Squeeze Detector | Long OI + price breakdown detection |
| `liq_003` | Short Squeeze Detector | Short OI + price breakout detection |

### Program E: MicrostructureAlpha (3 strategies)
| ID | Name | What's Needed |
|----|------|--------------|
| `micro_001` | LOB Imbalance Signal | Order book depth data (bid/ask sizes) |
| `micro_002` | CVD Divergence | Cumulative Volume Delta data |
| `micro_003` | Aggressive Buy/Sell Imbalance | Market order flow data |

### Program F: ContextEngine (2 strategies)
| ID | Name | What's Needed |
|----|------|--------------|
| `mtf_001` | HTF Volatility Context Filter | Multi-timeframe vol comparison logic |
| `mtf_002` | HTF Trend Age Filter | HTF trend duration measurement |

### Program G: RelativeValueAlpha (3 strategies)
| ID | Name | What's Needed |
|----|------|--------------|
| `rv_001` | BTC-ETH Cointegration Pair | Cointegration test + spread trading logic |
| `rv_002` | BTC Dominance Effect | BTC.D data + altcoin weight adjustment |
| `rv_003` | Sector Spread Z-Score | Sector index calculation |

### Program H: FeatureLibrary (2) + MachineLearningAlpha (2)
| ID | Name | What's Needed |
|----|------|--------------|
| `feat_001` | Automated Feature Importance Ranking | 220+ feature library + SHAP |
| `feat_002` | Mutual Information Feature Selection | Feature-target MI calculation |
| `ml_001` | LightGBM Expected Return Predictor | ML pipeline with walk-forward |
| `ml_002` | Meta-Labeling for Trade Filtering | Binary classifier on trade outcomes |

### Program I: PortfolioConstruction (2 strategies)
| ID | Name | What's Needed |
|----|------|--------------|
| `port_001` | Kelly vs Half-Kelly | Multiple alpha streams to allocate |
| `port_002` | Dynamic Strategy Allocation | Rolling Sharpe tracking per stream |

### Program J: ExecutionResearch (2 strategies)
| ID | Name | What's Needed |
|----|------|--------------|
| `exec_001` | Adaptive Exit: Maker vs Taker | Spread data + fill probability model |
| `exec_002` | Dynamic Holding Time | Volatility regime detection |

---

## Part 3: Test Procedure

### 10-Stage Pipeline

Each strategy was evaluated through:

1. **Economic Explanation** (Manual) — Validate rationale exists
2. **In-Sample Discovery** (Automated) — Backtest on 3000 most recent bars with 0.1% fee + 0.05% slippage
3. **Walk-Forward Validation** (Automated) — 8-fold purged walk-forward, Deflated Sharpe Ratio (DSR)
4. **Bootstrap** (Automated) — 2000-sample bootstrap, p-value < 0.05 required
5. **Outlier Robustness** (Automated) — 1% trimmed PF drop ≤ 30% required
6. **Transaction Costs** (Automated) — Net PF > 1.0 after realistic costs
7. **Regime Stability** (Automated) — Performance across Bull/Bear/Neutral (≥2 positive required)
8. **Cross-Asset Validation** (Automated) — Test on ETHUSDT and SOLUSDT (≥2 passing required)
9. **Paper Trading** (Simulated) — 30-day estimated metrics
10. **Production Gate** (Simulated) — 5 safety checks

### Pass/Fail Criteria
- **Stage 2**: PF > 1.0
- **Stage 3**: DSR > 0 AND P(IR > 0) ≥ 0.60
- **Stage 4**: Bootstrap p-value < 0.05 AND CI lower > 0
- **Stage 5**: Trimmed PF > 1.0 AND PF drop ≤ 30%
- **Stage 6**: Net PF > 1.0
- **Stage 7**: ≥2/3 regimes with PF > 1.0
- **Stage 8**: ≥2/2 cross-assets with PF > 1.0
- **Stage 9**: Simulated PF > 1.0, trades ≥ 10, win rate > 45%
- **Stage 10**: All 5 safety checks pass

### Tools Used
- **DatasetRegistry**: Loaded real Binance OHLCV data
- **BacktestEngine**: Event-driven simulation with realistic fills
- **PurgedWalkForward**: 8-fold purged cross-validation
- **RiskManager**: Kelly sizing with circuit breakers (suppressed during evaluation)
- **EvidenceLadder**: Persistent hypothesis tracking and scoring

---

## Part 4: Key Findings & Discoveries

### Confirmed Discoveries
- **D005 (CONFIRMED)**: Walk-forward destroys in-sample PF. Even strategies that showed PF 1.8+ in earlier research now show PF < 0.8 in-sample on recent data.
- **D006 (CONFIRMED)**: Transaction costs matter. Even with 34-36 trades on 3000 bars, the 15bp total cost erodes already-negative returns further.
- **D009 (CONFIRMED)**: BTC MR is not a standalone alpha. PF=0.444 confirms the edge has vanished entirely in recent data.

### New Findings
1. **Simple momentum (price > SMA) generates almost no trades on 1h ETH/SOL** (5-6 trades in 3000 bars), and all lose. The signal is too simplistic for practical use.
2. **ATR compression as a standalone signal is unprofitable** (PF=0.708). While regime stability is decent (2/3 positive), the net return is negative.
3. **SOLUSDT showed marginal cross-asset validity for expansion strategies** (PF=1.035), suggesting compression-breakout dynamics might work better on more volatile assets.
4. **The auto-signal architecture covers only 3 of 13 families** (23% coverage). 77% of hypotheses lack executable signal implementations.
5. **Circuit breaker trips (5 consecutive losses) are common** across all strategies. The kill-switch at 10% drawdown triggers frequently, indicating these strategies have no real edge.

### Pipeline Infrastructure Observations
- The 10-stage pipeline infrastructure works correctly
- All 171 tests pass
- Data loading, backtesting, walk-forward, bootstrap, and regime analysis all function properly
- The bottleneck is not infrastructure — it's signal quality

---

## Part 5: Recommendations

### Immediate Actions
1. **Implement Program A signals** (PositioningAlpha) — OI and funding data are already available. These are the highest-expected-value strategies per the roadmap.
2. **Build OI data loading into DatasetRegistry** — the OI CSV files need to be indexed alongside OHLCV.
3. **Create signal templates** for the remaining 10 families to enable systematic testing.

### Signal Architecture Improvements
1. The `_auto_signal_source()` method needs expansion from 3 families to all 13.
2. Each family's signal should be differentiated per hypothesis (currently exp_001-003 all produce identical results).
3. Consider adding a signal registry that maps hypothesis IDs to specific signal implementations.

### Strategy-Specific Recommendations
- **BTC Mean-Reversion**: Do not retry without MTF regime filter (per NEG002)
- **ETH/SOL Momentum**: The 20-bar SMA crossover is too simplistic. Consider multi-timeframe momentum or ROC-based signals.
- **ATR Compression**: Shows marginally better results on SOL. Consider SOL-first testing for volatility strategies per D002.
- **Remaining 26 strategies**: Prioritize Program A (OI+Funding) signal implementation first, as these have the richest available data.

---

## Part 6: Evidence Ladder Status

After all evaluations:

| Level | Count | Strategies |
|-------|-------|------------|
| L0 | 31 | All untested + failed L1 strategies demoted |
| L2 | 5 | btc_mr_l2, exp_001, exp_002, exp_003, vol_comp_l0 |

**No strategy at L3 or above. Zero production candidates.**

---

## Appendix: Detailed Strategy Reports

Individual per-strategy reports are in the repository root:

1. `20260713_112222_btc_mr_l2.md` — BTC Mean-Reversion
2. `20260713_112329_eth_mom_l1.md` — ETH Momentum Continuation
3. `20260713_112418_sol_mom_l1.md` — SOL Momentum Continuation
4. `20260713_112520_exp_001.md` — ATR Compression Breakout
5. `20260713_112549_exp_002.md` — Bollinger Squeeze with Entropy Filter
6. `20260713_112630_exp_003.md` — Fractal Dimension Regime Switch
7. `20260713_112658_vol_comp_l0.md` — Volatility Compression

---

*Auto-generated by DeepCode Strategy Evaluator on 2026-07-13 11:30 UTC*  
*Data: Binance real OHLCV from data/raw/v3_binance/*
*Test suite: 171/171 passing*

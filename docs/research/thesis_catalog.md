# Thesis Catalog — All 200+ Research Hypotheses

> Organized by 10 Research Programs (A–J), priority order.
> Each hypothesis has ID, name, economic rationale, and falsification condition.

## Program A: Open Interest + Funding (★★★Very High) — ~35 hypotheses

### A1: OI Expansion/Contraction
| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| oi_001 | OI Expansion Breakout | Rising OI + rising price = new money entering, trend confirmation |
| oi_002 | OI Divergence Reversal | Price up + OI down = positions closing, weakening trend |
| oi_003 | OI Collapse Before Reversal | Sharp OI drop precedes directional change by 2-6 bars |
| oi_004 | OI Velocity (2nd derivative) | Rate of OI change predicts acceleration/deceleration |
| oi_005 | OI Percentile Regime | OI above 90th percentile = crowded, below 10th = disinterested |
| oi_006 | OI vs Volume Ratio | OI/Volume ratio normalization predicts breakouts |
| oi_007 | OI Expansion Rate | Faster OI growth = stronger trend persistence |

### A2: Funding Rate
| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| fund_001 | Funding Rate Acceleration | 2nd derivative of funding predicts squeeze conditions |
| fund_002 | Funding Divergence Cross-Asset | BTC-ETH funding spread predicts relative outperformance |
| fund_003 | Funding Rate Persistence | Funding stays extreme longer than expected — don't fade early |
| fund_004 | Funding Rate Percentile | Funding at 95th+ percentile → mean-reversion within 24h |
| fund_005 | Funding Velocity | Speed of funding change > absolute level for timing |
| fund_006 | Cross-Exchange Funding Divergence | Divergence between exchanges signals fragmented positioning |
| fund_007 | Funding + OI Interaction | High OI + extreme funding = most crowded, highest reversal prob |

### A3: OI + Funding Combined
| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| oif_001 | Crowding Score | Composite: OI percentile × funding percentile → crowding signal |
| oif_002 | Positioning Cost Index | Funding × OI = total positioning cost borne by market |
| oif_003 | OI Expansion + Funding Convergence | OI growing + funding normalizing = healthy trend |
| oif_004 | OI Contraction + Funding Divergence | OI falling + funding diverging = trend exhaustion |

---

## Program B: Cross-Sectional Momentum (★★★Very High) — ~30 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| cs_001 | Cross-Sectional Relative Strength | Rank 30-100 assets by N-day return; long top, short bottom |
| cs_002 | Sector Rotation Detector | L1 → DeFi → Meme rotation patterns |
| cs_003 | Market Breadth Indicator | % of assets above N-day MA |
| cs_004 | Cross-Sectional Dispersion | High dispersion = good for stock-picking |
| cs_005 | Leader-Follower Pairs | BTC leads → ETH follows with lag |
| cs_006 | Relative Strength Persistence | Top-quintile assets stay top for 1-4 weeks |
| cs_007 | Cross-Sectional Reversal | Extreme relative strength reverses within 1 week |
| cs_008 | Sector Momentum | Sector ETF-equivalent momentum vs asset momentum |
| cs_009 | BTC Dominance Effect on Alts | Rising BTC.D → reduce alt exposure |
| cs_010 | Cross-Sectional Volatility Scaling | Scale positions by inverse realized vol |

---

## Program C: Volatility Expansion (★★★★High) — ~20 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| exp_001 | ATR Compression Breakout | ATR at N-period low → expect expansion |
| exp_002 | Bollinger Squeeze with Entropy Filter | BB width low + low entropy = high-confidence expansion |
| exp_003 | Fractal Dimension Regime Switch | FD crossing threshold → regime change signal |
| exp_004 | Parkinson Volatility Extremes | PK vol at percentile lows → expansion within N bars |
| exp_005 | Realized Volatility Clustering | Low vol clusters persist → stay in compression trades |
| exp_006 | Volatility Term Structure | Contango vs backwardation predicts vol regime |
| exp_007 | Range Contraction → Expansion | Narrowing daily range over N days → breakout |
| exp_008 | Gap Expansion After Compression | First expansion bar after compression → continuation |

---

## Program D: Liquidations (★★★★High) — ~15 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| liq_001 | Liquidation Cluster Bounce | Price approaching liquidation cluster → reaction tradeable |
| liq_002 | Long Squeeze Detector | High long OI + price breakdown = cascade |
| liq_003 | Short Squeeze Detector | High short OI + price breakout = explosive move |
| liq_004 | Cascade Exhaustion | After N% move on high liquidations → reversal |
| liq_005 | Liquidation Imbalance | Long liq vs short liq ratio predicts direction |
| liq_006 | Pre-Liquidation Positioning | Heavy one-sided positioning before known catalyst |

---

## Program E: Market Microstructure (★★★★High) — ~30 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| micro_001 | LOB Imbalance Signal | Bid/ask ratio predicts short-term direction |
| micro_002 | CVD Divergence | CVD vs price divergence → reversal |
| micro_003 | Aggressive Buy/Sell Imbalance | Market order ratio extremes → mean-reversion |
| micro_004 | Spread Expansion | Widening spread → volatility expansion |
| micro_005 | Micro-Price Deviation | Micro-price vs mid-price → short-term direction |
| micro_006 | Queue Imbalance | Order book queue imbalance → price pressure |
| micro_007 | Volume Profile Nodes | High-volume nodes act as support/resistance |
| micro_008 | Delta Divergence | Delta vs price → hidden buying/selling |

---

## Program F: Multi-Timeframe Context (★★★Medium-High) — ~15 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| mtf_001 | HTF Volatility Context Filter | HTF vol regime → adjust LTF thresholds |
| mtf_002 | HTF Trend Age Filter | Aged HTF trends → higher reversal prob at LTF extremes |
| mtf_003 | HTF Z-Score Context | LTF mean-reversion only when HTF is range-bound |
| mtf_004 | HTF Liquidity Zones | HTF support/resistance → LTF entry zones |
| mtf_005 | MTF Alignment Score | All TFs aligned → strongest signal |

---

## Program G: Relative Value (★★★Medium) — ~15 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| rv_001 | BTC-ETH Cointegration Pair | Spread mean-reversion |
| rv_002 | BTC Dominance Effect on Alts | BTC.D trend → adjust cross-sectional weights |
| rv_003 | Sector Spread Z-Score | Sector vs BTC z-score → sector mean-reversion |

---

## Program H: Machine Learning (★★Low-Medium) — ~30 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| ml_001 | LightGBM Expected Return Predictor | ML captures non-linear interactions |
| ml_002 | Meta-Labeling for Trade Filtering | Binary classifier filters false signals |
| ml_003 | Probability Calibration | Calibrated probabilities → better position sizing |
| ml_004 | Feature Importance Stability | Stable features across time → robust model |
| ml_005 | Regime-Conditioned ML | Train separate models per regime |

---

## Program I: Portfolio Construction (★★Low) — ~15 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| port_001 | Kelly vs Half-Kelly | Empirical comparison of sizing methods |
| port_002 | Dynamic Strategy Allocation | Rotate capital based on rolling Sharpe |
| port_003 | Volatility Targeting | Target constant portfolio vol |
| port_004 | Correlation Budgeting | Limit concentration in correlated streams |

---

## Program J: Execution Research (★★Low) — ~20 hypotheses

| ID | Hypothesis | Rationale |
|----|-----------|-----------|
| exec_001 | Adaptive Exit: Maker vs Taker | Dynamic choice based on spread and urgency |
| exec_002 | Dynamic Holding Time | Adjust hold based on vol regime |
| exec_003 | TWAP Execution Quality | TWAP vs market order cost comparison |
| exec_004 | Queue Priority Estimation | Estimate fill probability for limit orders |

---

**Total: ~200+ hypotheses across 10 programs**

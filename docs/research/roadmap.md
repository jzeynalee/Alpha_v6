# Research Roadmap

> **Sequential priorities. Prevents drifting into random experimentation.**
> **Updated 2026-07-14 — reflects current evidence ladder state.**

---

## Phase Now (COMPLETED → BLOCKED)

**Objective**: Push `btc_mr_l2` to production. **Result: FAILED.**

- [x] ADX regime filter added to BTC MR (`src/features/mean_reversion_signals.py`)
- [x] Tested through Stage 7 — PF=0.428 on 10k bars, DSR=-6.17
- [x] Confirmed D009/NEG002/NEG010: BTC MR is not viable on 15m
- [ ] No hypothesis reached L5/L6

**Decision**: Pivot to best available strategy. `eth_mom_l1` (PF=1.71, L4) is the top candidate but fails walk-forward (DSR=-11.69). `pos_004` (PF=1.11, L3) is the most stable. `pos_002` (PF=1.08, L3) is the most active.

---

## Now → Program A: Open Interest + Funding (★★★★★ IN PROGRESS)

**Status**: Data pipeline built, 6/18 hypotheses tested, 2 positive (PF>1.0).

### Completed
- [x] OI data pipeline: `src/features/positioning_enricher.py` — 366K rows, 5-min OI resampled to 15m
- [x] Funding data pipeline: 7K rows, 8h funding forward-filled to 15m
- [x] OI features: OI delta, OI percentile, OI z-score, OI/MA ratio
- [x] Funding features: funding z-score, funding acceleration, funding percentile
- [x] 6 signal functions in `src/features/positioning_signals.py`
- [x] Column preservation patch in `src/backtest/data.py`

### Results
| ID | Name | PF | Trades | Verdict |
|----|------|-----|--------|---------|
| `pos_004` | Funding Cross-Asset Divergence | **1.11** | 42 | **PROMISING** — L3, Sharpe=0.89 |
| `pos_002` | OI Divergence Reversal | **1.08** | 96 | **PROMISING** — L3, most active |
| `pos_003` | Funding Rate Acceleration | 0.71 | 27 | REJECTED |
| `pos_005` | Liquidation Cascade Detector | 0.66 | 9 | REJECTED — too few trades |
| `funding_div_l0` | Funding Divergence | 0.30 | 25 | REJECTED |
| `pos_001` | OI Expansion Breakout | 0.12 | 11 | REJECTED |

### Remaining Program A hypotheses (not in evidence ladder)
| ID | Hypothesis | Priority |
|----|-----------|----------|
| `oi_003` | OI Collapse Before Reversal | High |
| `oi_004` | OI Velocity (2nd derivative) | High |
| `oi_005` | OI Percentile Regime | Medium |
| `oi_006` | OI vs Volume Ratio | Medium |
| `oi_007` | OI Expansion Rate | Medium |
| `fund_001` | Funding Rate Acceleration | Medium |
| `fund_003` | Funding Rate Persistence | Low |
| `fund_004` | Funding Rate Percentile | Low |
| `fund_005` | Funding Velocity | Low |
| `fund_006` | Cross-Exchange Funding Divergence | Low |
| `fund_007` | Funding + OI Interaction | Medium |
| `oif_001` | Crowding Score (OI×funding) | High |
| `oif_002` | Positioning Cost Index | Medium |
| `oif_003` | OI Expansion + Funding Convergence | Medium |
| `oif_004` | OI Contraction + Funding Divergence | Medium |

---

## Now → Program C: Volatility Expansion (★★★ COMPLETED)

**Status**: All 4 hypotheses tested with distinct signals. Ghost Clone bug fixed.

| ID | Name | PF (SOL) | PF (BTC) | Verdict |
|----|------|----------|----------|---------|
| `exp_001` | ATR Compression Breakout | **1.09** | 0.71 | **PROMISING on SOL** |
| `exp_002` | BB Squeeze + Entropy | 0.07 | 0.71 | REJECTED — NEG008 |
| `exp_003` | Fractal Dimension Regime | 0.00 | 0.71 | REJECTED — 0 trades |
| `vol_comp_l0` | Volatility Compression | 0.71 | 0.71 | REJECTED |

**Key finding**: SOL outperforms BTC for expansion (D015). Need 30k+ bar validation for exp_001 on SOL.

---

## Next → Program B: Cross-Sectional Momentum (★★★ NOT STARTED)

**Prerequisite**: Program A complete. Requires 30+ asset data universe.

### Steps
1. Expand data collection to 30+ assets (prioritize top-50 by volume)
2. Build cross-sectional ranking engine
3. Implement signal functions for cs_001-004
4. Run experiment batch
5. Extract discoveries

---

## Next → Ensemble Alpha (★★★ IN PROGRESS)

**Status**: Infrastructure complete. 2 hypotheses in evidence ladder. Sub-strategy signals pre-computed.

| ID | Name | PF | Trades | Verdict |
|----|------|-----|--------|---------|
| `ensemble_001` | Regime-Adaptive | 0.71 | 87 | NEEDS DYNAMIC WEIGHTING |
| `ensemble_002` | Equal-Weight Blend | 0.57 | 71 | REJECTED — NEG011 |

### Next Steps for Ensemble
1. Implement rolling-Sharpe-weighted allocation (dynamic, not fixed)
2. Add meta-labeling filter to reject weak ensemble signals
3. Test with improved sub-strategies (eth_mom_l1 + pos_004 only)

---

## Later → Programs D–J (BLOCKED)

| Program | Blocker |
|---------|---------|
| D: Liquidations | No liquidation data feed |
| E: Microstructure | No order book data |
| F: Multi-Timeframe | OI + cross-sectional not mature |
| G: Relative Value | Cross-sectional infrastructure needed |
| H: Machine Learning | Feature library not populated |
| I: Portfolio Construction | Need multiple L4+ streams |
| J: Execution Research | No production deployment |

---

## Discovery Extraction Cadence

Updated 2026-07-14:
1. [x] 15 research papers generated → `docs/research/*_20260714.md`
2. [x] 7 new discoveries added → D011–D017 in DISCOVERIES.md
3. [x] 5 new negative knowledge entries → NEG007–NEG011
4. [ ] Update knowledge graph
5. [x] Roadmap updated (this file)

---

## Guiding Principles

1. **Highest expected value programs first** — OI/Funding > Cross-sectional > Volatility > Microstructure
2. **Don't advance until current phase is complete** — Program A still has 12 untested hypotheses
3. **Every experiment produces a paper** — 15 papers in `docs/research/`
4. **Negative results are discoveries too** — 11 NEG entries prevent repeated dead-ends
5. **The Knowledge Graph grows with every experiment** — needs update
6. **SOL-first for expansion, BTC for OI/funding** — asset specialization confirmed

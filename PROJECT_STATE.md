# Alpha_v6 — Project State

> **For LLMs**: Read this file first. It tells you everything you need to know in one page.  
> **ARCHITECTURE FREEZE v1.0** — No new modules without enabling a currently-impossible experiment.

---

## What Is This?

Alpha_v6 is a **scientific research platform for discovering and validating market mechanisms** in cryptocurrency markets. It answers "what market behavior exists, under what conditions, and why?" before asking "how do we trade it?"

The architecture follows: **Market → Mechanisms → Evidence Cards → Factors → Signals → Portfolio → Execution**. "Strategy" is no longer a primary object — it's an emergent combination of validated mechanisms, position sizing, and execution rules.

---

## Current Status (2026-07-17)

| Metric | Value |
|--------|-------|
| Validated mechanisms | 5 (M001-M005) |
| Active mechanisms | 4 (M003 rejected) |
| Research programs | 3 (RP001 completed, RP002 active, RP003 rejected) |
| Validated discoveries | **26** (14 structural, 12 tactical) |
| Negative knowledge entries | **16** |
| Acceptance levels | M001=L4, M002=L3, M004=L1, M005=L1, M003=rejected |
| Test suite | **171 passing** |

### Mechanism State

| ID | Mechanism | Level | Confidence | Best Effect | Null Model | Verdict |
|----|-----------|-------|------------|-------------|------------|---------|
| M001 | Liquidity Exhaustion | **L4** Production Candidate | 0.691 | +61bp 4h / +427bp 1d | ✅ beats random (99.5%), naive, B&H | **ACCEPTED** |
| M002 | Trend Continuation | **L3** Robust | 0.763 | +55bp 4h | ❌ naive SMA20 beats it on all 3 assets | **NEEDS RECONSTRUCTION** |
| M003 | Position Unwind | — | 0.205 | — | — | **REJECTED** |
| M004 | Funding Rotation | L1 Observed | 0.219 | +33bp 4h | — | **EVIDENCE INSUFFICIENT** |
| M005 | Vol Compression | L1 Observed | 0.208 | +9bp SOL | — | **NEEDS REPLICATION** |

Confidence is frozen: saturating functions from cross-market replication, temporal WF, effect size, significance, parameter robustness, cross-asset consistency, and out-of-sample validation. Only L4+ mechanisms eligible for strategy generation.

---

## Core Infrastructure

### Research & Validation
| Module | Purpose |
|--------|---------|
| `src/validation/event_study.py` (694 lines) | Event-study engine — trigger detection, forward returns at 5 horizons, t-test + block-bootstrap CI + circular block permutation test, regime splits, cross-asset, interaction studies, boundary discovery, stability analysis, effect-size-first ranking |
| `src/core/mechanism_registry.py` (560 lines) | M001-M005 catalog — reusable market behaviors with confidence scoring, effect summaries with CI, boundaries, stability metrics, research cost optimizer |
| `src/core/causal_graph.py` (404 lines) | Cause→Mechanism→Observable→Prediction chains, auto hypothesis generation, risk data per mechanism |
| `src/core/evidence_ladder.py` | L0-L6 classification + multi-dimensional scoring |
| `src/core/experiment_manager.py` | Dispatches to 6 signal families (MeanReversion, Momentum, Expansion, Positioning, Ensemble) |
| `src/core/knowledge_base.py` | Persistent research findings |
| `src/core/research_pipeline.py` | 10-stage automated evaluation |
| `data/experiments/mechanism_evidence_cards.json` | Machine-readable evidence cards with FDR tracking, sample classification (5 levels), negative evidence DB |

### Signal Implementation (6 Families)
| Family | File | Hypotheses |
|--------|------|------------|
| MeanReversionAlpha | `src/features/mean_reversion_signals.py` | btc_mr_l2 (ADX-filtered z-score) |
| MomentumAlpha | `src/features/momentum_signals.py` | eth_mom_l1, sol_mom_l1 (SMA crossover + ROC + volume + HTF filter) |
| ExpansionAlpha | `src/features/expansion_signals.py` | exp_001-003, vol_comp_l0 (4 DISTINCT signals — Ghost Clone fixed) |
| PositioningAlpha | `src/features/positioning_signals.py` | pos_001-005, funding_div_l0 (OI + funding signals) |
| PositioningAlpha | `src/features/positioning_enricher.py` | OI (366K rows, 5m) + funding (7K rows, 8h) → enriched OHLCV |
| EnsembleAlpha | `src/features/ensemble_signals.py` | ensemble_001 (regime-adaptive), ensemble_002 (equal-weight) |

### Data
- **Binance OHLCV**: 8 symbols (BTC, ETH, SOL, BNB, XRP, DOGE, LINK, TON), timeframes 5m/15m/1h/4h/1d
- **Open Interest**: 8 symbols, 5-min intervals, 366K rows (2023-01→2026-06)
- **Funding Rate**: 6 symbols, 8h intervals, 7K rows (2020-01→2026-05)

---

## Methodology

### Event-Study Approach (replaces strategy testing)

Every hypothesis decomposes into sub-questions before strategy construction:

```
H01: Does trigger predict forward returns?     → Event study (50k bars)
H02: At which horizon?                          → 1,3,5,10,20 bar horizons
H03: Which regime?                              → Trend, vol, volume splits
H04: Which assets?                              → BTC, ETH, SOL, BNB cross-asset
H05: What exit maximizes edge?                  → Exit analysis
H06: Survive costs?                             → Cost hurdle check
─── Only after H01-H06 pass ───
S01: Build strategy from validated evidence
```

### Statistical Standards
- **Log returns** ln(Pt+h/Pt) — symmetric, additive, better for t-tests
- **Three-test defense**: one-sided t-test + bootstrap 95% CI (5000 iterations) + circular block bootstrap permutation (block_size=20, 2000 perms)
- **FDR tracking**: 12 tests, 7 significant, FDR=0.086
- **Sample classification**: exploratory → tentative → moderate → strong → established
- **Effect uncertainty stored as CI**: mean_bp + ci_lower_bp + ci_upper_bp + n_events

---

## Key Discoveries

### The Critical One (D019)
**Mechanisms are invisible at 15m but dominant at 4h/1d.** Effect is non-linear with timeframe:

| Mechanism | 15m | 4h | 1d |
|-----------|-----|-----|-----|
| M001 Z-score MR | +3.6bp (ns) | **+61.1bp ★★★** | **+427bp ★★★** |
| M002 ROC momentum | +6.5bp (ns) | **+54.8bp ★★★** | +222bp (low n) |
| M004 Funding | — | **+33.1bp ★★★** | **+84.9bp ★** |

→ **All mechanism validation MUST include 4h+ timeframes before rejection.**

### Other Key Findings
- D020: Z-score overbought asymmetric — only tops predict reversal, not bottoms
- D021: ROC is the momentum driver, SMA crossover adds noise
- D022: Funding works on BTC, not ETH (confirms D001 at mechanism level)
- D023: M001 AMPLIFIED by strong trends at 4h (causal graph edge reversed)
- D024: ROC(5) momentum is commoditized — naive SMA20 beats it (D025 validates null model gate)
- D014: Near-zero correlation momentum vs OI (~0.001)

### Full catalog: `DISCOVERIES.md` — **26 findings + 16 NEG entries**

---

## Entry Files for LLMs (Read Order)

| # | File | Purpose |
|---|------|---------|
| 1 | `PROJECT_STATE.md` | Current state — **read first** |
| 2 | `NEXT_ACTION.md` | Exact instructions, architecture freeze rules — **read second** |
| 3 | `ARCHITECTURE.md` | System design — **read third** |
| 4 | `DISCOVERIES.md` | **26 validated findings + 16 NEG entries** — read fourth |
| 5 | `docs/methodology/event_study_method.md` | Event-study methodology + case study |
| 6 | `docs/research/roadmap.md` | Research priorities |
| 7 | `docs/research/higher_timeframe_validation_20260716.md` | Breakthrough: mechanism validation at 4h/1d |
| 8 | `docs/research/btc_mr_l2_decomposed_20260716.md` | Worked example: decomposed hypothesis |
| 9 | `data/experiments/mechanism_evidence_cards.json` | Machine-readable mechanism state |

### Strategy Reports (15 in `docs/research/`)
Per-strategy consolidated reports with Method, Source Code, Data Sources, Calibration Parameters, Backtest Configuration, Run History, and Decision sections.

---

## What NOT to Do

- ❌ Do NOT add new architecture modules (Freeze v1.0)
- ❌ Do NOT test complete strategies without mechanism validation
- ❌ Do NOT reject a mechanism based solely on 15m data (D019)
- ❌ Do NOT treat "strategy" as a primary research object — mechanisms are
- ❌ Do NOT modify existing modules without `pytest tests/` (171 tests)

---

*Last updated: 2026-07-16 — Architecture Freeze v1.0*

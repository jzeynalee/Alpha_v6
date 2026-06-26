# Pipeline Improvement Plan v2 — Auditor-Reviewed

**Generated**: 2026-06-14T14:01:38+00:00
**Status**: Revised after auditor review. None of these changes have been implemented yet.
**Previous version**: `docs/20260614_134657_improvement_plan.md`
**Reference**: Pipeline audit of BTCUSDT 5min vs `strategies_hub_v2_btcusdt_20260613T234035.json`

---

## Auditor Verdict

| Area | Score | Notes |
|---|---|---|
| Diagnosis quality | 9/10 | Correctly identifies label mismatch, PF inflation, gate misalignment |
| Engineering practicality | 8.5/10 | Most fixes are code changes, not new infrastructure |
| Profitability relevance | 8/10 | Attacks observed failure modes, not theoretical ones |
| Risk of overfitting | 6/10 | Bar-direction labels would overfit to `sign(close[t+H] - close[t])` — trade-outcome labels are more robust |
| Priority ordering | 7/10 | Phases should be: labels → ranking → audit → minimal pipeline → A/B test layers |

**Overall**: ~80% agreement. Main corrections:
1. Labels must be **trade-outcome based** (`TP hit before SL`), not direction-based (`close[t+H] > close[t]`)
2. Remove all expected performance numbers — they create anchoring bias
3. Eliminate useless gates (PriceAction), don't tune them
4. Add marginal-contribution analysis per pipeline layer
5. Build minimal pipeline first, then A/B test each additional layer

---

## Current State (from pipeline audit)

| Stage | Signals | Trades | WR | PF | P&L |
|---|---|---|---|---|---|
| SignalFactory (raw) | 2,655 | 2,655 | 34.3% | 0.26 | -$10,000 |
| + RiskManager | 1,193 | 1,193 | 32.9% | 0.17 | -$3,454 |
| + PriceAction | 1,189 | 1,189 | 33.0% | 0.17 | -$3,440 |
| + DeterAlpha | 0 | 0 | — | — | $0 |

**Marginal contribution per gate**:
- RiskManager: reduces trades 55%, saves $6,546 in losses — **positive contribution**
- PriceAction: filters 4 signals (0.3%), saves $13.52 — **negligible contribution**
- DeterAlpha: 0% survival — **non-functional as a filter**

---

## Corrected Root Cause Analysis

### Root Cause #1 (CRITICAL): Discovery Labels Don't Match Trading Outcomes

**Problem**: `label_zones()` classifies zones as bull/bear based on `close_end - close_start > ATR`. Strategies are ranked by how well features predict **zone direction** — not by whether trading those signals would be profitable.

**The auditor's key insight**: Profitability ≠ direction. A strategy that correctly predicts "close will be 2% higher in 20 bars" can still lose money because it gets stopped out on a 1% adverse move first. The label should be:

```
LONG signal label:
  +1  if TP was hit before SL was hit
  -1  if SL was hit before TP was hit
   0  if neither was hit within max_hold_bars
```

This aligns discovery with **actual trade outcomes**, not theoretical price direction. It bakes the SL/TP structure into the label itself, so strategies learn to predict trade-level outcomes directly.

**Files affected**: `src/core/strategy_discovery.py` (`label_zones` replacement), `scripts/signal_factory_simulation.py` (`process_timeframe`), `scripts/signal_factory_holdout.py`

---

### Root Cause #2 (CRITICAL): Discovery PF ≠ Trade PF (confirmed by auditor)

**Problem**: `evaluate_strategy()` PF uses raw zone returns `(close_end - close_start) / close_start` — no SL/TP, no fees, no slippage. Discovery PF is ~10× higher than trade PF.

**Auditor agreement**: "The observation that top-ranked strategies lose money despite ranking highly is extremely important."

**Fix**: Replace zone-return PF with trade-simulated PF. For each matched zone, simulate a trade with entry at zone-start, SL/TP from RiskManager config, exit at first hit, and compute net P&L after fees/slippage. Then rank by **net expectancy after costs**.

---

### Root Cause #3 (CRITICAL): No Trade-Outcome Labels Exist

**Problem**: Zero code constructs trade-outcome labels. All existing labeling (`label_zones`, zone classification, holdout validation) uses price-direction thresholds, not trade outcomes.

**Fix**: Add `compute_trade_labels(df, sl_atr_mult, tp_atr_mult, max_hold_bars)` to `strategy_discovery.py` that walks through each bar, simulates a trade with ATR-based SL/TP, and records the outcome. This is the foundation for every subsequent fix.

---

### Root Cause #4 (HIGH): RiskManager Threshold Misalignment (confirmed)

**Problem**: `min_proba_alpha=0.65` vs Wilson LB 0.0-0.15 range. Gate is not calibrated to the signal source — it's a units mismatch, not a strategy quality problem.

**Auditor agreement**: "That is not a strategy problem. That is a units problem."

**Fix**: After retraining on trade-outcome labels, recalibrate `min_proba_alpha` to the actual Wilson LB distribution. Add `min_wilson_lb_sf` config key specifically for the SignalFactory path.

---

### Root Cause #5 (HIGH): DeterAlpha Non-Functional (confirmed)

**Problem**: 0/14,568 signals survive. Proxy regime labels `sign(close[t] - close[t-20])` have no causal relationship with features.

**Auditor**: "DeterAlpha is not functioning as a filter. It is functioning as a kill-switch."

**Fix**: Feed trade-outcome labels (from fix #3) as DeterAlpha's causal target. If it still produces 0% survival after that fix, **remove it** — don't keep tuning a broken component.

---

### Root Cause #6 (HIGH): PriceAction Should Be Removed, Not Tuned

**Original plan**: "Tighten threshold from 0.40 to 0.60."

**Auditor correction**: "If the audit shows 0.3% filtering effect, then first prove PriceAction has predictive power. If it doesn't, remove it. Don't tune it. A useless gate tuned harder usually remains useless."

**Fix**: Run marginal-contribution analysis on PriceAction using survival audit data. If it doesn't improve expectancy or PF, **delete it from the pipeline**.

---

### Root Cause #7 (MEDIUM): Scoring Ranks Statistical Purity, Not Profitability (confirmed)

**Problem**: `score = Wilson_lb × log(1+support) × PF` ranks by statistical consistency, not by expected P&L. The auditor agrees this should become **net expectancy after costs** as the primary ranking metric.

---

### Root Cause #8 — NEW: No Marginal-Contribution Analysis Exists

**Auditor**: "The biggest missing piece. For every stage, measure trades, WR, PF, expectancy. Then compute marginal contribution of each layer. Only keep layers that improve expectancy, PF, drawdown. Everything else should be deleted."

**Fix**: Extend `scripts/pipeline_audit.py` to read survival audit logs (`survival_*.jsonl`) and produce per-layer marginal contribution tables. This becomes the decision tool for which layers stay and which go.

---

## Revised Implementation Plan

### Phase A — Fix Discovery Labels (P0)

| # | Action | Files | Effort |
|---|---|---|---|
| A1 | Add `compute_trade_labels(df, sl_atr, tp_atr, max_hold)` → array of {+1, -1, 0} per bar | `src/core/strategy_discovery.py` | 3 hours |
| A2 | Create `TradeOutcomeStrategyDiscovery` that votes features against trade labels instead of zone labels | `src/core/strategy_discovery.py` | 1 day |
| A3 | Replace zone-return PF in `evaluate_strategy()` with mini trade simulation that applies SL/TP/fees/max-hold | `src/core/strategy_discovery.py` | 1 day |
| A4 | Regenerate strategy pool using trade-outcome labels + trade-simulated PF | `scripts/signal_factory_simulation.py` | 1 run |

**Checkpoint**: Rerun `pipeline_audit.py` on new pool. Verify Stage 0 WR improves beyond baseline 34.3%.

---

### Phase B — Replace Strategy Ranking (P0)

| # | Action | Files | Effort |
|---|---|---|---|
| B1 | Replace `score = Wilson × log(1+s) × PF` with `net_expectancy = avg_win × WR - avg_loss × (1-WR) - costs` | `scripts/signal_factory_simulation.py` | 2 hours |
| B2 | Rank strategies by net expectancy; select top 20 per direction by profitability, not statistical purity | `scripts/signal_factory_simulation.py` | 1 hour |

**Checkpoint**: Verify that top-ranked strategies by net expectancy actually outperform in backtest.

---

### Phase C — Survival Audit + Marginal Contribution (P1)

| # | Action | Files | Effort |
|---|---|---|---|
| C1 | Extend `pipeline_audit.py` to compute per-layer marginal contribution (Δ WR, Δ PF, Δ expectancy) | `scripts/pipeline_audit.py` | 3 hours |
| C2 | Run survival audit on new strategy pool across all timeframes | `scripts/pipeline_audit.py --all-tfs` | 3 runs |
| C3 | Identify layers with NEGATIVE marginal contribution | Analysis | 1 hour |

**Decision gate**: If PriceAction has negative or zero contribution → delete. If DeterAlpha still at 0% → delete. If CSS has negative contribution → delete.

---

### Phase D — Build Minimal Pipeline (P1)

| # | Action | Files | Effort |
|---|---|---|---|
| D1 | Create minimal production path: `SignalFactory → RiskManager → Execution` (nothing else) | `src/core/alpha_factory.py` (config toggle) | 1 hour |
| D2 | Benchmark minimal pipeline against full pipeline | `scripts/pipeline_audit.py` | 1 run |
| D3 | Recalibrate `min_proba_alpha` to the new Wilson LB distribution from trade-outcome labels | `src/risk/risk_manager.py`, config | 1 hour |

**Checkpoint**: Minimal pipeline should have equal or better metrics than full pipeline (since it removes broken gates).

---

### Phase E — A/B Test Each Layer (P2)

| # | Action | Files | Effort |
|---|---|---|---|
| E1 | Add DeterAlpha back → A/B test vs minimal | `src/core/alpha_factory.py` | 2 hours |
| E2 | Add PriceAction back (if Phase C shows positive contribution) → A/B test | `src/core/alpha_factory.py` | 1 hour |
| E3 | Add regime alignment (bull strats only in Bull) → A/B test | `src/core/alpha_factory.py` | 2 hours |
| E4 | Per-strategy SL/TP grid search → A/B test | New script | 1 day |
| E5 | Multi-strategy consensus (≥3 agree) → A/B test | `src/core/alpha_factory.py` | 4 hours |

**Rule**: Only keep a layer if it **measurably improves expectancy** in an A/B test. Delete everything else.

---

## What the Auditor Explicitly Rejected

| Original Proposal | Auditor Verdict | Reason |
|---|---|---|
| `sign(close[t+H] - close[t])` labels | **Rejected** | Direction ≠ profitability. Use `TP hit before SL` labels instead. |
| Expected WR 42-46%, PF 0.7-0.9 | **Rejected** | Numbers not derived from evidence. Remove all performance predictions. |
| Tighten PriceAction threshold | **Rejected** | First prove it has predictive power. If not, delete it — don't tune it. |
| Keep all gates, recalibrate | **Rejected** | Delete layers with negative contribution. Build minimal pipeline first. |

---

## Success Criteria (Falsifiable, No Predicted Numbers)

| Criterion | How to Verify |
|---|---|
| Trade-outcome labels produce higher Stage 0 WR than zone labels | `pipeline_audit.py` on new hub |
| Top-ranked strategies by net expectancy outperform top-ranked by Wilson score | Compare strategy ranking vs backtest P&L |
| Minimal pipeline (SF + RiskManager) outperforms full pipeline | A/B test via `pipeline_audit.py` |
| Each added layer improves expectancy | Marginal contribution analysis per layer |
| DeterAlpha survival > 0% with trade-outcome labels | Stage 3 trade count > 0 |

---

## The Single Most Important Change

From the auditor:

> "If you execute only one thing from the entire roadmap, I would choose: **Replace zone-based discovery with trade-outcome-based discovery and then rerun the entire Signal Factory generation process from scratch.**"

This is Phase A. Everything else depends on it.

---

*Generated by Deep Code on 2026-06-14. Revised after auditor review.*
*Previous version: `docs/20260614_134657_improvement_plan.md`*

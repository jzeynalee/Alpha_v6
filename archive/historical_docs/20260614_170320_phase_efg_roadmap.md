# Alpha V3 — Phase E/F/G Roadmap (Auditor-Reviewed)

**Generated**: 2026-06-14T17:03:20+00:00
**Status**: Auditor review of `docs/20260614_153720_phase_implementation_report.md`
**Previous**: `docs/20260614_140138_improvement_plan_v2.md`

---

## Auditor Verdict

| Area | Score | Notes |
|---|---|---|
| Engineering quality | 9/10 | Well-implemented trade labels, layer analysis, minimal pipeline |
| Experimental methodology | 9.5/10 | Measuring actual trading-path outcomes, not feature hypotheses |
| Architecture simplification | 9/10 | Removed 2 broken gates, cut pipeline in half |
| Statistical rigor | 8.5/10 | Layer contribution is the right methodology |
| Evidence of actual alpha | **3/10** | Every configuration still loses money |

**Key distinction**: "The project is now becoming scientifically trustworthy. However, the report does not demonstrate a profitable strategy yet. It demonstrates that you've removed several sources of self-inflicted damage and have a cleaner path to discovering whether a real edge exists."

---

## Auditor Corrections

### Correction 1: "5min is viable" → "5min is least bad"

The report claimed 5min is "the only viable timeframe." The auditor: "All are losing. The correct conclusion is: None are profitable. 5m is merely least bad."

### Correction 2: Timeframe comparison is apples-to-oranges

The same SL=1.5×ATR, TP=2.0×ATR, max_hold=20 across all timeframes means:

| TF | SL/TP as % of price | Real holding time | Strategy type |
|---|---|---|---|
| 5m | ~0.5-1% / ~0.7-1.3% | 100 min | Scalping |
| 15m | ~1-2% / ~1.4-2.7% | 300 min | Swing |
| 60m | ~3-5% / ~4-7% | 1200 min (20h) | Position |

These are fundamentally different strategies. The auditor: "You're not comparing timeframes. You're comparing a 100-minute system, a 300-minute system, and a 20-hour system." Per-timeframe SL/TP optimization is required before any conclusion about timeframe viability.

### Correction 3: Net expectancy needs stronger support floor

Current: `score = expectancy × log(1 + support)`. The auditor recommends `expectancy × sqrt(support)` or a stronger support floor to prevent "3 lucky trades" from outranking "300 statistically meaningful trades." The support distribution was not shown.

---

## What the Auditor Wants Next

### Phase E — SignalFactory vs. RiskManager Expectancy

**Question**: Does SignalFactory produce positive-expectancy signals that RiskManager merely filters, or does RiskManager simply reduce losses on negative-expectancy signals?

**Method**: Compare Stage 0 (raw SF, no RiskManager) vs Stage 1 (SF + RiskManager) across all datasets. If Stage 0 has negative expectancy and Stage 1 has less-negative expectancy, the problem is in SignalFactory — not in the gates.

**Files**: `src/core/layer_contribution.py` (already has the analysis, just needs Stage 0 vs Stage 1 comparison with expectancy as primary metric)

**Decision**: If SignalFactory has negative expectancy, stop pipeline work and fix discovery. If it has positive expectancy but RiskManager degrades it, fix RiskManager calibration.

---

### Phase F — Validate Neutral Mean Reversion Thesis

**Current evidence** (from previous audit findings):
- BB-%B and SMI are dominant features among surviving neutral strategies
- Neutral strategies show stability across holdout validation
- The feature convergence report shows consistent cross-dataset dominance

**Method**: Build a **standalone** strategy, not through the discovery pipeline:

```python
# Direct conditional logic, not DSL voting
if bb_pct_b < 0.2 and smi < 30 and regime == "Neutral":
    direction = +1  # long mean-reversion
    confidence = 1.0 - bb_pct_b  # stronger signal when further from band
```

Backtest this against the SignalFactory-generated strategies. Compare P&L, WR, PF.

**Rationale**: "That experiment has higher expected value than further pipeline work." The discovery engine is selecting "less bad" strategies, not profitable ones. A manually constructed thesis-tested strategy might find edge that the automated discovery misses.

---

### Phase G — Failed Mean Reversion → Continuation

**Current evidence**: Mean reversion strategies survive holdout validation. The natural follow-up: "What happens when they don't revert?"

**Hypothesis**: A failed mean reversion (price continues beyond the band, BB-%B drops further) is a strong continuation signal — trend-following in the direction the market is already moving.

**Method**:
1. Identify bars where a mean-reversion signal fired but price continued moving against it (failed reversion)
2. Enter in the direction of the continuation (opposite of the mean-reversion direction)
3. Compare P&L vs the original mean-reversion P&L

**Rationale**: Failed signals are often stronger than successful ones. A mean-reversion strategy that's right 45% of the time may generate continuation signals from the 55% that fail.

---

## Updated Priority Roadmap

| Phase | What | Question | Effort |
|---|---|---|---|
| **E** | SF vs RiskManager expectancy | Does SignalFactory have positive edge? | 2 hours |
| **F** | Neutral mean reversion standalone | Can a direct thesis beat discovery? | 4 hours |
| **G** | Failed mean reversion → continuation | Do failures become signals? | 4 hours |
| — | Per-TF SL/TP optimization | Fix apples-to-oranges 3TF comparison | 1 day |
| — | Support floor for net expectancy | Prevent 3-lucky-trade strategies | 1 hour |

---

## What the Auditor Wants to STOP Doing

1. **Stop general pipeline optimization** — "The next stage should focus much more on validating specific hypotheses and much less on general pipeline optimization."

2. **Stop calling 5min "viable"** — "All are losing. None are profitable."

3. **Stop comparing timeframes without per-TF SL/TP calibration** — different timeframes need different exit parameters.

4. **Stop treating DeterAlpha as fixable** — "Removing it is correct until proven otherwise."

---

## Success Criteria (Revised)

| Criterion | How to Verify |
|---|---|
| Any configuration achieves PF > 1.0 | Backtest with positive P&L |
| SignalFactory has positive raw expectancy | Stage 0 expectancy > 0 |
| Standalone neutral thesis beats discovery | Direct strategy P&L > best SF strategy P&L |
| Failed mean reversion generates profitable continuation signals | Continuation P&L > reversion P&L |

**The only metric that matters**: P&L > $0. Until then, the system is not alpha — it's a research platform with improving methodology.

---

*Generated by Deep Code on 2026-06-14 after auditor review.*
*Previous reports: `docs/20260614_153720_phase_implementation_report.md`, `docs/20260614_140138_improvement_plan_v2.md`*

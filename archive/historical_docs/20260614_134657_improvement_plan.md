# Pipeline Improvement Plan — From Loss-Making to Profitable

**Generated**: 2026-06-14T13:46:57+00:00
**Status**: Diagnostic complete. None of these changes have been implemented yet.
**Reference**: Based on pipeline audit of BTCUSDT 5min vs `strategies_hub_v2_btcusdt_20260613T234035.json`

---

## Current State

| Stage | Signals | Trades | WR | PF | P&L |
|---|---|---|---|---|---|
| SignalFactory (raw) | 2,655 | 2,655 | 34.3% | 0.26 | -$10,000 |
| + RiskManager | 1,193 | 1,193 | 32.9% | 0.17 | -$3,454 |
| + PriceAction | 1,189 | 1,189 | 33.0% | 0.17 | -$3,440 |
| + DeterAlpha | 0 | 0 | — | — | $0 |

**The system loses money at every stage that produces trades.**

---

## Root Cause Analysis

### Root Cause #1 (CRITICAL): Zone Labels ≠ Bar-Level Alpha

**What happens**:
- `label_zones()` in `src/core/strategy_discovery.py` classifies multi-bar swing segments as bull/bear/neutral based on `close_end - close_start > ATR_threshold`
- SignalFactory evaluates features at **zone-start bars only** and learns "does feature X predict zone direction?"
- In live trading, `SignalHub.evaluate()` runs at **every bar**, including mid-zone bars where the directional edge is diluted
- A strategy that correctly predicts zone direction 80% of the time may only predict bar-level direction 50% of the time

**Evidence**: The `docs/backtest_report.md` already identified this:
> "Label mismatch: Zone labels (bull/bear/neutral by ATR threshold over a multi-bar segment) don't translate to bar-level direction accuracy"

**Why it matters**: This is the #1 reason for 34.3% WR. Zone labels measure multi-bar trend, but trades are placed and exited at individual bars with SL/TP.

---

### Root Cause #2 (CRITICAL): Discovery PF ≠ Trade PF

**What happens**:
- `evaluate_strategy()` in `strategy_discovery.py:1212-1221` computes PF from raw zone returns:
  ```python
  raw = (z.close_end - z.close_start) / z.close_start  # no SL/TP, no fees
  rets.append(raw * d)  # signed return, no trade simulation
  ```
- The actual backtest applies ATR-based SL/TP, fees (0.1%), and slippage (0.05%)
- A strategy with discovery PF=2.0 may have actual trade PF=0.17

**Evidence**: Strategy discovery reports PF > 1.0 for top strategies, but Stage 1 backtest PF = 0.17 for ALL strategies combined.

**Why it matters**: Strategies are ranked by a PF metric that bears no relationship to actual profitability. The "best" discovery strategies are not the best trading strategies.

---

### Root Cause #3 (CRITICAL): No Bar-Level Labeling Exists

**What happens**:
- The entire pipeline operates on zone-level data: `label_zones()`, `evaluate_strategy()`, `vote_features_at_zone_start()`, `holdout validation`
- There is **zero code** that constructs `label[t] = sign(close[t+H] - close[t])` for any horizon H
- Every component — from discovery to backtest — inherits this zone-level assumption

**Why it matters**: Until bar-level labels exist, no other fix (RiskManager calibration, DeterAlpha tuning, PriceAction thresholding) can make the system profitable. The labels are the foundation.

---

### Root Cause #4 (HIGH): RiskManager Threshold Misalignment

**What happens**:
- `RiskManager.min_proba_alpha = 0.65` (expects bar-level alpha probability from an alpha model)
- SignalFactory Wilson LB scores are in range 0.00-0.15 (zone-level label accuracy)
- At 0.65: all 2,655 signals blocked. At 0.00: all 14,973 pass.

**Evidence**: Pipeline audit Stage 1 = 0 trades at `min_proba_alpha=0.65`, 1,193 trades at 0.00.

**Why it matters**: The RiskManager cannot function as a meaningful gate — it's either fully open or fully closed. The threshold was calibrated for a different signal source.

---

### Root Cause #5 (HIGH): DeterAlpha 100% Rejection Rate

**What happens**:
- DeterAlpha's `RollingCausalAnalyser` discovers causal feature sets using **proxy regime labels**: `sign(close[t] - close[t-20])`
- These proxy labels have no stable causal relationship with any feature at the 5-minute timeframe
- 0 of 14,568 PriceAction-approved signals pass the causal validation gate

**Evidence**: Pipeline audit Stage 3 = 0 trades. `warm_features()` log previously showed `CausalRefit C=0 A=0` collapse.

**Why it matters**: The causal gate is completely non-functional for SignalFactory strategies. It either needs bar-level labels or a complete redesign.

---

### Root Cause #6 (HIGH): PriceAction Is a No-Op

**What happens**:
- `|alpha_raw| >= 0.40` threshold in the pipeline audit
- Only 4 of 1,193 signals (0.3%) are filtered out
- The remaining 1,189 trades have identical win rate (33.0% vs 32.9%)

**Evidence**: Pipeline audit Stage 1→2 marginal impact = 4 signals, $13.52 P&L improvement.

**Why it matters**: This gate provides zero signal discrimination. It consumes computation without improving outcomes.

---

### Root Cause #7 (MEDIUM): Strategy Scoring Ignores Trade Economics

**What happens**:
- `Strategy.score = Wilson_lb × log(1 + support) × PF`
- This ranks strategies by **statistical purity** (how consistently features vote with zone labels)
- It does NOT consider: trade frequency, expected P&L after costs, drawdown, or risk-adjusted return

**Evidence**: The top-ranked strategies by discovery score (`bear_6f`, `bull_6f`) lose money in backtest. There is zero correlation between discovery score rank and actual P&L rank.

**Why it matters**: The strategy selection pipeline optimizes for the wrong objective. We're selecting the most statistically pure strategies, not the most profitable ones.

---

### Root Cause #8 (MEDIUM): Feature Evaluation at Zone-Start Only

**What happens**:
- `vote_features_at_zone_start()` evaluates features at `zone.indicator_eval_bar` (first bar of zone)
- Zones span 10-50 bars. Features at bar 1 may look very different from features at bar 15.
- In live trading, `SignalHub.evaluate()` fires when ALL features agree at the CURRENT bar — which may be deep inside a zone

**Evidence**: The backtest report notes: "Signal dilution: Strategies evaluate ALL bars, not just zone starts."

**Why it matters**: The feature voting patterns learned at zone-start don't generalize to mid-zone bars. The edge is diluted.

---

## Priority Roadmap

### P0 — Foundation (must fix before anything else)

| # | Fix | File(s) | Expected Impact | Effort |
|---|---|---|---|---|
| 1 | Add bar-level label function `compute_bar_labels(close, horizon)` returning `sign(close[t+H] - close[t])` for H ∈ {5, 10, 20} | `src/core/strategy_discovery.py` | Foundation for all fixes below | 2 hours |
| 2 | Create `BarLevelStrategyDiscovery` class that votes features against bar-level labels instead of zone labels | `src/core/strategy_discovery.py` | Directly addresses root cause #1 | 1 day |
| 3 | Replace zone-return PF in `evaluate_strategy()` with a mini walk-forward trade simulation that applies SL/TP, fees, max-hold | `src/core/strategy_discovery.py` | Fixes root cause #2; strategies ranked by actual profitability | 2 days |

**After P0**: Expected Stage 0 WR improvement from 34.3% → 42-46%. PF from 0.26 → 0.7-0.9.

### P1 — Gate Calibration (after P0)

| # | Fix | File(s) | Expected Impact | Effort |
|---|---|---|---|---|
| 4 | Feed bar-level labels to DeterAlpha instead of proxy regime labels; use `close[t+H]` as causal target | `src/core/alpha_factory.py`, `src/core/deter_alpha.py` | Unblocks Stage 3; +2-3% WR | 1 day |
| 5 | Calibrate `min_proba_alpha` to 75th percentile of new Wilson LB distribution; add `min_wilson_lb_sf` config key for SignalFactory path | `src/risk/risk_manager.py`, config | RiskManager gates become meaningful | 2 hours |
| 6 | Tighten PriceAction `|alpha_raw|` threshold to `>= 0.60` and calibrate against trade outcomes; or replace with meta-labeling model | `src/features/price_action.py` | Gate actually discriminates signals | 4 hours |

**After P1**: Expected WR 46-50%, PF 0.9-1.1.

### P2 — Optimization (after P1)

| # | Fix | File(s) | Expected Impact | Effort |
|---|---|---|---|---|
| 7 | Add regime-aligned filter: bull strategies only trade in Bull regime, bear only in Bear | `src/core/alpha_factory.py` (V4 loop) | +2-3% WR | 2 hours |
| 8 | Grid search optimal SL/TP ATR multipliers per strategy (SL ∈ {1.0, 1.5, 2.0, 2.5}, TP ∈ {1.5, 2.0, 3.0, 4.0}) | `scripts/backtest_strategies.py` or new script | +2-5% WR | 1 day |
| 9 | Multi-strategy consensus: require ≥3 strategies in same direction to fire within K bars | `src/core/alpha_factory.py` | +2-4% WR | 4 hours |
| 10 | Replace `score = Wilson × log(1+s) × PF` with trade-economics-aware ranking: `expected_pnl = n_trades × (avg_win × WR - avg_loss × (1-WR) - costs)` | `scripts/signal_factory_simulation.py` | Strategies ranked by expected profitability | 4 hours |

**After P2**: Expected WR 52-58%, PF 1.2-1.6.

---

## Implementation Order

```
P0.1 → P0.2 → P0.3  (bar-level foundation — cannot skip)
  ↓
P1.4 → P1.5 → P1.6  (gate calibration — depends on P0)
  ↓
P2.7 → P2.8 → P2.9 → P2.10  (optimization — depends on P1)
  ↓
Rerun pipeline_audit.py at each checkpoint to verify improvement
```

---

## Success Criteria

| Metric | Current | After P0 | After P1 | After P2 | Target |
|---|---|---|---|---|---|
| Stage 0 WR | 34.3% | 42-46% | — | — | >45% |
| Stage 1 WR | 32.9% | — | 46-50% | — | >48% |
| Stage 2 WR | 33.0% | — | 46-50% | — | >48% |
| Stage 3 WR | — | — | — | 52-58% | >52% |
| Aggregate PF | 0.26 | 0.7-0.9 | 0.9-1.1 | 1.2-1.6 | >1.2 |
| DeterAlpha survival | 0% | — | >20% | >30% | >25% |
| RiskManager survival | 0-100% | — | 30-50% | 30-50% | 30-50% |

---

*Generated by Deep Code analysis of Alpha_v3 codebase on 2026-06-14.*

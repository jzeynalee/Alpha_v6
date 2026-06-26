# Alpha V3 — Plan v7 (Architectural Redesign)

*Supersedes v6 — frozen 2026-05-29*

---

## Why v7 exists

v6 was a **discovery plan**: find an edge first using simple hand-coded theses on raw data, freeze the architecture while doing so, and only A/B-test architectural changes once a thesis passed Phase A.

That sequence assumed the architecture was sound and the search problem was *finding signal in the data*. After running two theses (TREND_CONTINUATION and MEAN_REVERSION, both closed), the calibration retraining on enlarged LBank data, and the standalone-measurement preparation work, the operator's diagnosis changed:

> *"The strategy was implemented wrong."*

This isn't "the strategy underperforms." It's "the implementation does not match the design intent." That changes what the project is.

v7 records that diagnosis, sets a new sequence that fits it, and bounds the work so it doesn't sprawl.

---

## The diagnosis (recorded verbatim from the operator)

Three problems with the current architecture:

1. **"alpha_factory is designed to suppress the signals, but it is the first stage of the strategy and is expected to create them."**

2. **"deter_alpha.py is not implemented as was designed. If it is re-written in accordance with the original design, it will create so many alphas for the gatekeeping layer i.e. alpha_factory.py. It means we need to change the sequence of running."**

3. **"alpha_factory.py needs to be a bit optimistic rather than the current pessimistic performance. Obviously, it needs some measurements before implementation."**

### Independent confirmation of (1) and (3)

The strategy explainer document `alphav3_strategy_explained.md` (written 2026-05-28) described every alpha_factory layer in terms of *what it suppresses*. CSS multiplies alpha by ≤ 1. Entropy discount multiplies by ≤ 1. Execution adjustments subtract costs and multiply by fill probability and latency decay. Min-edge gate zeroes. EQS suspension zeroes. **No layer in the documented design can increase alpha.** The pipeline is six filters and one weak source (L4). Empirical symptom: "1 trade in 2005 bars" and Brier ≈ 0.25 across all L2 calibrators on next-bar direction.

The decision-model retraining on enlarged LBank data (2026-05-29) revealed **AUC 0.61-0.64** on L4 — the first quantitative evidence that one layer has signal the others don't. This validates the diagnosis: there *is* a generative component (L4), it's just buried inside a stack of filters that mostly attenuate it.

### Operator's intent for the corrected design

Sequence inversion:

```
Current:  features → alpha_factory (6 layers) → deter_alpha (gate) → trade
Intended: features → deter_alpha (generator) → alpha_factory (gatekeeper) → trade
```

`deter_alpha` becomes the *upstream signal generator* — produces many directional candidates derived from causal feature analysis. `alpha_factory` becomes the *downstream gatekeeper* — filters the abundant candidate stream for quality, executability, and risk.

---

## The five-step sequence

### Step 1 — Finish artifact state ✅ COMPLETE (2026-05-29)

All four ML artifacts trained on consistent LBank data, tagged `v2`:
- HMM (`hmm_v2.pkl`) — LBank 71,935 60m bars
- Calibration (`evidence_calibration_v2.pkl`) — LBank 100,001 5m bars, Brier ≈ 0.25 (no edge at H=5)
- CSS table (`causal_v2.parquet`) — LBank-trained via direct `train_causal_table()` call
- Decision models — six files for BTC/ETH × {5m, 15m, 60m}, Brier 0.236-0.252, AUC 0.61-0.64

### Step 2 — Three-arm decomposition measurement (baseline-before-rewrite)

Build a harness that runs three independent arms through the backtest engine on the LBank 60m data:

- **Arm A** — `alpha_factory` alone: trade when `proba_alpha ≥ 0.65`, ignore deter_alpha
- **Arm B** — `deter_alpha` alone (current implementation), fed real L4 proba
- **Arm C** — production AND-gate: both must agree

For each arm, report:
- Win rate
- Profit factor
- Trade frequency (trades per 1000 bars)
- Average R-multiple

Plus two cross-arm metrics:
- **Agreement rate**: fraction of bars where A and B agree on direction (or both produce no signal)
- **Per-arm trade frequency ratio**: A/B/C as a triple, showing where signal is lost

**This is the baseline measurement.** The same three arms will be run again after the rewrite to produce a clean before/after comparison.

The measurement uses the same backtest engine and triple-barrier conventions as the Phase A theses (TP=2×ATR, SL=1×ATR, timeout=48 bars, pessimistic intrabar tie-break). Walk-forward 5 folds, embargo=24. This keeps results directly comparable to the prior Phase A work.

### Step 3 — Plan the rewrite

After measurement data is in hand:

1. Re-read both `deter_alpha.py` and `alpha_factory.py` against the operator's intent
2. Write a focused rewrite plan: which functions change, which interfaces between the two halves change, which filter-layer tweaks are needed and *why* (specifically: which layer's measured signal-attenuation justifies the tweak)
3. Define success criteria for the rewrite (Step 5)
4. Define explicit budget (below)

The rewrite plan is a separate document, not v7. v7 only sets the frame.

### Step 4 — Execute the rewrite

Three-part scope:
- (a) Invert the sequence: deter_alpha runs first, produces candidate alpha stream; alpha_factory consumes the stream
- (b) Rewrite deter_alpha's internals to actually behave as a generator (currently it produces a single boolean per bar; it needs to produce many directional candidates per bar from the causal feature partition)
- (c) Adjust filter layers based on measurement data — only layers whose suppression was empirically large get touched

One commit per discrete change, smoke-tested independently, so any regression in Step 5's re-measurement is attributable to a specific change.

### Step 5 — Re-measure with same three arms

Same harness from Step 2, run against the rewritten code. Direct before/after comparison.

Success criteria (locked here, not negotiable after seeing results):
- **Generator check**: post-rewrite deter_alpha produces ≥ 5× more candidate signals than pre-rewrite, per 1000 bars
- **Throughput check**: at least 30% of deter_alpha's candidates survive to a tradeable signal through alpha_factory (vs. current near-zero throughput evidenced by "1 trade in 2005 bars")
- **Quality check**: combined system (Arm C equivalent) shows PF ≥ 1.0 on at least 4 of 5 walk-forward folds AND mean R-multiple ≥ 0 across folds

If all three criteria pass: rewrite succeeded, proceed to Step 6.
If generator check passes but throughput/quality fails: deter_alpha is generating but filters still throttle. Targeted filter-layer rework.
If generator check fails: deter_alpha rewrite didn't deliver. Stop, reassess design intent.

### Step 6 — Decide next direction (post-measurement)

Three outcomes:
- **Success on all three criteria** → proceed to A/B testing per v6 Phase B-G structure (carries over)
- **Partial success** → targeted iteration on the specific layer that's failing
- **Failure** → return to thesis discovery with Thesis #3 (volatility compression), having learned from the rewrite attempt

---

## Budget — and the rules for stopping

The single biggest risk of an architectural rewrite is scope creep. Bounds:

| Limit | Value | Rule |
|---|---|---|
| Wall-clock time for Step 4 (rewrite execution) | **2 calendar weeks** | If not complete by end of week 2, stop and reassess the whole approach |
| Discrete commits in Step 4 | **≤ 12** | Each commit is one bounded change; if a thirteenth feels needed, the design isn't bounded |
| Re-measurement iterations after Step 5 | **≤ 2** | If two measurement-then-tweak cycles don't pass success criteria, stop and reassess |
| Filter-layer tweaks in (c) | **≤ 4 distinct changes** | Each justified by measurement data showing material suppression by that layer |

**Hard stops:**
- If deter_alpha post-rewrite produces *fewer* candidates than pre-rewrite, the redesign is wrong — stop immediately
- If the Step 5 generator check fails, do not iterate on filter layers — go back to Step 3 and reassess design
- If at any point the operator says "this doesn't feel right," pause work and re-plan rather than push through

These are not soft limits. They exist because the surrounding evidence already tells us this is a difficult signal-extraction problem; an unbounded rewrite isn't going to make it easier.

---

## What changes from v6

| v6 commitment | v7 status |
|---|---|
| Architecture freeze until Phase A passes | **Lifted** — explicitly, with the diagnosis above as justification |
| Thesis-first discovery, run thesis scripts before architecture work | **Paused** — Thesis #3 (vol compression breakout) deferred to Step 6 |
| Two of three families closed (1 family-failure remaining) | **Preserved** — accounting carries over; if v7 fails at Step 5, returning to Thesis #3 consumes the last family-failure slot |
| DSR n_trials accounting (cumulative 3.5) | **Preserved** — the rewrite itself doesn't add n_trials; Step 5's measurement adds +1.0 (new architecture = new strategy variant for DSR purposes) |
| Information-decay diagnostic (planned for after a thesis passes) | **Brought forward** — Step 2's three-arm measurement *is* the information-decay diagnostic |
| Operational A/B framework for layer replacement | **Preserved** — used for the optional Step 6 follow-up if partial success |

What's intentionally preserved from v6: the discipline. No threshold softening after results. No mid-rewrite reframing. Pre-registered success criteria. Honest failure when criteria don't pass.

---

## What's needed from the operator before Step 2 starts

Two things only:

1. **Confirmation of the deter_alpha proba-input decision.** Earlier-confirmed answer: feed deter_alpha the real L4 proba for the Step 2 baseline. Confirmed again here because that decision shapes the harness code.

2. **Confirmation of the bar resolution for measurement.** Step 2 should run at 60m (matches all prior Phase A work and the operator's intended trading horizon). Confirmed here unless the operator overrides.

After confirmation, the harness build proceeds. Estimated effort: one day to build, smoke-test, and run; one day to interpret. Total to Step 2 completion: ~2 days.

---

## Project identity (unchanged from v6)

| Dimension | Value |
|---|---|
| Project name | Alpha V3 |
| Plan version | **v7** (frozen 2026-05-29) |
| Timeframe | 60m |
| Data source | Nobitex (live) + LBank (training, `v2`) |
| Asset class | BTCUSDT, ETHUSDT spot |
| Execution style | Directional event-driven entries |
| Label structure | Triple-barrier on ATR(14): TP=2×ATR, SL=1×ATR, timeout=48 bars |

Changing any of the above triggers Alpha V4 per the v6 identity criteria (carried over).

---

*One page of new direction, one page of guard-rails. The diagnosis is the operator's. The sequence and budget are the contract that keeps the rewrite from becoming an open-ended redesign project.*

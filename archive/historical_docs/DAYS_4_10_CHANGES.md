# Days 4-10 — HMSRE-Lite Integration & Measurement Suite

This delivery completes Sub-Phase 1A. It includes Day 4 integration into
features_engineering.py, Day 5 mandatory synthetic tests, Day 6 combined
replay/causality test, Day 7 quantitative gates script, Day 8-9 L4
retraining and comparison drivers, and the Day 10 sub-phase 1A writeup
template.

## Status

- **88/88 HMSRE tests pass** (Day 1: 40, Day 2: 16, Day 3: 24, Day 5: 6, Day 6: 2)
- **One real bug found and fixed during Day 5**: state machine parity
  bug (see "Critical fix" section below). This is exactly what Day 5
  synthetic tests are designed to catch.
- All script syntax validated. End-to-end Day 9 logic exercised on
  synthetic JSON inputs.

## Critical fix discovered during Day 5

The original state machine only matched ONE chronological parity of
the HH-HL-HH-HL pattern:

```python
# Old (broken):
if types == ("HIGH", "LOW", "HIGH", "LOW"):
    # check for uptrend
```

But a genuine alternating swing series cycles between two parities
as new swings arrive:
- After swings 4,5,6,7: types = (HIGH, LOW, HIGH, LOW)
- After swings 5,6,7,8: types = (LOW, HIGH, LOW, HIGH)
- Both represent the same uptrend if HHs and HLs are rising.

The original code silently classified half of all genuine trends as
RANGE. Day 5 synthetic uptrend test exposed this immediately — the
deterministic uptrend produced 0% UPTREND bars before the fix.

Fix: `_evaluate_candidate_state`, `_compute_trend_strength_up`, and
`_compute_trend_strength_down` in state_machine.py all now accept
both chronological parities of the pattern.

One Day 2 test (`test_range_when_no_trend_pattern`) was constructed
to test "lower HH (uptrend disqualifier) but lower LL". Under the
parity-fix, this is correctly DOWNTREND (both highs falling AND both
lows falling). The test was updated to use "lower HH but HIGHER HL"
which genuinely is mixed (neither uptrend nor downtrend).

## Files in this delivery

### Day 4 — integration

- **`patches/day4_features_engineering.patch.md`** — documented
  description of the edits to features_engineering.py
- **`patched_files/features_engineering.py`** — full applied version
  (syntax verified, ~2200 lines)

Five edits:
1. HMSRE import (with try/except for graceful import failure)
2. Three hint attributes added to `FeatureEngineerOptimized.__init__`
3. New `_compute_hmsre_columns_safe(df)` method on the class
4. `generate_features` modified to run HMSRE ONCE on the assembled
   feature dataframe AFTER batching (avoids chunk-seam artifacts)
5. `_update_incremental` Tier-1 fallback already handles HMSRE columns
   via the existing "copy from previous bar" logic — no explicit edit
   needed. Verified.

### Day 5 — mandatory synthetic tests

- **`src/features/hmsre/tests/test_day5_synthetic.py`** — 6 tests
  - test_pure_uptrend_produces_uptrend_majority
  - test_pure_downtrend_produces_downtrend_majority
  - test_pure_range_produces_range_majority
  - test_synthetic_outputs_are_float32
  - test_synthetic_outputs_length_matches_input
  - test_synthetic_trend_strength_nonzero_during_trend

Uses a stair-step uptrend/downtrend builder (`_build_60m_with_paired_15m`)
that constructs paired 60m and 15m series with anchored pivot bars so
MTF qualification can succeed.

### Day 6 — combined replay/causality test

- **`src/features/hmsre/tests/test_day6_replay_causality.py`** — 2 tests
  - test_combined_pipeline_replay_stability (random walk)
  - test_combined_pipeline_replay_with_explicit_uptrend (stair-step)

Tests that the entire pipeline (swing → MTF qualification → state
machine → overlap masking) is replay-stable: the value at any bar T
does not change when more bars are appended after T.

### Day 7 — quantitative gates

- **`scripts/day7_state_diagnostics.py`** — ~390 lines
  - Loads real CSV data (60m + 15m)
  - Runs the pipeline
  - Evaluates four pre-registered gates:
    1. State frequency in [5%, 80%] per state
    2. Mean run-length ≥ 3 bars per state
    3. Transition matrix diagonal ≥ 80%
    4. Visual sanity chart (matplotlib)
  - Writes `reports/day7_state_diagnostics.md`
  - Exit code 0 = all pass, 1 = any fail, 2 = data error

### Day 8 — L4 retraining driver

- **`scripts/retrain_decision_l4.py`** — ~330 lines
  - Loads 60m OHLCV, runs feature engineering (with or without HMSRE)
  - Trains LightGBM with locked hyperparameters
  - Chronological 70/30 train/OOS split
  - Computes Brier, AUC, accuracy, expectancy at p ∈ {0.50, 0.55, 0.60, 0.65}
  - Writes model artefact and metrics JSON
  - Run TWICE: once with `--include-hmsre false`, once with `true`

### Day 9 — comparison driver

- **`scripts/evaluate_l4_comparison.py`** — ~360 lines
  - Loads two metrics JSON files (baseline + treatment)
  - Evaluates PRE-REGISTERED criteria (locked thresholds in script)
  - Classifies failure mode (A/B/C) if FAIL
  - Writes `reports/day9_comparison.md`
  - Exit code 0 if 1A passes, 1 if fails

### Day 10 — writeup template

- **`reports/SUB_PHASE_1A_WRITEUP.md`** — template
  - Sections for engineering quality (done), Day 7 gates (TBD),
    Day 8-9 measurement (TBD), failure-mode classification (TBD),
    stop-or-go decision (TBD)
  - Operator fills in the TBD sections after running Days 7-9.

## How to run

```bash
# Day 7 — gates (must pass before Day 8)
python scripts/day7_state_diagnostics.py \
    --symbol BTCUSDT --data-version v2 --output-dir reports

# Day 8 — train both arms
python scripts/retrain_decision_l4.py \
    --symbol BTCUSDT --data-version v2 \
    --include-hmsre false \
    --output artefacts/l4_baseline.pkl

python scripts/retrain_decision_l4.py \
    --symbol BTCUSDT --data-version v2 \
    --include-hmsre true \
    --output artefacts/l4_with_hmsre.pkl

# Day 9 — compare
python scripts/evaluate_l4_comparison.py \
    --baseline artefacts/l4_baseline_metrics.json \
    --treatment artefacts/l4_with_hmsre_metrics.json \
    --output reports/day9_comparison.md
```

## Pre-registered criteria (LOCKED)

**Day 7 gates** (each must pass independently):
- Gate 1: state frequency in [5%, 80%]
- Gate 2: mean run length ≥ 3 bars
- Gate 3: transition diagonal ≥ 80%
- Gate 4: visual sanity (operator inspects)

**Day 9 PRIMARY**: Expectancy at p > 0.60 must improve by ≥ 0.05 R.

**Day 9 SECONDARY** (if PRIMARY borderline ±0.02 R):
- (a) Brier relative improvement ≥ 5%
- (b) AUC absolute improvement ≥ 0.01
- (c) Expectancy at p > 0.60 not degraded > 0.02 R

**Day 9 pass rule**: PRIMARY outright OR (borderline AND 2+ of {a,b,c}).

**Failure-mode classification** (only if FAIL):
- Mode A: HMSRE gain importance < 1% of total
- Mode B: high importance but no metric improved
- Mode C: borderline / mixed signals

**All failure modes recommend STOPPING** at 1A. 1B expansion only on
clean PRIMARY-or-secondary PASS.

## Hand-off

This delivery is now READY FOR AUDIT. The operator (Chabok) needs to:

1. Apply `patched_files/features_engineering.py` to the project
2. Update `offline_trainer.py` and live factory callers per
   `patches/day4_features_engineering.patch.md` Edit 6
3. Run pytest to confirm 88/88 tests pass after applying
4. Run Day 7 → Day 8 → Day 9 in sequence on real BTC data
5. Fill in the TBD sections of `reports/SUB_PHASE_1A_WRITEUP.md`
6. Make the go/no-go decision per Section 7 of the writeup

If any step fails, do not proceed to the next. Auditor sign-off
should come after the audit of this whole delivery, before applying.


# HMSRE-Lite — Phase 1 Design Document (v3)

**Status**: Auditor-approved (8.5/10), with three required changes incorporated.
**Replaces**: HMSRE-Lite v1 (draft) and v2 (post-auditor-review-1).
**Goal**: Add market-structure features to Alpha V3's L4 ML stack, measure
whether they improve trading-relevant metrics, expand only on positive result.
**Scope**: Sub-Phase 1A only. 1B and 1C are blocked until 1A demonstrates
measurable L4 improvement.

## v3 changelog (auditor review round 2)

The auditor scored v2 at 8.5/10 and required three specific changes before
sign-off. All three are incorporated below:

1. **Adaptive-k removed → fixed k=4** (auditor: *"We are not testing
   swing-detection research. Keep the structure engine as simple as
   possible. If 1A succeeds, adaptive-k becomes a Phase 1B/1C
   optimization."*). See §3.1.

2. **Pass criterion tightened**: was "ANY of three metrics improves"; now
   "expectancy improves OR two of three improve" (auditor: *"A
   calibration-only improvement should not trigger another phase. Your
   stated goal is trading performance, not label quality."*). See §4.4.

3. **Day-7 visual inspection replaced with quantitative gates** (auditor:
   *"A chart is useful. Statistics are better. State distribution,
   transition matrix, average duration — these should be explicit Day-7
   gates."*). See §8.1.

Auditor flagged Issue 2 (trend_strength may be over-engineered) but did not
block. User opted to keep the structural swing-range formula for 1A and
revisit only if feature importance ends up negligible. Documented in §7.

## v2 changelog (auditor review round 1) — for traceability

1. Fixed adaptive-k bug (later removed entirely in v3)
2. Removed NaN strategy → 0.0 for warmup/failure
3. Kept 1A scope strict (market_state + trend_strength only)
4. Visual inspection mandatory before retraining (now quantitative in v3)
5. LightGBM feature-importance recorded after every measurement
6. Causality invariant added to Swing dataclass

---

## 0. Reading guide

This document is the agreement between us, you, and the auditor about what
gets built and how. Three weeks of work depend on it being right.

The auditor's three priorities, in stated order:
1. **Causality** — no information from time T+1 used in any feature at time T
2. **Stability** — small data perturbations should not flip features
3. **Trading value** — features must measurably improve L4

Section 1 is causality enforcement (most important).
Section 2 is the integration architecture (most concrete).
Section 3 is the module-by-module design.
Section 4 is the measurement protocol with pre-registered success criteria.
Section 5 is what's deliberately out of scope.

`DECISION:` flags places where the spec was ambiguous and I made a specific
choice. `DEFERRED:` flags things explicitly out of Phase 1A.

---

## 1. Causality enforcement

The single biggest risk for HMSRE features is a subtle look-ahead bug. The
audit verified Verification A: bar-index mapping between 15m and 60m is safe
within the 2023-07-21 to 2026-05-28 overlap window (zero gaps, exact 4:1
ratio). That removes one class of look-ahead risk (timestamp drift).

The remaining causality risks are at swing-confirmation boundaries and at
MTF alignment. Both are addressed below.

### 1.1 Two timestamps per swing

Every swing carries two timestamps and two bar indices:

```python
@dataclass(frozen=True)
class Swing:
    timeframe: str          # "15" or "60"
    swing_type: str         # "HIGH" or "LOW"
    swing_bar_index: int    # The bar where the pivot price occurred
    confirm_bar_index: int  # The bar where we knew it was a pivot
    swing_time: pd.Timestamp
    confirm_time: pd.Timestamp
    price: float
    k_used: int             # Confirmation window (4 in Phase 1A)

    def __post_init__(self):
        # Causality invariant: cannot confirm a swing before it occurs
        assert self.confirm_bar_index >= self.swing_bar_index, (
            f"Causality violation: swing at bar {self.swing_bar_index} "
            f"cannot be confirmed at bar {self.confirm_bar_index}"
        )
        assert self.confirm_time >= self.swing_time, (
            f"Causality violation in timestamps: swing at {self.swing_time} "
            f"cannot be confirmed at {self.confirm_time}"
        )
        assert self.swing_type in ("HIGH", "LOW")
        assert self.k_used == 4, (
            f"Phase 1A uses fixed k=4; got k={self.k_used}"
        )
```

`DECISION`: the assertion `confirm_bar_index >= swing_bar_index` is a
causality invariant. Auditor explicitly requested it. It catches accidental
indexing mistakes early — the kind of bug that produces beautiful-looking
backtests that don't hold up.

**Critical rule**: the engine NEVER uses a swing at time T unless
`confirm_bar_index <= current_bar_index_on_engine_TF`. Not swing time.
Confirm time.

A 60m swing at bar 100 with k=3 has `confirm_bar_index = 103`. It is
invisible to the state machine until bar 103.

### 1.2 Causality at MTF alignment

When the 60m engine looks at the 15m confirmation TF, the rule is:

```python
def visible_15m_swings_at(t60_bar_idx):
    """Returns 15m swings whose confirm_bar_index implies they were
    known no later than the 60m bar at index t60_bar_idx."""
    # 60m bar t60_bar_idx ends at the end of (t60_bar_idx + 1) * 60 minutes.
    # The corresponding 15m bar index is (t60_bar_idx + 1) * 4 - 1.
    cutoff_15m = (t60_bar_idx + 1) * 4 - 1
    return [s for s in all_15m_swings if s.confirm_bar_index <= cutoff_15m]
```

**This is the function that catches MTF look-ahead.** A 15m swing confirmed
at 15m-bar 405 is visible to 60m-bar 101 (cutoff = 102*4 - 1 = 407 → 405 ≤ 407).
A 15m swing confirmed at 15m-bar 410 is **not** visible to 60m-bar 101.

`DECISION`: the engine's primary TF is 60m. The 15m TF is used only for
swing confirmation, not as a primary source of state transitions. Sub-Phase
1A produces features indexed by 60m bars.

### 1.3 Replay test (mandatory before 1A ships)

Run the engine on 60m bars [0:N], then [0:N+1], then [0:N+2]. Verify the
feature row at bar T never changes after first emission, for all N covering
the overlap window.

This is implemented as a unit test:

```python
def test_replay_causality():
    df_60m = load_overlap_60m()  # 25,000 bars
    df_15m = load_overlap_15m()  # 99,998 bars
    engine = HMSREEngine()

    label_history = {}
    # Run on growing prefixes (sample every 50 bars for speed)
    WARMUP = 200
    for n in range(WARMUP, len(df_60m), 50):
        features = engine.compute(df_60m.iloc[:n], df_15m.iloc[:n*4])
        for bar_idx, row in features.iloc[WARMUP:].iterrows():
            sig = (row["market_state"], row["trend_strength"])
            if bar_idx in label_history:
                assert label_history[bar_idx] == sig, (
                    f"Feature flip at bar {bar_idx}: "
                    f"was {label_history[bar_idx]}, now {sig}"
                )
            else:
                label_history[bar_idx] = sig
```

If this test fails, Sub-Phase 1A is not complete.

---

## 2. Integration architecture

This is concrete and based on the audit findings (Scenario A confirmed,
marker test PASS).

### 2.1 Module location

```
src/features/hmsre/
├── __init__.py           # public API: compute_hmsre_features()
├── swing_detector.py     # Layer 1 — adaptive-k swing detection
├── state_machine.py      # Layer 5 — HH/HL/LH/LL → state
├── engine.py             # Orchestration
└── tests/
    ├── test_swing_detector.py
    ├── test_state_machine.py
    ├── test_engine_synthetic.py    # Mandatory: synthetic trend/range
    └── test_replay_causality.py    # Mandatory: the big test
```

For 1A, only these modules. `events.py`, `compression.py`, `confidence.py`
are deferred to 1B / 1C.

### 2.2 Public API

```python
# src/features/hmsre/__init__.py
from .engine import compute_hmsre_features

def compute_hmsre_features(
    df: pd.DataFrame,
    *,
    symbol: str | None = None,
    primary_tf: str = "60",
    data_version: str = "v2",
) -> dict[str, np.ndarray]:
    """
    Compute HMSRE-Lite features for the given primary-TF OHLCV dataframe.

    Returns a dict of float32 arrays, one per bar in df. Currently emits:
      - market_state:     float32; -1.0 DOWN, 0.0 RANGE/WAITING, 1.0 UP
      - trend_strength:   float32; [0.0, 1.0]; 0.0 during WAITING

    Inputs:
      df:           Primary-TF OHLCV. Must have columns ['timestamp','open','high','low','close','volume'].
      symbol:       Used to locate the 15m confirmation CSV. If None, falls back to single-TF mode.
      primary_tf:   "60" for Sub-Phase 1A.
      data_version: For locating the 15m CSV via get_historical_data().

    Behavior:
      - For bars before warmup completes, returns 0.0 for all values.
      - Training/measurement uses the overlap window only (2023-07-21 to
        2026-05-28). Pre-overlap bars are excluded from the training and
        evaluation windows entirely, not represented as NaN.
      - All output arrays have length == len(df).
    """
```

### 2.3 Integration into calculate_indicators

Single change to `src/features/features_engineering.py`. Near the end of
`calculate_indicators()`, before the final `_sanitize_column_names()` call:

```python
# ── HMSRE-Lite feature injection (Sub-Phase 1A) ──────────────────────
# Adds: market_state, trend_strength
try:
    from src.features.hmsre import compute_hmsre_features
    # Symbol/data_version detection — see DECISION below
    hmsre_cols = compute_hmsre_features(
        df,
        symbol=getattr(self, '_symbol_hint', None),
        primary_tf=getattr(self, '_primary_tf_hint', "60"),
        data_version=getattr(self, '_data_version_hint', "v2"),
    )
    for name, values in hmsre_cols.items():
        df[name] = values.astype(np.float32)
except Exception:
    logger.exception("HMSRE feature computation failed — using 0.0 columns")
    df["market_state"] = np.float32(0.0)
    df["trend_strength"] = np.float32(0.0)
```

`DECISION`: `FeatureEngineerOptimized` currently doesn't know the symbol or
TF it's processing. The cleanest minimal change is to add three optional
attributes (`_symbol_hint`, `_primary_tf_hint`, `_data_version_hint`) that
callers set before invoking `calculate_indicators`. Both call sites that
matter (`decision_trainer.train_decision_model` and the live factory)
already know these values.

`DECISION`: HMSRE failures fall back to 0.0 columns (semantically "no
structural information") rather than NaN. This is consistent with the
warmup behavior — both states mean the same thing to the model, and we
avoid decision_trainer's NaN→column-median fill which would falsely imply
"typical structural state."

### 2.4 Why this won't break existing models

The integration adds 2 columns to a 168-column feature dataframe. Three
properties of the existing system make this safe:

1. **Models stored before this change** have a `columns` list of length 168.
   When loaded by `decision_layer`, it reads only those 168 columns by name
   from the new 170-column features_df. The new columns are silently ignored
   by the old model. Verified by reading `decision_layer.py:280-293`.

2. **Models retrained after this change** will include the 2 new columns
   in their `columns` list. They expect 170 columns. They'll fail cleanly
   if loaded by a code path that produces only 168 (logs error, returns 0
   alpha — verified at `decision_layer.py:281-290`).

3. **The dtype filter in decision_trainer** picks up the new columns
   automatically because we emit `float32` (verified by Verification B PASS).

### 2.5 Lookback requirements

HMSRE-Lite needs:
- 200 60m bars of warmup (matches existing indicators' typical warmup)
- + k=4 bars for the confirmation window
- = 204 60m bars minimum

`FeatureEngineerOptimized.MAX_LOOKBACK` is sized to the slowest existing
indicator. 204 bars is well below typical PSAR/regime windows. Almost
certainly no MAX_LOOKBACK bump needed.

`DECISION`: this is a quick check, not a design choice — will verify in
implementation. If MAX_LOOKBACK needs bumping, it's one line and a
recalculation of related buffer sizes.

---

## 3. Module design

### 3.1 swing_detector.py

**Purpose**: detect confirmed pivot highs and lows on a single TF, with
adaptive confirmation window k.

**Inputs**: OHLCV dataframe (single TF).

**Outputs**: list of `Swing` dataclass instances, each with the dual-timestamp
contract from Section 1.

**Confirmation window (fixed k=4)**:

For Sub-Phase 1A, swing confirmation uses a fixed window of `k=4` bars
on both sides. No adaptive-k.

```python
K_CONFIRM = 4
```

`DECISION`: per auditor v3 review — "We are not testing swing-detection
research. We are testing: does market structure help L4? Keep the structure
engine as simple as possible." Adaptive k was added complexity that could
become a confounding variable in the 1A measurement: if the experiment
passed or failed, we wouldn't know whether the structural-state idea was
responsible or whether the k tuning was the difference.

Fixed k=4 means:
- A swing high at bar i is confirmed at bar i+4 iff
  `high[i] > max(high[i-4:i])` AND `high[i] >= max(high[i+1:i+5])`
- Warmup is 4 bars (not 8) on the primary TF
- One fewer source of "did we tune this right?" questions
- If 1A succeeds, adaptive-k becomes a Phase 1B/1C optimization
- If 1A fails, we have a cleaner answer about whether the *concept*
  works, separable from whether the *parameters* were right

**Swing confirmation**:
```python
# A swing high at bar i is confirmed at bar i+k iff:
#   high[i] > max(high[i-k:i])      # k bars before
#   high[i] >= max(high[i+1:i+k+1]) # k bars after (>= handles equal highs)
```

`DECISION`: `>=` on the right side picks the earliest of equal highs. This
is the standard choice and matches what the auditor specified.

**ATR for adaptive k**: standard 14-period ATR on the TF being processed.

### 3.2 state_machine.py

**Purpose**: detect HH/HL and LH/LL sequences from a stream of confirmed swings,
emit market_state and trend_strength.

**States**: -1.0 (DOWN), 0.0 (RANGE/WAITING), 1.0 (UP).
`DECISION`: WAITING and RANGE both emit 0.0. Per the auditor: "use 0.0
for WAITING during warmup; never 99.0." This makes them indistinguishable
at the feature level but the trend_strength column carries the "no signal"
information (0.0 during WAITING).

**Trend detection** (entering UP from RANGE):
- Last 4 swings (in chronological order, regardless of which 60m bar they
  came from) are: HIGH, LOW, HIGH, LOW
- The HIGH-to-HIGH comparison shows the second HIGH > first HIGH
- The LOW-to-LOW comparison shows the second LOW > first LOW
- All four swings must be from the 60m TF (15m used as confirmation only;
  see §3.3)

**Symmetric for DOWN** (LH/LL sequence).

**RANGE**: when neither sequence is satisfied. Default state.

**Hysteresis**: state changes require 2 consecutive 60m bars confirming the
new state. During the confirmation window, the engine reports the prior state.

`DECISION`: hysteresis is 2 bars on the primary TF, not 3. Two reasons:
- 60m primary makes "3 bars confirm" mean 3 hours, which is a long lag
- Auditor's HMSRE v3 specified 3, but that was for 5m primary
- We can revisit if measurement shows the state is too noisy

**trend_strength**: a float in [0.0, 1.0] derived from the swing data:
```python
# When in UPTREND:
#   trend_strength = clip01((newest_HH - oldest_HL) / (ATR_60m * 10))
# When in DOWNTREND:
#   trend_strength = clip01((oldest_LH - newest_LL) / (ATR_60m * 10))
# When in RANGE or WAITING:
#   trend_strength = 0.0
```

`DECISION`: the divisor `ATR_60m * 10` normalizes to a roughly meaningful
scale. A trend with 10x ATR range maps to strength=1.0. This is a design
choice; we'll see if L4 finds it useful.

### 3.3 engine.py

**Purpose**: orchestrate the swing detector and state machine, handle MTF
confluence with 15m confirmation, return the feature dict.

**MTF confluence rule (15m → 60m)**:

`DECISION`: For Sub-Phase 1A, the 15m TF is used as a *confirmation filter*
only — a 60m swing is "qualified" iff there's a same-direction 15m swing
within ±15 minutes of the 60m swing time AND within ±0.25 × ATR_60m in price.

If 15m confirmation is absent or price differs too much, the 60m swing is
detected but tagged as "unqualified." Only qualified swings feed the state
machine.

This is a conservative version of the auditor's MTF idea. We get the
confluence requirement without building the full hierarchical scoring system
(deferred to potential 1C).

**Warmup**:
- First 204 bars: emit market_state=0.0, trend_strength=0.0 (WAITING)
- After warmup: emit actual values
- Training and evaluation windows are restricted to the overlap period
  (2023-07-21 to 2026-05-28). Pre-overlap 60m bars (the 46,935 bars from
  2018-03 to 2023-07) are simply not included in either window. No NaN
  emitted anywhere.

**Output**:
```python
return {
    "market_state":   np.array([...], dtype=np.float32),
    "trend_strength": np.array([...], dtype=np.float32),
}
```

---

## 4. Measurement protocol

Pre-registered before any HMSRE code is written. **These thresholds do not
change after measurement.**

### 4.1 Training window

- 60m bars: 2023-07-21 to 2026-05-28 (25,000 bars)
- 15m bars: same period (99,998 bars)
- Train/test split: 70/30 chronological
  - Train: ~17,500 bars (2023-07-21 to 2025-09-12 approx)
  - Test:  ~7,500 bars  (2025-09-12 to 2026-05-28 approx)

### 4.2 Driver script

`scripts/retrain_decision_l4.py` (new, ~150 lines):

```
python scripts/retrain_decision_l4.py \
    --symbol BTCUSDT --timeframe 60 \
    --data-version v2 \
    --artefact-tag baseline_<date>
```

Calls `train_decision_model` directly. Writes pickle with explicit tag.
Then with HMSRE code patched in:
```
python scripts/retrain_decision_l4.py \
    --symbol BTCUSDT --timeframe 60 \
    --data-version v2 \
    --artefact-tag with_hmsre_1a_<date>
```

### 4.3 Evaluation script

`scripts/evaluate_l4_comparison.py` (new, ~250 lines):

Loads both pickles. For each, runs `predict_proba` on the test window.
Computes:
- **Brier score** (calibration loss; lower is better)
- **AUC** (discrimination; higher is better)
- **Expectancy at threshold p**: for p in {0.55, 0.60, 0.65, 0.70},
  measures the average R-unit P&L of trades that would be taken if the
  L4 probability exceeds the threshold

**Also records, from the with-HMSRE model**:
- **LightGBM gain importance** for `market_state` and `trend_strength`
  (via `model.feature_importances_` with `importance_type='gain'`)
- **Split count** for both features (how often any tree used them)
- **Rank among all 170 features**

This addresses the two-different-failure-modes question. If features have
zero importance, the trees never used them — they carry no information.
If features have substantial importance but metrics didn't improve, the
existing 168 features already encode whatever signal HMSRE captures.

Reports the delta, the importance values, and an outcome verdict per the
criteria and decision tree below.

### 4.4 Pre-registered success criteria

**Sub-Phase 1A earns its place iff EITHER:**

(a) **Expectancy at threshold p=0.60 improves by ≥ 0.05 R-units**
    (a single-metric pass, anchored on the trading-decision metric), OR

(b) **At least TWO of the three metrics improve by their full magnitude
    thresholds:**
- Brier score improves by ≥ 5% relative
- AUC improves by ≥ 0.01 absolute
- Expectancy at threshold p=0.60 improves by ≥ 0.05 R-units

`DECISION`: per auditor v3 review — the original "ANY of three improves"
rule had a failure mode: Brier could improve in isolation while AUC and
expectancy stayed flat or worsened, technically triggering 1B even though
trading performance hadn't improved. The new rule prevents
calibration-only improvements from justifying expansion.

Magnitude thresholds (≥5% relative Brier, ≥0.01 absolute AUC,
≥0.05 R expectancy) are unchanged — these are what counts as "improves"
in both clauses. Smaller deltas don't count.

These criteria are strict. They reject "small marginal improvement that
doesn't justify added complexity." Trading-system orientation, not
research-output orientation.

### 4.5 What we DON'T measure in 1A

- Live deployment metrics
- Slippage / execution cost
- Multi-strategy combination behavior
- Sharpe ratio (not enough sample for stable estimate)
- Drawdown (same)

These all matter eventually but not in 1A. The single question 1A answers
is: *does adding market_state and trend_strength as features make L4's
predictions measurably better on a held-out window?*

### 4.6 Decision tree after measurement

```
1A passes (criterion (a) or (b) in §4.4 met)
  → Proceed to Sub-Phase 1B (events: bars_since_bos, bars_since_choch)
  → Repeat measurement after 1B

1A fails (neither criterion (a) nor (b) met)
  → Examine LightGBM feature importance to classify the failure mode:

  Failure Mode A — Importance ≈ 0 for both HMSRE features
    → Trees never used them. Structural state carries no predictive
      information that L4 can extract on its own.
    → CONCLUSION: stop HMSRE expansion. The structural-features
      hypothesis is not supported by the data on this asset/timeframe.
    → 1B and 1C are NOT justified.

  Failure Mode B — Importance significant but metrics unchanged
    → Trees used them heavily, but the existing 168 features already
      encode the same predictive signal. HMSRE doesn't add new
      information; it just provides another way to express what's
      already there.
    → CONCLUSION: also stop HMSRE expansion, but the reasoning is
      different. The signal is real; we just don't need more of it.
    → 1B and 1C are NOT justified.

  Failure Mode C — Importance moderate, some metrics close to threshold
    → Mixed signal. Possible candidates: feature scaling, hysteresis
      tuning, swing-detector parameters.
    → CONCLUSION: 1B is NOT automatically justified. Decide manually
      based on visual inspection and which metric was closest to
      passing. Document the reasoning before proceeding.
```

The rule remains: **no expansion to 1B without measurable 1A improvement.**
The feature-importance check helps distinguish "no signal exists" from
"signal exists but is redundant" when 1A fails.

---

## 5. What's deliberately NOT in Sub-Phase 1A

The auditor explicitly prohibited work on these until 1A demonstrates value:

- BOS (Break Of Structure) detection
- ChoCH (Change of Character) detection
- Compression detection (structural or otherwise)
- Confidence scoring (Layer 11 in the auditor's spec)
- 4h timeframe (we don't have the data)
- 1d timeframe (same)
- Full hierarchical structural scoring (Layer 2-4 in auditor's spec)
- Magnitude/persistence scoring beyond simple counting
- Multiple-asset HMSRE (ETH comes after BTC 1A confirms value)
- HMSRE features in calibration (Layer 4 stays on its 5 aggregates)
- HMSRE features in CSS table
- Incremental update path optimization (live trading accepts staleness; §6)
- Replacing Signal Factory or its labels
- Anything related to execution costs or live deployment

**If you find yourself wanting to add any of these to 1A, the answer is
"defer to 1B or 1C, only if 1A clears the criteria."**

---

## 6. Known limitations and accepted compromises

### 6.1 Live trading staleness (from audit Finding 2)

`_update_incremental` will stale HMSRE features by up to 11 bars during
live trading. For 60m primary, that's up to 11 hours.

**Phase 1A response**: accept it. Document it. Don't optimize.

State features change rarely (hours-to-days timescale). 11-bar staleness
≈ "no change" most of the time. If 1A measurement shows positive results
on offline retraining, we re-evaluate whether staleness hurts live
performance later.

### 6.2 Training window is 25K bars

About half the bars we had on Phase B (50K). Adequate for L4 measurement
but means the test window covers only ~10 months of recent BTC history.

**Phase 1A response**: proceed with 25K. If 1A clears criteria and we
need a longer test window for confidence in the result, backfill 15m
history then.

### 6.3 No 4h/1d confluence

The auditor's full HMSRE used 5 timeframes. Phase 1A uses 2 (60m + 15m).
This is a meaningful reduction.

**Phase 1A response**: accept. Adding higher TFs in 1C if results justify.

### 6.4 Hysteresis is short

2-bar hysteresis on 60m means 2-hour confirmation lag. This is fast for a
structural state engine.

**Phase 1A response**: this is a tunable parameter exposed via config.
Initial value 2 bars. Can be raised based on visual inspection or
measurement.

---

## 7. Open questions — resolved by auditor

These were the design choices flagged for review in v1. The auditor's
answers are now incorporated above; this section records the resolutions
for traceability.

**Q1 — Trend strength formula**: structural `(last_HH - first_HL) / (10*ATR)`
form (auditor: *"Keep the structural version. If you replace trend_strength
with `close > MA50`, you've essentially reinvented a trend indicator that
probably already correlates heavily with existing Alpha V3 features. You
want new information."*). Implemented in §3.2.

**Q2 — Extra features in 1A**: NO additional features. Strictly
`market_state` and `trend_strength` only (auditor: *"If you add extra
features now, attribution becomes impossible. Suppose performance
improves. Which feature caused it? No way to know."*). Implemented in §2.2.

**Q3 — NaN vs 0.0 for unavailable bars**: USE 0.0 (auditor: *"You are
not missing data. You are expressing: no confirmed structural information
exists yet. That's a state. Not missingness."*). Also: training/evaluation
windows are restricted to the overlap period, so pre-overlap bars are
excluded entirely, not represented at all. Implemented in §2.2, §2.3, §3.3.

**Q4 — Visual inspection**: MANDATORY before retraining (auditor: *"Imagine
replay test passes, code works, retraining runs — then you discover 95%
RANGE, 3% UP, 2% DOWN. The ML experiment becomes meaningless. A single
chart inspection often catches hysteresis problems, swing bugs,
confirmation-window mistakes in minutes."*). Reordered into the
implementation plan §8 so visual inspection happens on Day 7, before
retraining on Day 8. **v3 update**: replaced with quantitative gates
(§8.1); chart is now supplementary.

### Auditor's v3 Issue 2: trend_strength flagged but not blocking

The auditor flagged the structural trend_strength formula as potentially
over-engineered, suggesting simpler alternatives like
`bars_since_last_state_change`. The auditor did not block on this.

User decision: **keep the original swing-range formula for Sub-Phase 1A**.
Reasoning: preserves structural definition; if 1A measurement shows the
feature has zero LightGBM importance, the simpler alternative becomes
the natural revision direction for any retry. We learn more from the
structural version failing than from the simpler version failing.

Documented for traceability. Will revisit based on Day-9 feature-importance
output.

---

## 8. Implementation plan (Sub-Phase 1A)

Visual inspection moved before retraining (auditor's recommendation —
catches state-distribution pathologies early and saves days 8-9 if the
labels are broken).

| Day | Work |
|---|---|
| 1 | swing_detector.py + unit tests (synthetic monotonic series, equal highs, gaps) |
| 2 | state_machine.py + unit tests (synthetic HH/HL, LH/LL, transitions) |
| 3 | engine.py: MTF confluence, warmup, 0.0-during-WAITING, output assembly |
| 4 | Integration into features_engineering.py + the 3 _hint attributes |
| 5 | Synthetic tests (mandatory: trend → UPTREND, range → RANGE) |
| 6 | Replay/causality test (the mandatory big one) |
| 7 | **Day-7 quantitative gates + visual chart** — see §8.1 below. **STOP if any gate fails.** |
| 8 | scripts/retrain_decision_l4.py driver + run baseline retrain |
| 9 | scripts/evaluate_l4_comparison.py + with-HMSRE retrain + evaluation (including LightGBM gain importance for both HMSRE features) |
| 10 | Write up 1A result, apply pre-registered criteria + failure-mode classification, decide on 1B |

10 working days = ~2 calendar weeks. Honest estimate, not optimistic.

If anything turns out harder than expected (likely candidates: MTF
confluence edge cases at warmup, replay test exposing subtle look-ahead)
I'll flag it rather than push through silently.

### 8.1 Day-7 quantitative gates (mandatory)

Per auditor v3 review — visual inspection is necessary but not sufficient.
A chart is harder to falsify with statistics, so the Day-7 verification
report computes four diagnostic measures and applies explicit numeric
gates. If ANY gate fails, Sub-Phase 1A stops on Day 7 and we debug
before proceeding to retraining on Day 8.

**Gate 1 — State distribution (no state dominates)**
- Compute: percentage of bars in each state (UP / DOWN / RANGE)
- Pass: every state's frequency is in [5%, 80%]
- Stop conditions:
  - Any state > 80% (the engine isn't actually detecting structure)
  - Any state < 5% (the engine is producing a degenerate label rarely used)

**Gate 2 — Average state duration (states must persist)**
- Compute: mean duration in bars of each contiguous same-state run
- Pass: every state's mean duration ≥ 3 bars
- Stop condition:
  - Any state's mean duration < 3 bars → states are oscillating; hysteresis
    or swing-detector is buggy

**Gate 3 — Transition matrix (same-state persistence)**
- Compute: probability of state at bar t+1 given state at bar t,
  as a 3×3 matrix
- Pass: every diagonal entry (P[X→X]) ≥ 0.80
- Stop condition:
  - Any diagonal entry < 0.80 → too many bar-to-bar transitions

**Gate 4 — Visual chart (sanity check, not a numerical gate)**
- Produce: BTC 60m last 6 months chart with state-colored background
  (green=UP, red=DOWN, gray=RANGE) and 7-day-window overview at top
- Inspect: do UPTREND-colored periods correspond to visually trending
  price action? Do RANGE-colored periods correspond to sideways action?
- Stop condition (subjective): if the answer is obviously no — labels
  look uncorrelated with price action — stop and debug

**Day-7 deliverable**: a short report file (`day7_state_diagnostics.md`)
listing all four gates with pass/fail and the underlying numbers. If all
gates pass, proceed to Day 8. If any fails, fix and re-run Day 7
diagnostics — even if it adds a day or two before retraining.

---

## End of design doc.

All three auditor v3 changes incorporated (fixed k=4, tightened pass
criterion, quantitative Day-7 gates). Issue 2 (trend_strength formula)
flagged but not blocking; user opted to retain structural formula.

Plan is locked. Pending final auditor sign-off on v3, coding starts
Day 1 of Sub-Phase 1A: `swing_detector.py` with unit tests for synthetic
monotonic series, equal highs, and gap handling.

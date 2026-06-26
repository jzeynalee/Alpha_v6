# Alpha V3 — Research log

Per `docs/alphav3_consolidated_plan_v6.md`, this log is the binding accountability mechanism for the project. Every thesis test, every variant, every architectural A/B test is logged here. The log enforces what scripts cannot: experiment budget, cumulative DSR n_trials, project identity discipline, and failure morphology tracking.

---

## Project identity declaration

| Identity dimension | Value |
|---|---|
| Project name | Alpha V3 |
| Plan version | v6 (frozen 2026-05-27) |
| Timeframe | 60m |
| Data source | Nobitex (live) + LBank (training, `v2_lbank`) |
| Asset class | BTCUSDT, ETHUSDT spot |
| Execution style | Directional event-driven entries |
| Label structure | Triple-barrier on ATR(14): TP=2×ATR, SL=1×ATR, timeout=48 bars |
| Holding period | Sub-week (max 48 hours = 48 bars on 60m) |

Changing any of the above beyond the bounds specified in v6 §"Project identity criteria" formally ends Alpha V3 and starts a new branch.

---

## Failure morphology taxonomy

Added 2026-05-27 per external auditor's recommendation. Every FAILed thesis is classified across the following dimensions. Over time this corpus becomes evidence about which failure patterns repeat — more valuable than isolated PF numbers.

| Field | Possible values |
|---|---|
| Failure type | structural / parametric / sparse / asymmetric / mixed |
| Failure mechanism | text description of mechanism |
| Edge decay mode | none-observed / regime-instability / cost-erosion / sample-insufficiency |
| Parameter sensitivity suspected | low / medium / high |
| Retry justified | yes / no (with reasoning) |
| Family continuation allowed | yes / no |

---

## Phase A — Thesis Discovery

### Budget tracker

| Limit | Used | Remaining |
|---|---|---|
| Total theses + variants | 1 | 7 |
| Cumulative effective n_trials (DSR) | 1.0 | (no cap; informational) |
| Wall-clock weeks in Phase A | 0 (started 2026-05-27) | 6 |
| Clean failures | 1 | 2 before stop-rule re-evaluation |

---

### Thesis #1 — Pullback continuation (symmetric)

| Field | Value |
|---|---|
| Test date | 2026-05-27 |
| Status | **FAIL — family closed, no retry** |
| Family | TREND_CONTINUATION |
| Family-first? | Yes (n_trials += 1.0) |
| Cumulative effective n_trials at test time | 1.0 |
| Pre-registration | `scripts/test_pullback_thesis.py` (committed before run) |
| Data | `data/raw/v2_lbank/ohlcv_btcusdt_60.csv`, 50,001 bars |
| Edge taxonomy classification | Trend continuation (indicator/directional tier — known data-source limitation) |

**Specification** (locked):
- Trend filter: `close > SMA(200)` AND `SMA(50) > SMA(200)` (long), symmetric for short
- Pullback rule: `close ≤ 0.98 × rolling_max(close, 10)` (long), symmetric for short
- Trigger: `close > close.shift(1)` (long), symmetric for short
- Entry: next bar's open
- Triple-barrier: TP=2×ATR(14), SL=1×ATR(14), timeout=48 bars
- Walk-forward: 5 folds, embargo=24
- Pass criteria: expectancy ≥ 0.2R, PF ≥ 1.3/fold, ≥4/5 folds positive, ≥50 events/fold, DSR > 0

**Results**:

| Side | Events | Mean expR | Overall PF | Folds positive | Folds PF≥1.3 |
|---|---|---|---|---|---|
| Long | 578 | -0.140 | 0.898 | 2/5 | 1/5 |
| Short | 834 | -0.072 | 0.927 | 2/5 | 0/5 |
| Combined | 1412 | -0.073 | 0.915 | 1/5 | 0/5 |

**Per-fold detail (long)**: hit rates 20.4%, 30.4%, 30.4%, 35.5%, 12.1%. Required ≥33% for break-even on 2:1 geometry.

**Per-fold detail (short)**: hit rates 34.6%, 30.1%, 30.8%, 22.1%, 34.6%. Same break-even insufficiency.

**DSR**: not computed. Realized fold Sharpes are negative; DSR is necessarily negative. Result is FAIL regardless of DSR correction. (Future thesis tests must compute DSR explicitly per v6 §A.0.)

### Failure morphology

| Field | Value |
|---|---|
| Failure type | structural — negative expectancy across all three sides |
| Failure mechanism | hit rate insufficient for 2:1 TP/SL geometry across all five folds (not just some); the asymmetric outcome the thesis predicted is absent |
| Edge decay mode | regime-instability — SMA(50)>SMA(200) admits periods that are technically trending but practically rolling over (e.g., long fold 0: hit 20.4%, expR -0.39R during what was likely a stall-and-reverse window) |
| Parameter sensitivity suspected | medium — changing TP/SL geometry would test a different economic claim ("small drift beats costs"), not the original thesis ("continuation produces 2× wins") |
| Retry justified | **no** — the failure morphology is structural, not parametric. Reviewer framing: "retries should be reserved for cases where the economic behavior appears partially present but parameterization likely suppressed it. This does not look like that." |
| Family continuation allowed | **no — TREND_CONTINUATION family closed for this Phase A cycle** |

### Side-knowledge gained from this failure

Even failed theses produce knowledge. From Thesis #1:

1. **SMA(50)>SMA(200) is a weak trend filter on 60m crypto.** It admits regime transitions where the trend label persists but the underlying behavior has shifted. Future theses should use either price-action structure (HH/HL confirmation) or stronger trend definitions (slope-based, structural).

2. **Pure 2:1 TP/SL geometry on directional events is demanding.** The break-even hit rate of 33% is the floor; on this data the realized hit rate sits well below. Future theses with similar geometry need an event-detection rule that produces materially higher hit rates than 33%, not just statistical noise around it.

3. **Crypto 60m doesn't produce the textbook "trend persists after small pullback" behavior** in the LBank 2024-2026 window. This is consistent with crypto's structural tendency toward sweep-and-reclaim dynamics over smooth continuation.

### Output artifacts

- `data/research/pullback_thesis_2026-05-28T02-01-05.297907_00-00.json`
- `data/research/pullback_thesis_2026-05-28T02-01-05.297907_00-00.md`

### Decision

Pullback continuation closed. No retry. Family TREND_CONTINUATION closed for this Phase A cycle. Proceeding to Thesis #2 (Failed Mean Reversion → Continuation, MEAN_REVERSION family).

---

### Thesis #2 — Failed Mean Reversion → Continuation (PRE-REGISTERED, awaiting run)

| Field | Value |
|---|---|
| Pre-registration date | 2026-05-27 |
| Status | Pre-registered; ready to run |
| Family | MEAN_REVERSION (new family) |
| Family-first? | Yes (n_trials += 1.0) |
| Cumulative effective n_trials at test time | 2.0 (1.0 from pullback + 1.0 for this thesis) |
| Pre-registration file | `scripts/test_failed_mr_thesis.py` (to be committed before run) |
| Data | `data/raw/v2_lbank/ohlcv_btcusdt_60.csv`, 50,001 bars |
| Edge taxonomy classification | Mean reversion → continuation (indicator/directional tier — same OHLCV-only constraint) |

### Economic hypothesis

Crypto markets often exhibit:
- Liquidity sweeps below prior swing lows (long-side setup) or above prior swing highs (short-side setup)
- Failed countertrend participation: stops triggered, mean-reversion attempt fails
- Immediate reclaim of the swept level with strong rejection
- Forced continuation as trapped counter-trend participants cover

The hypothesis predicts that *failed mean-reversion attempts* produce more decisive directional continuation than smooth trend pullbacks (Thesis #1). Trapped participation is forced; trend persistence is optional.

### Event detection (locked pre-registration)

**Long-side event** (failed downward mean-reversion → upside continuation):

All conditions must hold on the same bar t:

1. **Swept low**: `low[t] < min(low[t-10..t-1])` — bar t made a new 10-bar low intraday
2. **Reclaim**: `close[t] > min(low[t-10..t-1])` — closed back above the prior 10-bar low (the swept level)
3. **Rejection strength** (per reviewer's refinement): `close[t] > low[t] + 0.25 × ATR(14)[t]` — close is at least 0.25 ATR above the bar's low, indicating active rejection not just a marginal reclaim
4. **Body dominance** (per reviewer's refinement): `|close[t] - open[t]| > 0.5 × (high[t] - low[t])` — bar body is more than half of its total range, confirming directional intent

Entry: next bar's open.

**Short-side event** (failed upward mean-reversion → downside continuation):

Symmetric mirror:

1. `high[t] > max(high[t-10..t-1])` — swept a new 10-bar high
2. `close[t] < max(high[t-10..t-1])` — closed back below the swept level
3. `close[t] < high[t] - 0.25 × ATR(14)[t]` — rejection from the sweep
4. `|close[t] - open[t]| > 0.5 × (high[t] - low[t])` — body dominance

Entry: next bar's open.

### Why these specifications (locked before run)

- **10-bar sweep window**: matches Thesis #1's lookback for consistency
- **0.25 ATR rejection floor** (reviewer's addition): filters out weak reclaim bars where price barely crossed the level. Per the reviewer: "Without this, weak dead-cat reclaim bars may contaminate the event set. You want actual rejection, not merely 'price crossed back above by one tick.'"
- **50% body dominance** (reviewer's addition): a candle with strong body relative to wicks indicates directional commitment; a doji-like reclaim is excluded
- **No trend filter**: deliberately omitted. The thesis is about *forced continuation from trapped participation*, not about confirming an existing trend. Adding a trend filter would conflate two hypotheses.

### Triple-barrier and walk-forward (held constant)

Identical to Thesis #1 — keep these constant across all Phase A theses so results are comparable.

- TP = 2 × ATR(14)
- SL = 1 × ATR(14)
- Timeout = 48 bars
- Walk-forward: 5 folds, embargo = 24
- Intrabar tie-breaking: pessimistic (SL wins on ambiguous bar)

### Pre-registered pass criteria (locked)

ALL must hold per side (long, short, combined):

- Mean expectancy across folds ≥ 0.2R
- Profit factor per fold ≥ 1.3
- At least 4 of 5 folds positive (mean R > 0)
- At least 50 events per fold
- DSR > 0 at effective n_trials = 2.0

A thesis that passes strict criteria but fails DSR ≥ 0 is treated as **FAIL**, not BORDERLINE (per v6 §A.0).

Tradeability floor also evaluated. Failure of tradeability floor produces LOW_TRADEABILITY classification, not advancement to Phase B.

### Expected challenges (honest pre-prediction)

The 4-condition event detection is much more restrictive than pullback's 3 conditions. Possible outcomes:

- **PASS** (~25% probability) — the more selective event detection produces higher-quality events with hit rate ≥ 40%, enough to clear 2:1 geometry
- **LOW_SAMPLE_REVIEW** (~30% probability) — events insufficient per fold (<50). If this happens, the thesis archive captures the result and Phase A continues.
- **BORDERLINE** (~10% probability) — fails one criterion (likely fold-consistency) but DSR > 0 and expectancy > 0
- **FAIL** clean (~35% probability) — the trapped-participation hypothesis isn't observable at this granularity on this data

Phase A may exit with no PASS at all. That is a valid outcome and the plan accounts for it.

### Output artifacts (will be generated on run)

- `data/research/failed_mr_thesis_<timestamp>.json`
- `data/research/failed_mr_thesis_<timestamp>.md`

### Decision after run

Per v6 §A.1 branching:
- PASS_BOTH → A.2 (information-decay diagnostic build), then Option 3 (full pipeline test on event bars)
- PASS_LONG_ONLY / PASS_SHORT_ONLY → same, restricted to passing side
- BORDERLINE / LOW_SAMPLE_REVIEW → archive, proceed to Thesis #3 (volatility compression breakout)
- FAIL clean → archive with failure morphology, proceed to Thesis #3

---

## Phase A — Stop rule tracker

| Failures so far | 1 (Thesis #1 — Pullback continuation, family closed) |
| Stop rule threshold | 3 cleanly-failed theses → re-evaluate at project level |
| Status | 2 remaining failures before project-level re-evaluation |

---

## Thesis #2 RESULT — Failed Mean Reversion → Continuation (FAIL, retry justified)

| Field | Value |
|---|---|
| Run date | 2026-05-28 |
| Status | **FAIL** — but retry-justified morphology (distinct from Thesis #1) |
| Cumulative effective n_trials after this test | 2.0 |

**Results**:

| Side | Events | Mean expR | Overall PF | Folds positive | Folds PF≥1.3 |
|---|---|---|---|---|---|
| Long | 759 | +0.035 | 1.015 | 4/5 | 0/5 |
| Short | 761 | +0.026 | 1.019 | 4/5 | 1/5 |
| Combined | 1520 | +0.031 | 1.017 | 4/5 | 0/5 |

**Per-fold hit rates**: long 30.8-35.8%, short 29.6-39.7%. Clustered at ~33-34%, right at the 2R break-even (33.3%).

### Failure morphology

| Field | Value |
|---|---|
| Failure type | **parametric** (not structural) — edge present but below threshold |
| Failure mechanism | hit rate (~33%) sits exactly at the 2R break-even; positive expectancy but too small to clear +0.2R bar |
| Edge decay mode | none-observed — 4/5 folds positive on all sides, shallow worst fold (-0.11R), no catastrophic collapse |
| Parameter sensitivity suspected | **high** — payoff geometry (2R) likely suppressing a real signal |
| Retry justified | **YES** — this is the textbook retry case per v6: "economic behavior partially present, parameterization suppressing it" |
| Family continuation allowed | yes — one retry permitted, then closed |

### Why this FAIL is different from Thesis #1

Thesis #1: negative expectancy, PF < 1, 1-2/5 folds positive, catastrophic worst fold (-0.54R) → **direction wrong**.

Thesis #2: positive expectancy, PF > 1, 4/5 folds positive, shallow worst fold (-0.11R) → **direction right, magnitude insufficient for geometry**.

The fold stability is the key signal. Noise-mined edges usually fail the catastrophic-fold test; Thesis #2 passes it. This is the first economically coherent (if sub-threshold) signal in the project.

### Output artifacts

- `data/research/failed_mr_thesis_2026-05-28T06-27-25.456754_00-00.json`
- `data/research/failed_mr_thesis_2026-05-28T06-27-25.456754_00-00.md`

---

### Thesis #2 RETRY — 3R geometry (PRE-REGISTERED, FINAL failed-MR variant)

| Field | Value |
|---|---|
| Pre-registration date | 2026-05-28 |
| Status | Pre-registered; ready to run |
| Family | MEAN_REVERSION (within-family variant) |
| Variant type | retry 1 of 1 (max allowed) |
| n_trials contribution | +1.5 (within-family variant per v6 thesis-family registry) |
| Cumulative effective n_trials at run | 3.5 (1.0 pullback + 1.0 failed-MR + 1.5 retry) |
| Pre-registration file | `scripts/test_failed_mr_thesis_retry.py` |

**The ONE change**: TP_ATR_MULT 2.0 → 3.0. Everything else identical and locked.

**Economic hypothesis change** (what makes this a legitimate retry, not a sweep):
- From: "failed mean-reversion predicts modest continuation" (2R)
- To: "failed mean-reversion predicts infrequent but EXTENDED directional expansion" (3R)

Break-even hit rate: 3R → 25% (vs 2R → 33.3%). If observed ~33% hit rate holds when the target widens, the same events become profitable.

**New diagnostic**: passive MAE/MFE excursion distributions. Interpretation only — never fed back into parameter choice. Answers: "do these events generate excursions large enough for 3R?"
- If median MFE < 2R → 3R is fantasy, retry geometrically doomed
- If MFE often ≥ 3R but exits failed at 2R → geometry was suppressing edge

**Pass criteria**: UNCHANGED (expectancy ≥ 0.2R, PF ≥ 1.3/fold, ≥4/5 folds positive, ≥50 events/fold).

**Binding commitment**: this is the final allowed failed-MR variant. If it fails, the MEAN_REVERSION family is closed permanently for this Phase A cycle, regardless of how close it comes. No further geometry tweaks, no threshold softening, no fold cherry-picking.

**Smoke tests**: 24/24 green (18 base + 6 MFE/MAE validation including TP=3R confirmation and excursion-bound correctness).

### Decision after run

- PASS_BOTH / PASS_one-side → proceed to A.2 (information-decay diagnostic), restricted to passing side(s)
- FAIL → MEAN_REVERSION family closed. 2nd clean thesis-level failure. Proceed to Thesis #3 (volatility compression breakout). One failure remaining before stop-rule project re-evaluation.

---

## Thesis #2 RETRY RESULT — FAIL, MEAN_REVERSION family CLOSED

| Field | Value |
|---|---|
| Run date | 2026-05-28 |
| Status | **FAIL — family closed permanently per pre-commitment** |
| Cumulative effective n_trials after this test | 3.5 |

**Results (3R geometry)**:

| Side | Events | Mean expR | Overall PF | Folds positive | Folds PF≥1.3 |
|---|---|---|---|---|---|
| Long | 759 | -0.005 | 0.985 | 2/5 | 0/5 |
| Short | 761 | +0.041 | 1.062 | 2/5 | 1/5 |
| Combined | 1520 | +0.020 | 1.024 | 3/5 | 0/5 |

**Comparison to Thesis #2 (2R)**: widening the target made the LONG side WORSE
(+0.035R → -0.005R) and the COMBINED fold-positivity worse (4/5 → 3/5). The 3R
hypothesis is falsified.

### The decisive MAE/MFE diagnostic

| Side | MFE median | MAE median | Frac MFE≥2R | Frac MFE≥3R |
|---|---|---|---|---|
| Long | +1.00R | -1.23R | 32.9% | 22.9% |
| Short | +1.01R | -1.21R | 34.6% | 25.8% |
| Combined | +1.00R | -1.23R | 33.8% | 24.3% |

**Median MFE = 1.00R < 2R → 3R target geometrically doomed** (per the
pre-registered reading guide). Only ~24% of trades ever reach 3R favorable
excursion. Critically, **median MAE (-1.23R) exceeds median MFE (+1.00R)** —
the typical event moves FURTHER against the thesis direction than for it. The
trapped-participation forced-continuation dynamic the thesis predicted is
absent: these are small-amplitude, slightly adverse-skewed events.

### Failure morphology (retry)

| Field | Value |
|---|---|
| Failure type | parametric retry of a parametric failure — now resolved to structural |
| Failure mechanism | events are small-amplitude (median MFE 1.00R) and slightly adverse-skewed (median MAE -1.23R); no exit geometry can produce 0.2R expectancy from this excursion distribution |
| Edge decay mode | none-observed at 2R; geometry-induced degradation at 3R (wider target converts small winners to stop-outs) |
| Parameter sensitivity suspected | RESOLVED — the MAE/MFE distribution is geometry-independent ground truth. No target placement rescues this. |
| Retry justified | already used (this was the retry) |
| Family continuation allowed | **NO — MEAN_REVERSION family closed permanently for this Phase A cycle** |

### Permanent knowledge gained

1. **Failed-MR events on 60m BTC/ETH are small-amplitude and roughly symmetric.** Median favorable excursion 1.00R, median adverse 1.23R. This is geometry-independent — it's a property of the events, not the barriers.

2. **The faint +0.03R edge at 2R was a small-favorable-move artifact**, not a suppressed large-move continuation effect. The MAE/MFE distribution proves there was no large effect to suppress.

3. **No exit geometry will rescue this signal.** This is the strongest possible form of "thesis closed" — not "we didn't find the right parameters" but "the events themselves don't have the shape the thesis requires."

### Output artifacts

- `data/research/failed_mr_retry_3R_2026-05-28T06-56-16.518081_00-00.json`
- `data/research/failed_mr_retry_3R_2026-05-28T06-56-16.518081_00-00.md`

---

## Updated Phase A — Stop rule tracker (post-retry)

| Field | Value |
|---|---|
| Thesis-level families closed | 2 (TREND_CONTINUATION, MEAN_REVERSION) |
| Stop rule threshold | 3 cleanly-failed theses → re-evaluate at project level |
| Status | **1 family-failure remaining before project-level re-evaluation** |
| Next thesis | #3 — Volatility compression breakout (VOLATILITY_EXPANSION family) |

## Updated budget tracker (post-retry)

| Limit | Used | Remaining |
|---|---|---|
| Total theses + variants | 3 (pullback, failed-MR 2R, failed-MR 3R) | 5 |
| Cumulative effective n_trials (DSR) | 3.5 | (no cap; informational) |
| Wall-clock weeks in Phase A | <1 | ~5 |
| Clean thesis-level failures | 2 (TREND_CONTINUATION, MEAN_REVERSION) | 1 before stop-rule re-evaluation |
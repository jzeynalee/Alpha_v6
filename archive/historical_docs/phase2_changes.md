# Phase 2 — Changes and Triage Guide

Per-module: what changed, why, and what to do if the result is bad.

---

## 2.0 — Hypothesis document

Phase 2 begins with `docs/alpha_theses.md`, a written commitment to
2-3 falsifiable trade hypotheses. The validator is strict because the
single biggest waste in financial research is engineering on a vague
hypothesis until you've sunk-cost yourself into committing to it.

**Triage on validator rejection:**

| Symptom | Cause | Fix |
|---|---|---|
| `found 0 hypotheses` | Template wasn't replaced | Fill in at least two `## Hypothesis N — <name>` sections |
| `placeholder text still present` | Template snippets left in | Search the doc for "Replace with", "Example:", and "_Example:_"; remove them |
| `Capacity classification has empty or unfilled fields` | The `[low-freq \| intraday \| ...]` bracket wasn't replaced | Pick one option; the bracketed alternatives must be deleted |
| `hypothesis name is still the placeholder` | Section heading still says `<Name your hypothesis here>` | Replace with the actual hypothesis name |
| `missing cross-notes section` | No `## Cross-hypothesis notes` heading | Add the section; describe hypothesis correlation and your conviction-leader |

---

## 2.1 — Triple-barrier labels

**Change:** replaced binary "close[t+H] > close[t]" with a 3-class
{-1, 0, +1} label based on whether the upper / lower ATR-anchored
barriers are touched within `max_horizon` bars.

**Why:** binary forward-return labels are noisy and ignore trade
realism. A bar that drifted up 0.1% over 24 bars labels as +1 even
though no trader would have captured the move. Triple-barrier labels
respect actual trade outcomes (TP, SL, time-out).

**Triage when labels look wrong:**

| Symptom | Cause | Fix |
|---|---|---|
| Distribution heavily skewed to 0 (>80% no-trade) | `tp_atr` or `sl_atr` too large for the volatility | Reduce both proportionally; check ATR is reasonable for the bar size |
| Distribution skewed to one direction (e.g. 60% +1) | Series is heavily trending in-sample | Use a more representative training window; or accept the asymmetry |
| Most labels are "unobserved" | `max_horizon` too large vs. dataset size | Shorten horizon, OR extend the dataset |

---

## 2.2 — Two-model meta-labelling

**Change:** instead of one multi-class model, train Model A
(direction) and Model B (take/skip given A's direction). Model B
sees Model A's probabilities as extra features.

**Why:** a single model balances two distinct tasks. Specialising
Model B for "when is A right vs. wrong" usually gives 5-15% improvement
on precision-at-recall vs. one combined model.

**Known limitation:** the standalone `meta_labeling.py` uses
in-sample Model A predictions to construct Model B's labels. With
high-capacity backends (default LightGBM) this is degenerate — Model A
memorises training, so meta-labels are all "A was right" and Model B
collapses. The pipeline detects this and falls back to A-alone.

The production fix is out-of-fold predictions, which is exactly what
the Phase 2.5 walk-forward CV provides. `run_phase2_pipeline.py` wires
this correctly: each fold trains Models A and B on the fold's train
set and predicts on the held-out test set, so meta-labels are
genuinely out-of-sample.

**Triage:**

| Symptom | Cause | Fix |
|---|---|---|
| `Model B training set has only one class` warning | A is memorising train | Lower A's `n_estimators` and `max_depth`; or always use PurgedWalkForward |
| `Model A picked no directional bars` raise | `tau_a` too high or labels too rare | Lower `tau_a`; check label distribution |
| Many predictions with reason='low_a_confidence' | `tau_a` is correctly filtering — this is fine | No action; the system is being appropriately selective |

---

## 2.3 — Feature selection 220 → 25

**Change:** new module. Selects 25 features from your 220-feature
matrix using MI ranking → Spearman correlation prune.

**Why not use the existing reduction mechanisms?**

- `feature_evidence.py` reduces 220 → 5 *regime-conditional probabilities* —
  different output, different consumer (the alpha factory's evidence
  layer, not a supervised classifier).
- `deter_alpha.py` `CausalRefit` selects by Granger + transfer entropy
  against the *regime* label — different criterion, different label.
- `decision_trainer.py` uses all 220 features without selection — which
  is exactly what Phase 2.3 fixes.

The supervised-ML feature selector is orthogonal to the existing
work. It serves the new Models A/B specifically.

**Triage:**

| Symptom | Cause | Fix |
|---|---|---|
| Final feature set has < 25 features | Heavy correlation prune ate the top-60 | Loosen `tau_corr` to 0.90 — or accept fewer features |
| Same family of indicators dominates (e.g. all RSI) | The 220 features are clustered around few signals | Add more diverse features (volume profile, microstructure, HTF alignment) — or lower `tau_corr` to force diversity |
| Selection is unstable across runs | MI estimator has stochasticity | Use a fixed `random_state` in `FeatureSelectionConfig` — already default |

---

## 2.4 — Probability calibration

**Change:** wrap fitted classifiers with isotonic or Platt
calibration; expose Brier / ECE diagnostics.

**Why:** raw tree-ensemble probabilities are over-confident at the
extremes. A model that outputs 0.85 should be right 85% of the time
on that subset; tree ensembles default to outputting 0.85 for things
that are right ~70% of the time. Without calibration, `tau_b` is
miscalibrated — you set 0.55 thinking it means 55% confidence but
the empirical hit rate at that threshold is 50%.

**sklearn 1.8 note:** `CalibratedClassifierCV(cv='prefit')` was
deprecated in sklearn 1.6 and removed in 1.8. The module uses
`FrozenEstimator` for sklearn ≥ 1.6 and falls back to the legacy
string for older installs.

**Triage:**

| Symptom | Cause | Fix |
|---|---|---|
| `brier_improved = False` | Base model is already well-calibrated, or validation set too small for isotonic | Try `method='sigmoid'`; or use a larger validation window |
| ECE > 0.10 even after calibration | Validation set doesn't span enough of [0, 1] | The base model is collapsed to extreme probabilities; investigate model capacity |
| `max_diagonal_gap_3_to_8 > 0.10` | Local miscalibration in the "actionable" probability range | Re-check the calibrator's monotonicity; use isotonic if Platt was used |

---

## 2.5 — Purged walk-forward CV

**Change:** new module. Expanding-window walk-forward with purge
(drop training observations whose label window reaches into test) and
embargo (skip `max_horizon + 1` bars after test before the next train).

**Why this is the most operationally critical Phase 2 module:** plain
`TimeSeriesSplit` from sklearn does NOT purge or embargo. Using it
silently biases every Phase 2 PF and Sharpe upward — the bias is
typically large (PF inflated by 0.2-0.5) and never detected until
live trading.

**Triage:**

| Symptom | Cause | Fix |
|---|---|---|
| `purged_count` is 0 across all folds | Purge logic broken — likely a refactor | Run `test_purged_count_equals_max_horizon` |
| Folds skipped due to `min_train_size` | First few folds have too-small training sets | Either lower `min_train_size` or use more data |
| `too_few_observations` raises | n < n_folds × 2 | Reduce `n_folds` or use more data |

---

## 2.6 — Four benchmarks

**Change:** new module. Buy-and-hold, EMA(20)/EMA(50), ATR breakout,
random-entry-same-exits. All four return identical-shape
`BenchmarkResult` objects so verifier comparisons are trivial.

**Why this is the single highest-leverage Phase 2 check:** if the
full Alpha V3 system cannot beat a 5-line EMA crossover after fees,
the architecture is not justified. Equally, if it cannot beat random
entries with the same exits by margin > 0.15 PF, all the alpha lives
in the exits — the direction model is essentially noise.

**Triage when the system fails to beat a benchmark:**

| Failing benchmark | Diagnostic |
|---|---|
| Buy & hold Sharpe | System has worse risk-adjusted returns than passive market exposure → either the entries are bad, the position sizing is wrong, or the strategy doesn't add over beta |
| EMA crossover PF | The system is no better than a 1960s trend-following rule → architecture overhead isn't paying for itself |
| ATR breakout PF | The system is no better than a naive volatility breakout → entries don't carry information beyond what volatility alone provides |
| Random-entry by margin > 0.15 | All the alpha is in the exits — replace the direction model with a simpler heuristic, save the engineering time |

---

## 2.7 — 14-criterion exit verifier

**Change:** new module. 14 checks across profitability, turnover,
stability, and benchmark beat. Each check has a specific failure
comment that diagnoses the cause.

**Why 14 checks?** Each one catches a specific overfit / spurious-edge
failure mode:

- 3 profitability checks: catch "no edge at all"
- 3 turnover checks: catch "micro-churn — edge < cost"
- 4 stability checks: catch "one trade / one month / one regime did all the work"
- 4 benchmark checks: catch "this is no better than a one-line strategy"

**Triage when many checks fail simultaneously:** the most likely
cause is `decision_trainer.py` being used instead of the new Phase 2
pipeline. Confirm `run_phase2_pipeline.py` is what's running.

---

## Common cross-cutting failure: "everything looks right but PF is 1.05"

Three checks to run in order:

1. **Did purge actually happen?** Print `wf.summary(n).purged_total`.
   If it's 0, leakage is happening and your PF is biased upward by ~0.2.
2. **Are the labels right?** Print `labels.distribution`. If one class
   is > 75% of the labeled bars, the model is mostly predicting "no
   trade" and trade volume is too low.
3. **Are the benchmarks beating you?** If random-same-exits has higher
   PF than your system, the direction model is anti-signal — invert
   it and re-run.

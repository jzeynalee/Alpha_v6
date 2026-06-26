# Sub-Phase 1A Result Writeup — HMSRE-Lite Integration

**Status**: TEMPLATE — fill in TBD sections after running Days 8-9 on real data.

---

## 1. Sub-Phase 1A summary

**Goal**: Determine whether the two HMSRE-Lite features (`market_state`,
`trend_strength`) materially improve the L4 decision model's
out-of-sample performance, using pre-registered measurement criteria.

**Outcome** (TBD): _PASS / FAIL_ — _classification mode if FAIL_

**Decision** (TBD): _Proceed to Sub-Phase 1B / Stop at 1A_

---

## 2. Pipeline summary

The HMSRE-Lite pipeline:

1. **Swing detection** (`swing_detector.py`) — k=4 confirmation,
   timestamp-based causality, outside-bar labeling.
2. **State machine** (`state_machine.py`) — last-4 swing pattern matching
   with chronological-parity awareness, 2-bar hysteresis, ATR-normalized
   trend_strength.
3. **MTF qualification** (`engine.py`) — 60m swings require a 15m partner
   within ±15 min and ±0.25·ATR; binary-search optimization.
4. **Overlap masking** — bars outside the 15m time coverage emit 0.0.
5. **Integration** (`features_engineering.py`) — runs once on the
   assembled feature dataframe after batching, via the
   `_compute_hmsre_columns_safe` helper.

Two columns added to the feature matrix: `market_state` (∈ {-1, 0, +1})
and `trend_strength` (∈ [0, 1]), both float32.

---

## 3. Engineering quality

### Test coverage

| Day | Tests | Status |
|---|---|---|
| Day 1 (swing detector) | 40 | ✅ |
| Day 2 (state machine, post-parity-fix) | 16 | ✅ |
| Day 3 (engine + MTF qualification) | 24 | ✅ |
| Day 5 (synthetic mandatory tests) | 6 | ✅ |
| Day 6 (combined replay/causality) | 2 | ✅ |
| **Total** | **88** | **✅ all pass** |

### Key bug fixes during build

1. **State machine parity bug** (caught by Day 5 synthetic test):
   the original state machine only matched one chronological parity
   of the HH-HL-HH-HL pattern, silently missing ~50% of genuine trends.
   Fixed to accept both parities of the last-4 swing alternation.

2. **15m alignment** (caught by Day 5 synthetic test):
   synthetic 15m bars need to anchor their high/low at the 60m
   timestamp to enable MTF qualification. Real production data is
   correctly aligned by construction (15m bars tile 60m bars exactly).

### Performance

- 25,000 60m bars + 100,000 15m bars: ~1.6 s (cold start)
- Bottleneck: 15m `detect_swings` (~1 s on 100K bars). All other stages
  are sub-100ms.

---

## 4. Day 7 gates (state quality on real data)

(Fill in from `reports/day7_state_diagnostics.md`)

| Gate | Threshold | Observed | Status |
|---|---|---|---|
| 1. State frequency | each in [5%, 80%] | TBD | TBD |
| 2. Mean run duration | ≥ 3 bars per state | TBD | TBD |
| 3. Transition diagonal | ≥ 80% | TBD | TBD |
| 4. Visual sanity | operator inspection | TBD | TBD |

**Day 7 verdict**: TBD

If any Day 7 gate fails, **Days 8-9 must not proceed** until the
underlying cause is identified. Common causes:
- Engine bug → fix code, re-run tests, re-run Day 7
- Real market regime missing structure → drop the experiment;
  HMSRE-Lite is not useful on this data window
- Data version issue → verify CSV integrity, regenerate if needed

---

## 5. Day 8-9 measurement results

### Pre-registered criteria (locked, do not adjust)

**PRIMARY**: Expectancy at p > 0.60 must improve by ≥ 0.05 R units.

**SECONDARY** (consulted only if PRIMARY is borderline within ±0.02 R):
- (a) Brier score relative improvement ≥ 5%
- (b) AUC absolute improvement ≥ 0.01
- (c) Expectancy at p > 0.60 must not degrade > 0.02 R

**Pass rule**: PRIMARY passes outright OR (PRIMARY borderline AND at
least 2 of {a, b, c} pass).

### Observed metrics

(Fill in from `reports/day9_comparison.md`)

| Metric | Baseline | Treatment (with HMSRE) | Δ |
|---|---|---|---|
| Brier (↓) | TBD | TBD | TBD |
| AUC (↑) | TBD | TBD | TBD |
| Expectancy @ p>0.60 (R) | TBD | TBD | TBD |
| HMSRE feature importance share | n/a | TBD | n/a |

### Primary criterion: TBD (PASS/FAIL)

### Secondary criteria: TBD (a: …, b: …, c: …)

### Overall verdict: TBD

---

## 6. Failure-mode classification (only if FAIL)

If 1A fails the pre-registered criteria, classify the failure mode:

### Mode A — HMSRE columns ignored

- Symptom: combined gain importance < 1% of total
- Interpretation: the existing feature set already captures whatever
  market_state and trend_strength encode. Adding them gives no signal.
- **Decision**: STOP. Do not proceed to 1B.
- **Reason**: heavier 1B features encode the same kind of structural
  information at higher cost. If the L4 model finds the lightweight
  version uninformative, the heavyweight version will be too.

### Mode B — High importance but redundant

- Symptom: HMSRE gain share > 1%, but no metric (primary or secondary)
  improved
- Interpretation: the model used HMSRE but didn't gain predictive power
  from it — likely because HMSRE is collinear with existing features.
- **Decision**: STOP. Do not proceed to 1B.
- **Reason**: 1B would add more collinear features without resolving
  the redundancy.

### Mode C — Borderline mixed signals

- Symptom: primary borderline, some secondaries pass and others fail
- Interpretation: HMSRE may help in some regimes and hurt in others.
  Without a clean win at 1A, expanding to 1B risks false positives.
- **Decision**: STOP. Do not proceed to 1B.
- **Reason**: a borderline 1A result with 25K bars is statistical noise
  more likely than a real effect. Production deployment needs cleaner
  evidence.

---

## 7. Stop-or-go decision

| Outcome | Decision | Next step |
|---|---|---|
| 1A PASS | PROCEED to 1B | Begin Sub-Phase 1B implementation |
| 1A FAIL — Mode A | STOP | Archive HMSRE-Lite code; do not deploy |
| 1A FAIL — Mode B | STOP | Same as Mode A |
| 1A FAIL — Mode C | STOP | Same as Mode A |

**My recommended decision** (TBD after seeing results): ____

---

## 8. Notes for future iterations

Regardless of 1A outcome, the following are useful artefacts:

1. **`scripts/day7_state_diagnostics.py`** — reusable gate-checker for
   any state-feature engine. The four pre-registered gates generalize.
2. **`scripts/retrain_decision_l4.py`** — clean A/B harness for any
   future feature comparison. Just toggle the include-flag.
3. **`scripts/evaluate_l4_comparison.py`** — locked-criteria comparison
   driver. Editable thresholds for future experiments.
4. **HMSRE-Lite test suite** (88 tests) — covers swing detection, state
   machine semantics, MTF qualification, replay causality, and synthetic
   gold cases. Reusable for any market-structure module.

If 1A fails, the swing detector and state machine themselves are still
sound engineering and could be repurposed (e.g., for a separate
risk-management feature or a different layer of the strategy). The
failure of 1A means *these features don't help the L4 decision model*,
not that the underlying engine is broken.

---

## 9. Appendix: how to run

```bash
# Day 7 — gates
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

All three scripts exit non-zero if their respective verdict is FAIL,
making them suitable for use as CI gates.

---

*— Sub-Phase 1A writeup template, generated Day 10*

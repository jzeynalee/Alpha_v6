# Scientific Correctness Report

### SC-001 — Critical — Confidence: High
**Evidence/location:** `src/validation/event_study.py`, `EventStudy._t_test`.

The function is labeled a one-sample t-test but computes a normal-approximation p-value with `erf`; it does not use Student-t degrees of freedom. At t=3 and 5 degrees of freedom, the one-sided p-values are about 0.0150 versus 0.00135 under the normal approximation. Published significance can therefore be overstated.

**Recommended fix/effort:** use a validated Student-t test and predeclare direction. Small.

### SC-002 — Critical — Confidence: High
**Evidence/location:** `EventStudy._permutation_test`.

The implementation samples arbitrary circular blocks and measures unconditional returns at arbitrary indices. It does not preserve the event-generation process or perform a clearly defined event-time permutation. The resulting null is not the stated event-study null.

**Recommended fix/effort:** define a valid event-label/time null and test it on synthetic data. Major.

### SC-003 — Major — Confidence: High
**Evidence/location:** `research_pipeline.py`, `_default_outlier_robustness` and `evaluate_regime_stability`.

Profit factor is approximated as `exp(mean_return * 252)`. This is not gross profits divided by gross losses. Stage gates can therefore classify hypotheses using a different metric from the reported PF.

**Recommended fix/effort:** calculate actual PF or rename the proxy. Moderate.

### SC-004 — Major — Confidence: High
**Evidence/location:** `research_pipeline.py`, `evaluate_bootstrap`.

The p-value is obtained from ordinary bootstrap samples of observed returns rather than a null-centered distribution. This is not a valid null p-value without additional justification.

**Recommended fix/effort:** use a null-centered test or report only a confidence interval. Moderate.

### SC-005 — Major — Confidence: High
**Evidence/location:** `event_study.py`, FDR block.

Benjamini-Hochberg is applied to five horizon p-values per trigger, but the broader family of triggers, assets, regimes, horizons, and experiments is not included.

**Recommended fix/effort:** define the multiplicity family before analysis and correct across it. Moderate.

### SC-006 — Major — Confidence: High
**Evidence/location:** `EventStudy.stability_analysis`.

Local window event indices are passed to `_compute_forward_returns`, which reads the study-global dataframe. Window results therefore use the wrong bars; a valid 300-bar synthetic input produced zero windows.

**Recommended fix/effort:** make dataframe/index ownership explicit. Moderate.

### SC-007 — Moderate — Confidence: Medium
Trigger features include the current bar close, while entry timing and fill convention are not specified. A causal close-to-next-open convention is not enforced.

**Recommended fix/effort:** specify signal availability and execution price. Small to moderate.

### SC-008 — Unable to determine — Confidence: Low
A complete OI/funding timestamp-alignment audit could not prove that every enrichment operation is causal across all raw datasets. More alignment evidence is required.

# Alpha_v6 Audit Action Plan

**Purpose:** convert the audit findings into a controlled remediation and revalidation sequence.

**Boundary:** this is a plan only. No source code, scripts, tests, data, or research conclusions are changed by this document.

## 1. Operating decision

Until the Critical gates below pass:

- Do not promote any mechanism or hypothesis.
- Do not publish new significance claims from `EventStudy`.
- Do not use M003/M004 sweep maxima as validation evidence.
- Do not treat M001-M005 confidence values as canonical.
- Do not use walk-forward, cross-asset, or rolling-stability results for acceptance decisions.

The existing `171 passed` test result is a software baseline, not a scientific clearance.

## 2. Execution order

The order is dependency-driven:

1. **Contain and preserve evidence**
2. **Repair statistical semantics**
3. **Repair leakage and dataframe isolation**
4. **Rebuild metrics and acceptance gates**
5. **Select one authoritative mechanism state model**
6. **Re-run affected experiments from clean provenance**
7. **Expand tests and documentation**
8. **Reassess mechanisms and issue a new audit closeout**

Do not reverse this order. Registry reconciliation before corrected calculations would merely formalize invalid evidence.

## 3. Phase 0 — Containment and evidence preservation

**Priority:** Critical  
**Owner surface:** repository/data/reports  
**Effort:** Small to moderate  
**Exit condition:** an immutable pre-remediation evidence snapshot exists.

### Actions

- Record the current commit, dirty-worktree diff, Python executable, dependency versions, test command, and current report hashes.
- Copy or hash all published discovery reports, evidence cards, mechanism registries, ladder state, M003/M004 sweep outputs, and relevant datasets.
- Mark M003/M004 sweep conclusions as `EXPLORATORY_UNCONFIRMED`; do not delete or rewrite historical artifacts.
- Record the current contradiction matrix for M001-M015, RP001-RP003, D/NEG identifiers, and confidence values.
- Freeze acceptance-level changes until the revalidation phase.

### Verification

- A clean checkout plus a separately preserved current-state manifest can be identified.
- Every published result has a file hash or an explicit `Unable to determine` provenance entry.
- No report uses “validated,” “verified,” or “production eligible” for evidence affected by the Critical findings.

## 4. Phase 1 — Statistical validity

**Priority:** Critical  
**Owner surface:** `src/validation/event_study.py`, `src/core/research_pipeline.py`  
**Effort:** Major  
**Prerequisite:** Phase 0.

### Actions

- Replace the normal approximation in `EventStudy._t_test` with a one-sided Student-t calculation using explicit degrees of freedom and direction.
- Define the null and alternative for reversal, continuation, and signed effects before implementation.
- Replace or formally redefine `_permutation_test`; preserve the event-study question, event count, horizon, overlap policy, and serial dependence assumptions.
- Correct `evaluate_bootstrap`: either use a null-centered bootstrap for a p-value or report a confidence interval without calling it a p-value.
- Replace `exp(mean_return * 252)` with actual gross-profit/gross-loss PF, or rename the metric and remove PF gate language.
- Define the multiple-testing family before rerunning experiments. Include the intended scope across triggers, horizons, assets, regimes, and experiments.
- Replace sentinel intervals such as `[-1, 1]` with explicit insufficient-sample status.

### Verification gates

- Analytic test cases agree with SciPy/reference calculations for Student-t p-values.
- Null simulations produce approximately calibrated Type-I error.
- Positive-signal simulations have power that increases with effect and sample size.
- Actual PF agrees with hand-calculated gross-profit/gross-loss examples.
- FDR tests verify the declared family, not only five per-trigger horizons.
- No affected experiment is reclassified until all gates pass.

## 5. Phase 2 — Leakage and data alignment

**Priority:** Critical  
**Owner surface:** `src/cv/walk_forward.py`, `src/validation/event_study.py`, `src/features/positioning_enricher.py`  
**Effort:** Major  
**Prerequisite:** Phase 0; can proceed in parallel with Phase 1 implementation but not with final revalidation.

### Actions

- Enforce `PurgedWalkForward.embargo` between prior test spans and subsequent training data.
- Add assertions for purge width, embargo gap, train/test disjointness, chronological ordering, and label-window boundaries.
- Make forward-return functions accept their dataframe explicitly; remove dependence on mutable study-global state.
- Repair `cross_asset()` so every asset computes features, events, and returns from its own dataframe.
- Repair `stability_analysis()` and boundary analysis so local indices remain local or are converted to global indices exactly once.
- Define signal availability and execution timing: current close, next open, or another explicit convention.
- Audit OI/funding/higher-timeframe alignment with timestamp-level synthetic tests, including missing timestamps, forward fill, resampling, and boundary bars.

### Verification gates

- A synthetic asset with a distinct price path produces distinct cross-asset results.
- A synthetic rolling series produces expected window results and nonzero windows where events exist.
- Embargo tests fail if the next training set enters the embargo interval.
- Every enriched feature timestamp is no later than the signal timestamp.
- No walk-forward or event-study result is accepted from the old implementation.

## 6. Phase 3 — Canonical mechanism and evidence state

**Priority:** Critical  
**Owner surface:** `mechanism_registry.py`, `mechanism_record.py`, `records/`, evidence cards, causal graph, ladder, project documents  
**Effort:** Major  
**Prerequisite:** Phases 1 and 2 must define valid evidence semantics.

### Actions

- Choose one authoritative mechanism object and state store. Treat the other representation as a compatibility layer or historical archive.
- Define lifecycle states: exploratory, candidate, replicated, rejected, validated, production-approved, retired.
- Define supersession rules for old and new boundaries, especially M003 lookback-5 versus lookback-10 and M004 candidate records.
- Implement or explicitly retire `MechanismRecord.confidence`, `.level`, and `.next_experiment`.
- Version the confidence formula and persist every component input, source experiment, p-value family, sample size, and calculation version.
- Prevent one experiment from contributing to multiple confidence components without explicit independence justification.
- Reconcile M001-M015, RP001-RP003, evidence cards, causal graph, ladder, and documents from the canonical state.
- Keep M006-M015 out of the validated catalog unless substantive evidence exists.

### Verification gates

- Every mechanism ID resolves to exactly one authoritative state.
- Rejected, candidate, and validated results are not conflated.
- Runtime confidence recomputes exactly from persisted inputs.
- Documentation and machine-readable state agree in a consistency test.
- M003/M004 statuses are supported by corrected, independent evidence rather than sweep maxima.

## 7. Phase 4 — Reproducible revalidation

**Priority:** Critical/Major  
**Owner surface:** experiment scripts, reports, datasets, provenance metadata  
**Effort:** Major  
**Prerequisite:** Phases 1-3.

### Revalidation order

1. Re-run null and synthetic statistical validation.
2. Re-run M001 affected event studies.
3. Re-run M002 higher-timeframe and null-model studies.
4. Re-run M003 from the original trigger before evaluating conditioning or lookback changes.
5. Re-run M004 with predeclared thresholds and adequate minimum sample sizes.
6. Re-run any result whose cross-asset, rolling, or walk-forward path used the affected implementations.
7. Recompute discovery, negative-evidence, mechanism, and ladder summaries.

### Required experiment manifest

Each run must record:

- repository commit and dirty diff status;
- Python executable and dependency versions;
- exact command and configuration;
- dataset paths, versions, date ranges, and hashes;
- random seeds and resampling methods;
- parameter grid declared before execution;
- train/validation/holdout boundaries;
- output paths and hashes;
- result status: exploratory, candidate, replicated, rejected, or validated.

### Verification gate

A discovery is reproducible only if a fresh environment can regenerate the result within declared numerical tolerances from the manifest and immutable inputs.

## 8. Phase 5 — Test and quality hardening

**Priority:** Major  
**Owner surface:** `tests/`, duplicated scripts, path/configuration modules  
**Effort:** Major  
**Prerequisite:** corrected behavior from Phases 1-4.

### Required test groups

- Student-t, bootstrap, permutation, FDR, and small-sample tests.
- Actual PF and regime-metric tests.
- Purge/embargo and chronological fold tests.
- Cross-asset, boundary, and stability dataframe-isolation tests.
- OI/funding causal alignment tests.
- Confidence formula, provenance, independence, and formula-version tests.
- Mechanism state transition and supersession tests.
- Equivalence tests for duplicated script calculations, or removal of the duplication.
- Documentation/registry consistency tests.
- Atomic persistence and concurrent-write behavior tests where state is shared.

### Exit condition

The complete suite passes, coverage is reported by scientific module, and every Critical finding has a regression test.

## 9. Phase 6 — Documentation closeout

**Priority:** Major  
**Owner surface:** `PROJECT_STATE.md`, `NEXT_ACTION.md`, `ARCHITECTURE.md`, `DISCOVERIES.md`, roadmap, reports  
**Effort:** Moderate  
**Prerequisite:** canonical state and revalidation.

### Actions

- Generate current-state counts and statuses from canonical machine-readable state.
- Mark historical reports as historical where their methods are superseded.
- Add method/version/provenance references to each discovery.
- Replace unsupported “verified,” “highly robust,” and “production” language with evidence-status language.
- Update stale `pytest.ini` comments and architecture transition wording.
- Document unresolved areas explicitly as `Unable to determine`.

## 10. Release gates

### Gate A — Scientific safety
No Critical statistical or leakage finding remains open. Corrected synthetic tests pass.

### Gate B — State integrity
One authoritative mechanism/evidence state exists and all derived documents agree with it.

### Gate C — Reproducibility
The required experiment manifest and dataset hashes exist for every retained published discovery.

### Gate D — Validation
Affected mechanisms have been rerun using corrected code, with independent confirmation where parameters were selected.

### Gate E — Audit closeout
A follow-up audit verifies the changed surfaces, records residual risk, and confirms that no source-level regression was introduced.

Until Gates A-D pass, the project should be treated as **research-invalid for acceptance and production decisions**, even though it remains executable and its existing regression suite passes.

## 11. Suggested first sprint

1. Freeze and hash current evidence.
2. Add failing regression tests for the embargo, cross-asset isolation, stability indexing, Student-t p-values, and actual PF semantics.
3. Agree on event-study null and multiple-testing family.
4. Agree on canonical mechanism state and lifecycle vocabulary.
5. Quarantine M003/M004 sweep conclusions.
6. Only then implement corrections and begin revalidation.

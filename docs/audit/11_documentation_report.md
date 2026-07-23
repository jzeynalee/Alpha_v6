# Documentation Report

### DOC-001 — Major — Confidence: High
`PROJECT_STATE.md` and `NEXT_ACTION.md` disagree on discovery counts, negative entries, acceptance levels, and RP002/RP003 statuses.

### DOC-002 — Major — Confidence: High
`ARCHITECTURE.md` presents `MechanismRecord` as the unifying object, but it is incomplete and the legacy registry remains operational.

### DOC-003 — Major — Confidence: High
`docs/methodology/event_study_method.md` claims a t-test, bootstrap, and permutation defense, but the implementation uses a normal approximation, non-null-centered bootstrap p-values, and an inadequately specified permutation null.

### DOC-004 — Moderate — Confidence: High
`NEXT_ACTION.md` describes RP002/RP003 as future work despite current 2026-07-23 M003/M004 reports and sweep artifacts.

### DOC-005 — Moderate — Confidence: High
`pytest.ini` comments reference Alpha_v3 and obsolete test names.

### DOC-006 — Moderate — Confidence: High
Discovery and negative-evidence documents lack explicit supersession/version metadata, so later candidate or negative results can coexist without precedence.

### DOC-007 — Major — Confidence: High
`docs/reports/20260723_m003_m004_sweep_report.md` uses “highly robust,” “verified,” and “extremely strong” for selected sweep maxima without documenting independent confirmation, multiplicity correction, or adequate sample-size criteria.

**Recommended fix:** generate current-state and discovery summaries from versioned machine-readable records and require report language tied to acceptance gates. Moderate to major effort.

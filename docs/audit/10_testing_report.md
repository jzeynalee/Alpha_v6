# Testing Report

### TEST-001 — Moderate — Confidence: High
The complete existing suite passes: `171 passed in 4.47s`. It does not establish correctness of untested scientific modules.

### TEST-002 — Major — Confidence: High
No direct tests were found for `src/validation/event_study.py`, `src/cv/walk_forward.py`, or `src/core/mechanism_record.py`. These are exactly the surfaces containing confirmed statistical, leakage, and stub defects.

### TEST-003 — Major — Confidence: High
`tests/test_research_pipeline.py` primarily seeds metrics into `HypothesisRecord` and tests orchestration. It does not recompute metrics from data or validate statistical semantics.

### TEST-004 — Moderate — Confidence: High
Evidence-ladder tests cover serialization and transitions, but not confidence provenance, formula versioning, multiplicity, or consistency with mechanism records.

### TEST-005 — Moderate — Confidence: High
No equivalence tests cover duplicated calculations in `evaluate_strategies.py` and `push_btc_mr_l2_pipeline.py`.

### TEST-006 — Moderate — Confidence: High
No synthetic tests assert that cross-asset and rolling-window calculations use their local dataframes, or that configured embargo gaps are respected.

### TEST-007 — Unable to determine — Confidence: Low
No coverage report was present, so exact line and branch coverage cannot be reported.

**Recommended minimum tests:** Student-t p-values, null bootstrap, event permutation, dataframe isolation, rolling windows, embargo gaps, actual PF, confidence provenance, and registry/documentation consistency.

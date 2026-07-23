# Repository Integrity Report

## Scope and evidence
Audit of `src/`, `scripts/`, `tests/`, configuration, data experiment artifacts, and research metadata in the current checkout. No source code was modified. The worktree was dirty at audit time, so current files include uncommitted M003/M004 changes.

## Findings

### RI-001 — Major — Confidence: High
**Evidence:** `scripts/evaluate_strategies.py` and `scripts/push_btc_mr_l2_pipeline.py` both define bootstrap, DSR, outlier, regime, classification, and related research calculations.

**Location/function:** duplicated helper functions in both scripts.

**Explanation/impact:** independent entry points can produce divergent results for nominally equivalent experiments. This violates the one-experiment-format architecture.

**Recommended fix/effort:** establish one calculation owner and add equivalence tests. Moderate.

### RI-002 — Major — Confidence: High
**Evidence:** `src/core/mechanism_registry.py` defines M001-M015; separate records exist under `src/core/records/`.

**Explanation/impact:** two catalogs can return different definitions, evidence, and state for the same mechanism ID. M006-M015 are registered but have no substantive evidence.

**Recommended fix/effort:** designate one authoritative registry and classify placeholders explicitly. Major.

### RI-003 — Major — Confidence: High
**Evidence:** `src/core/mechanism_record.py` contains `MechanismRecord.confidence`, `.level`, and `.next_experiment` stubs returning `0.0`, `L0`, and `{}`.

**Explanation/impact:** the advertised unified scientific object is incomplete and can silently report no evidence.

**Recommended fix/effort:** implement the contract or mark it non-authoritative. Moderate.

### RI-004 — Moderate — Confidence: Medium
**Evidence:** repeated helpers include `_load_csv`, `_load_state`, `_save_state`, `_warmup`, and `_validate_data_integrity` across modules.

**Explanation/impact:** intentional duplication cannot be separated from drift without semantic comparison. It is a maintenance and consistency risk.

**Recommended fix/effort:** compare implementations and centralize only equivalent behavior. Moderate.

### RI-005 — Moderate — Confidence: High
**Evidence:** `data/experiments/mechanism_evidence_cards.json` is not referenced by active Python code found by repository search, although documentation calls it machine-readable state.

**Explanation/impact:** it can become stale without runtime detection.

**Recommended fix/effort:** make it generated/validated or remove its active-state claim. Small to moderate.

### RI-006 — Unable to determine — Confidence: Low
Static import analysis found no cycles among 74 source modules, but dynamic optional-import cycles were not exhaustively exercised.

## Audit baseline
`pytest -q`: 171 passed. This is not evidence that untested scientific modules are correct.

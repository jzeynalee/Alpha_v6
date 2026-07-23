# Audit Action Plan Implementation Status

**Date:** 2026-07-23

## Completed in this implementation

### Statistical validity

- `EventStudy._t_test` now uses a one-sided Student-t survival function with `n - 1` degrees of freedom.
- Small-sample event-study bootstrap intervals now return explicit NaNs instead of the sentinel interval `[-1, 1]`.
- Event-study permutation testing now uses circular event-time shifts that preserve event count and relative spacing, with a finite-sample tail correction.
- Research-pipeline bootstrap p-values now resample returns centered under the zero-mean null.
- Research-pipeline PF calculations now use gross profits divided by gross losses.

### Leakage and dataframe isolation

- `PurgedWalkForward` now excludes the configured embargo interval following each previous test fold.
- Event-study forward returns accept an explicit dataframe.
- Cross-asset calculations use each asset's local dataframe.
- Rolling stability calculations use each window's local dataframe.

### Regression protection

Added `tests/test_audit_regressions.py` covering:

- Student-t p-value correctness;
- small-sample interval behavior;
- rolling stability window execution;
- walk-forward embargo exclusion;
- gross-profit/gross-loss PF;
- null-centered bootstrap behavior.

Validation result: `177 passed`.

## Not yet completed

The following action-plan phases remain open and must not be inferred as complete:

1. Canonical mechanism/evidence state reconciliation across the registry, records, evidence cards, causal graph, ladder, and documents.
2. M003/M004 clean independent revalidation after parameter selection.
3. Research-wide multiple-testing family definition and rerun.
4. Full OI/funding timestamp-causality audit.
5. Immutable experiment manifests with dataset/output hashes and environment capture.
6. Consolidation of duplicated script calculations.
7. Broad exception-policy and centralized-path cleanup.
8. Coverage measurement and tests for all remaining scientific public APIs.

## Current release decision

Alpha_v6 remains **blocked for scientific acceptance and production decisions** until the open phases are completed. The passing regression suite confirms software behavior for the addressed defects; it does not validate historical discoveries or mechanism confidence.

## Residual risks

- The event-study circular-shift null is a defined and testable improvement, but its suitability for every trigger family still requires domain review.
- Existing published results generated before these fixes remain invalidated or unconfirmed until rerun.
- Existing user changes in M003/M004-related files were preserved and were not reinterpreted by this implementation.

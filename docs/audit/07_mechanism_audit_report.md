# Mechanism Audit Report

### MECH-001 — Major — Confidence: High
M001 is documented as L4/0.691, has an evidence-card confidence of 0.69, and computes near 0.300 in the live registry. The same mechanism has incompatible acceptance and confidence states.

### MECH-002 — Major — Confidence: High
M002 registry effects report 12 bp ETH and 8 bp SOL, while `src/core/records/M002.py` records 15 bp and a 300-event sample. Effect provenance is not canonical.

### MECH-003 — Critical — Confidence: High
M003 is rejected in `PROJECT_STATE.md`, active in `causal_graph.py`, and `CANDIDATE_UNDER_VALIDATION` in `src/core/records/M003.py`.

### MECH-004 — Critical — Confidence: High
M003 stores a rejected lookback-5 boundary alongside an unvalidated lookback-10 candidate with effect 129.7 and sample size 1557. No supersession/acceptance rule establishes which result controls status.

### MECH-005 — Major — Confidence: High
M004 documentation describes BTC-specific findings, while `src/core/records/M004.py` stores ETH and BTC candidate effects, including 690.7 from only 16 observations. This is not sufficient evidence for the report's “extremely strong” wording.

### MECH-006 — Major — Confidence: High
M006-M015 have registry and report shells but no substantive evidence cards or validated runtime records. The M001-M015 catalog therefore overstates scientific coverage.

### MECH-007 — Major — Confidence: High
`docs/reports/20260723_m003_m004_sweep_report.md` labels best parameter-sweep configurations “highly robust” and “verified,” although the report selects maxima from the sweep, provides no independent holdout, and includes a 16-trade result. This is data-snooping/overclaiming evidence.

**Recommended remediation:** separate exploratory, candidate, replicated, rejected, and validated result namespaces; require independent confirmation and sample-size gates. Major effort.

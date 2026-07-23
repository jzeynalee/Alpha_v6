# Statistical Audit Report

### STA-001 — Critical — Confidence: High
`EventStudy._t_test` uses a normal approximation instead of Student-t. See Scientific Correctness SC-001.

### STA-002 — Critical — Confidence: High
`ResearchPipeline.evaluate_bootstrap` treats a non-null-centered bootstrap distribution as a p-value. See SC-004.

### STA-003 — Major — Confidence: High
Pipeline robustness and regime stages use `exp(mean_return * 252)` as PF. This is mathematically not profit factor.

### STA-004 — Major — Confidence: High
FDR correction covers horizons within a trigger, not the full research-search family.

### STA-005 — Moderate — Confidence: High
`EventStudy._bootstrap_ci` returns `[-1, 1]` for fewer than 10 observations, a sentinel interval that can look like a valid result and is not scale-aware.

### STA-006 — Moderate — Confidence: High
The block permutation path does not robustly validate that the data length supports `horizon + block_size`; small inputs can produce invalid random bounds.

### STA-007 — Moderate — Confidence: High
`metrics.monte_carlo_risk` samples trade returns iid with replacement, removing chronological dependence and clustered drawdowns.

### STA-008 — Moderate — Confidence: High
Monte Carlo CAGR uses `n_trades / 10` as elapsed time rather than timestamps or a strategy frequency.

### STA-009 — Unable to determine — Confidence: Low
No active implementation of Cohen's d or formal power estimation was found in the audited core paths. It may exist in uninspected generated artifacts, but this cannot be established.

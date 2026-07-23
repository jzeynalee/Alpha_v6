# Code Quality Report

### CQ-001 — Major — Confidence: High
Relative storage paths such as `data/experiments/...` are hard-coded in core modules. Running from a different working directory can read or write different state.

### CQ-002 — Major — Confidence: High
`research_pipeline.py` catches broad exceptions around thesis validation, paper trading, and production gates, then treats failures as skipped or falls back to weaker checks.

**Impact:** infrastructure failures can weaken scientific gates without failing the experiment.

### CQ-003 — Moderate — Confidence: High
`metrics.py` hard-codes 2025/2026 epoch split timestamps. Split configuration is not versioned or surfaced as experiment metadata.

### CQ-004 — Moderate — Confidence: High
Monte Carlo risk metrics use iid resampling and a trade-count time proxy, so drawdown and CAGR assumptions are not time-series faithful.

### CQ-005 — Moderate — Confidence: Medium
Evidence ladder documentation describes thread-safe reads but JSON writes use no lock or atomic replacement. Concurrent research processes can lose or corrupt state.

### CQ-006 — Minor — Confidence: High
`pytest.ini` comments refer to Alpha_v3 and obsolete test/module names.

### CQ-007 — Moderate — Confidence: Medium
Return-annotation coverage across `src`, `scripts`, and `tests` was approximately 54% by a simple syntactic scan. This is not itself a correctness defect, but public research APIs lack consistently explicit contracts.

**Unable to determine:** a complete performance/resource-leak audit was not possible without profiling long-running data and enrichment jobs.

# Prioritized Remediation Roadmap

## Critical

1. **Correct statistical significance calculations** — `event_study.py` normal-approximation t-test, invalid permutation null, and `research_pipeline.py` bootstrap p-value. **Effort:** Major.
2. **Fix validation leakage** — enforce `PurgedWalkForward` embargo and repair cross-asset/window dataframe isolation. **Effort:** Moderate.
3. **Resolve mechanism authority and lifecycle contradictions** — M001-M015 registry, records, evidence cards, causal graph, and project documents. **Effort:** Major.
4. **Quarantine overclaimed sweep results** — M003/M004 selected maxima require independent confirmation before “verified” status. **Effort:** Moderate.

## Major

5. Replace approximate PF with actual gross-profit/gross-loss calculation.
6. Implement or explicitly retire `MechanismRecord` confidence, level, and next-experiment stubs.
7. Define research-wide multiple-testing families and correction policy.
8. Add direct tests for event study, CV, mechanism records, script equivalence, and artifact consistency.
9. Add immutable experiment provenance: commit/diff, environment, dataset hashes, command, seeds, and output hashes.

## Moderate

10. Consolidate duplicated statistical helpers in scripts.
11. Route state paths through the central configuration/path abstraction.
12. Make Monte Carlo assumptions explicit and use time/dependence-aware resampling.
13. Generate documentation from one machine-readable state source.
14. Add sample-size statuses instead of sentinel confidence intervals.
15. Replace broad exception fallbacks with explicit unavailable/failed gate states.

## Minor

16. Update stale `pytest.ini` comments.
17. Improve public return type contracts.
18. Document event-study signal timing and execution assumptions.

## Final risk assessment

Alpha_v6 is operational and its existing test suite passes, but the repository is **not currently scientifically reliable as a unified research system**. The highest risks are invalid p-values, unenforced embargo, broken dataframe isolation in event-study validation, non-PF robustness gates, confidence-state divergence, and selected-parameter overclaiming. No code or test files were modified during this audit.

## Explicit limits

Dynamic import cycles were not confirmed by static analysis. Complete OI/funding timestamp causality, formal power calculations outside active Python modules, full branch coverage, and long-running resource behavior remain **Unable to determine** from the current evidence.

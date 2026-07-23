# Reproducibility Report

### REP-001 — Critical — Confidence: High
The audit checkout was dirty: modified reports and source files plus untracked M003/M004 outputs and `src/features/m003b_conditioning.py`. Current reports cannot be attributed to the last commit alone.

### REP-002 — Major — Confidence: High
`PROJECT_STATE.md` and `NEXT_ACTION.md` publish incompatible discovery counts and research statuses. Published state cannot be regenerated from one current source.

### REP-003 — Major — Confidence: High
Discovery entries name experiment IDs, but do not consistently link exact command, code revision, dataset version/hash, seed, and output artifact. The chain Discovery -> Experiment -> Dataset -> Code -> Result is incomplete.

### REP-004 — Major — Confidence: High
`mechanism_registry.json` and `mechanism_evidence_cards.json` overlap but disagree on effect summaries and confidence. No canonical-artifact rule is encoded.

### REP-005 — Moderate — Confidence: High
Some methods use fixed seeds, but seed handling is local to methods and not recorded uniformly in experiment metadata.

### REP-006 — Unable to determine — Confidence: Low
No complete dataset hash manifest or dependency lock artifact was found in the audited root. Exact historical data reproducibility cannot be proven from filenames/timestamps alone.

**Recommended remediation:** require commit/diff, environment, dataset hashes, commands, seeds, and output hashes for every published result. Major effort.

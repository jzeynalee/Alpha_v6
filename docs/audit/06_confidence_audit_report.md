# Confidence Audit Report

### CA-001 — Major — Confidence: High
**Evidence/location:** `src/core/mechanism_registry.py`, `Mechanism.confidence_score`.

The formula depends on replication, walk-forward, parameter plateau, null-model, and confirmation-period fields, but `mechanism_registry.json` does not persist the expected component fields consistently. Runtime values therefore fall back to defaults.

**Impact:** documented confidence is not reproducible from persisted state.

### CA-002 — Major — Confidence: High
The same M001-M005 mechanisms have incompatible confidence values across `PROJECT_STATE.md`, `mechanism_registry.json`, and `mechanism_evidence_cards.json`. Runtime confidence was approximately 0.300, 0.179, 0.168, 0.171, and 0.171 respectively under the loaded registry.

### CA-003 — Major — Confidence: High
Significance is `1 - min(p_values)`, so one best p-value controls the component across all stored effects. This permits confidence inflation from selective horizons/assets.

### CA-004 — Major — Confidence: High
OOS evidence is binary: a nonempty `confirmation_period` contributes full credit without validating a linked result, sample, or pass criterion.

### CA-005 — Moderate — Confidence: High
Parameter plateau and OOS are additive and can be sourced from the same confirmation experiment. There is no provenance-based double-count prevention.

### CA-006 — Major — Confidence: High
`MechanismRecord.confidence` always returns 0.0 and `.level` always returns L0, conflicting with the registry formula and published states.

**Recommended remediation:** store immutable component inputs, formula version, experiment IDs, multiplicity treatment, and independence rules in one authoritative record. Major effort.

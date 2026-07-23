# Architecture Consistency Report

### AC-001 — Major — Confidence: High
**Evidence:** `ARCHITECTURE.md` describes migration to a unified `MechanismRecord`, while runtime research state is still loaded by `src/core/mechanism_registry.py` and `mechanism_registry.json`.

**Explanation/impact:** target architecture and current architecture are not separated. Callers cannot identify the authoritative mechanism API.

**Recommended fix/effort:** document current versus target state and define a migration boundary. Major.

### AC-002 — Major — Confidence: High
**Evidence:** `ARCHITECTURE.md` says `ExperimentManager` is the only experiment format, while multiple scripts directly run research calculations and write outputs.

**Explanation/impact:** experiment lifecycle, metrics, and provenance differ by entry point.

**Recommended fix/effort:** declare supported entry points and route all published experiments through one provenance contract. Moderate.

### AC-003 — Major — Confidence: High
**Evidence:** the architecture prohibits hard-coded data paths, but relative `Path("data/...")` storage occurs in `mechanism_registry.py`, `evidence_ladder.py`, and `research_pipeline.py`.

**Explanation/impact:** behavior changes with current working directory and can read/write multiple state locations.

**Recommended fix/effort:** use the central path layer. Moderate.

### AC-004 — Major — Confidence: High
**Evidence:** `PROJECT_STATE.md` reports RP002 active/RP003 rejected and 26 discoveries; `NEXT_ACTION.md` reports RP002 not started/RP003 in progress and 19 discoveries; `causal_graph.py` defines both RP002 and RP003 as active.

**Explanation/impact:** governing state is contradictory.

**Recommended fix/effort:** generate state summaries from one authoritative store. Moderate.

### AC-005 — Major — Confidence: High
**Evidence:** documentation claims M001=L4 and M002=L3, while the live registry defaults to acceptance level 0 and persisted registry data lacks the documented confidence components.

**Explanation/impact:** eligibility and promotion can depend on which representation is read.

**Recommended fix/effort:** reconcile state stores and version the schema. Moderate.

### AC-006 — Major — Confidence: High
**Evidence:** `research_pipeline.py` defaults to stages 1-8 and caps automated promotion at L4; stages 9-10 are omitted by default.

**Explanation/impact:** the documented ten-stage lifecycle is not the default executable lifecycle and cannot automatically establish L5/L6.

**Recommended fix/effort:** distinguish research mode from production mode explicitly. Moderate.

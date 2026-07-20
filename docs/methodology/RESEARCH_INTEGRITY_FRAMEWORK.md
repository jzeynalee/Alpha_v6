# Research Integrity Framework

This document outlines the scientific audit dimensions required to evolve Alpha_v6 into a long-lived, reproducible research platform.

## 1. Audit Dimensions (Research Integrity Score)

| Dimension | Definition | Target Score |
|-----------|------------|--------------:|
| Reproducibility | Determinism and parity across environments. | 0.95 |
| Traceability | Provenance from result back to dataset/seed/revision. | 0.90 |
| Statistical Validity | Multiple-testing correction, proper evidence weighting. | 0.78 |
| Documentation | Accuracy of architecture and methodology docs. | 0.92 |
| Data Integrity | Integrity of OHLCV/Funding/OI ingestion. | 0.97 |
| Architecture | Consistency of the Hypothesis → Mechanism → Strategy pipeline. | 0.94 |
| Scientific Auditability | Ability to perform independent replication of claims. | 0.86 |

**Overall Research Integrity Score:** (Weighted Average)

## 2. Missing Audit Dimensions (To be Implemented)

1. **Research-State Consistency:** Automated checks ensuring synchronicity across Hypothesis, Mechanism, Evidence Card, Discovery, Confidence, Acceptance Level, Research Program, and Strategy.
2. **Provenance Audit:** Mandatory metadata for every reported effect: Dataset, Code Revision, Experiment Spec, Random Seed, Statistical Method, Discovery ID.
3. **Boundary Versioning:** Immutable identities for discovered mechanisms (e.g., `M001_B01`).
4. **Experiment Registry Consistency:** Handling of duplicate experiments (merge, overwrite, duplicate, or average?).
5. **Negative Evidence Integrity:** Ensuring failed experiments reduce confidence levels appropriately.
6. **Mechanism Independence:** Distinguishing between unique mechanisms and variants of existing ones.
7. **Determinism Testing:** Explicit verification that (data + seed + config) = constant output.

## 3. Implementation Priorities

- **P0:** Implement Experiment-Level Multiple-Testing Correction.
- **P1:** Establish provenance and boundary versioning infrastructure.
- **P2:** Reconcile M002 evidence-mismatch.
- **P3:** Build Research Integrity Dashboard (for score calculation).

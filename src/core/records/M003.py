from src.core.mechanism_record import MechanismRecord, BoundaryModel, EvidenceCard
from typing import Dict

def get_m003_record() -> MechanismRecord:
    return MechanismRecord(
        metadata={
            "mechanism_id": "M003",
            "version": 1,
            "created": "2026-07-21",
            "last_updated": "2026-07-21"
        },
        description="Position Unwind (Open Interest vs Price divergence).",
        causal_chain=["OI exhaustion", "Profit taking"],
        scientific_rationale="Divergence indicates lack of new capital.",
        falsification_criteria=["OI increases with price"],
        boundary_models={},
        evidence={},
        validation_history=["NEG-001"],
        known_interactions={},
        known_failure_domains=["Trending regimes"]
    )

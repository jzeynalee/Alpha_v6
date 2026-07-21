from src.core.mechanism_record import MechanismRecord, BoundaryModel, EvidenceCard
from typing import Dict

def get_m004_record() -> MechanismRecord:
    return MechanismRecord(
        metadata={
            "mechanism_id": "M004",
            "version": 1,
            "created": "2026-07-21",
            "last_updated": "2026-07-21"
        },
        description="Funding Rotation.",
        causal_chain=["Structural arbitrage", "Capital rotation"],
        scientific_rationale="Funding cost equalization.",
        falsification_criteria=[],
        boundary_models={},
        evidence={},
        validation_history=[],
        known_interactions={"amplifies": "M001"},
        known_failure_domains=[]
    )

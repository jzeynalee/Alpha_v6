from src.core.mechanism_record import MechanismRecord, BoundaryModel, EvidenceCard
from typing import Dict

def get_m005_record() -> MechanismRecord:
    return MechanismRecord(
        metadata={
            "mechanism_id": "M005",
            "version": 1,
            "created": "2026-07-21",
            "last_updated": "2026-07-21"
        },
        description="Volatility Compression → Expansion.",
        causal_chain=["Volatility mean reversion", "Catalyst release"],
        scientific_rationale="Pent-up demand/supply release.",
        falsification_criteria=["Volatility fails to expand"],
        boundary_models={},
        evidence={},
        validation_history=["NEG-002"],
        known_interactions={},
        known_failure_domains=["Trending regimes"]
    )

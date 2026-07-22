from src.core.mechanism_record import MechanismRecord, BoundaryModel, EvidenceCard
from typing import Dict

def get_m013_record() -> MechanismRecord:
    return MechanismRecord(
        metadata={'mechanism_id': 'M013', 'version': 1},
        description='M013 auto-generated.',
        causal_chain=[],
        scientific_rationale='Pending analysis.',
        falsification_criteria=['Performance fails baseline'],
        boundary_models={},
        evidence={},
        validation_history=[],
        known_interactions={},
        known_failure_domains=[]
    )

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

@dataclass
class BoundaryModel:
    model_id: str
    asset: str
    atr_range: Tuple[float, float]
    timeframe: str
    regime: str
    confidence: float
    # Computed from experiments
    effect: float
    ci_low: float
    ci_high: float
    sample_size: int

@dataclass
class EvidenceCard:
    """Raw observations vs Interpretation."""
    mean_bp: float
    p_value: float
    ci: Tuple[float, float]
    sample_size: int
    fdr_corrected: bool
    interpretation: str  # e.g., "Statistically significant"

@dataclass
class MechanismRecord:
    """Authoritative source of truth for a mechanism."""
    metadata: Dict[str, Any]
    description: str
    causal_chain: List[str]
    scientific_rationale: str
    falsification_criteria: List[str]
    boundary_models: Dict[str, BoundaryModel]
    evidence: Dict[str, EvidenceCard]
    validation_history: List[str]  # References to EXP/NEG/D IDs
    known_interactions: Dict[str, str] # e.g. {"suppressed_by": "M002"}
    known_failure_domains: List[str]
    
    @property
    def confidence(self) -> float:
        """Computed dynamically from evidence."""
        # ... logic to compute from evidence, replication, etc. ...
        return 0.0

    @property
    def level(self) -> str:
        """Computed dynamically from validation history."""
        return "L0"

    def next_experiment(self) -> Dict[str, Any]:
        """Identifies experiment with highest information gain."""
        return {}

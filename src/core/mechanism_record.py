from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import json
from pathlib import Path

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
    boundary_models: Dict[str, BoundaryModel] = field(default_factory=dict)
    evidence: Dict[str, EvidenceCard] = field(default_factory=dict)
    validation_history: List[str] = field(default_factory=list)  # References to EXP/NEG/D IDs
    known_interactions: Dict[str, str] = field(default_factory=dict) # e.g. {"suppressed_by": "M002"}
    known_failure_domains: List[str] = field(default_factory=list)
    
    def save(self):
        """Persist to JSON."""
        path = Path(f"data/records/{self.metadata['mechanism_id']}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Convert dataclasses to dicts manually to handle nested structures
        data = asdict(self)
        # Fix tuples and nested dataclasses if needed by asdict
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    @classmethod
    def load(cls, mechanism_id: str) -> MechanismRecord:
        path = Path(f"data/records/{mechanism_id}.json")
        with open(path, "r") as f:
            data = json.load(f)
        
        # Reconstruct complex types
        boundary_models = {
            k: BoundaryModel(**v) for k, v in data.get("boundary_models", {}).items()
        }
        evidence = {
            k: EvidenceCard(**v) for k, v in data.get("evidence", {}).items()
        }
        return cls(
            metadata=data["metadata"],
            description=data["description"],
            causal_chain=data["causal_chain"],
            scientific_rationale=data["scientific_rationale"],
            falsification_criteria=data["falsification_criteria"],
            boundary_models=boundary_models,
            evidence=evidence,
            validation_history=data["validation_history"],
            known_interactions=data["known_interactions"],
            known_failure_domains=data["known_failure_domains"]
        )

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

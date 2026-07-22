from src.core.mechanism_record import MechanismRecord, BoundaryModel, EvidenceCard
from typing import Dict

def get_m002_record() -> MechanismRecord:
    return MechanismRecord(
        metadata={
            "mechanism_id": "M002",
            "version": 2,
            "family": "Momentum",
            "created": "2026-07-16",
            "last_updated": "2026-07-21"
        },
        description="Trend Continuation (ROC-based). Momentum in confirmed trends.",
        causal_chain=["Institutional positioning", "Momentum reinforcement", "Exhaustion"],
        scientific_rationale="Persistent directional flows driven by narrative reinforce trends until exhaustion, detectable via ROC.",
        falsification_criteria=[
            "ROC(5) < 0.5% (Weak momentum)",
            "Volume divergence"
        ],
        boundary_models={
            "ETH_4h_B01": BoundaryModel(
                model_id="M002_ETH_4h_B01",
                asset="ETHUSDT",
                atr_range=(0.0, 1.0),
                timeframe="4h",
                regime="any",
                confidence=0.85,
                effect=15.0,
                ci_low=5.0,
                ci_high=25.0,
                sample_size=300
            )
        },
        evidence={
            "ETH_4h": EvidenceCard(
                mean_bp=15.0,
                p_value=0.01,
                ci=(5.0, 25.0),
                sample_size=300,
                fdr_corrected=True,
                interpretation="Statistically significant"
            )
        },
        validation_history=["D024", "EXP-2026-07-21"],
        known_interactions={"requires": "Trend regime"},
        known_failure_domains=["Mean reversion regimes"]
    )

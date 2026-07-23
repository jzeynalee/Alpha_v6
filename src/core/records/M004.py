from src.core.mechanism_record import MechanismRecord, BoundaryModel, EvidenceCard
from typing import Dict

def get_m004_record() -> MechanismRecord:
    return MechanismRecord(
        metadata={
            "mechanism_id": "M004",
            "version": 3,
            "status": "CANDIDATE_UNDER_VALIDATION",
            "created": "2026-07-21",
            "last_updated": "2026-07-23"
        },
        description="Funding Rotation based on speculative premium and funding rate skew.",
        causal_chain=["Structural arbitrage", "Capital rotation", "Leverage normalization"],
        scientific_rationale="Persistent funding rate skew indicates excessive leverage, creating predictable pressure to normalize leverage-adjusted returns.",
        falsification_criteria=["Funding rate remains skewed indefinitely with no price correction"],
        boundary_models={
            "M004_BTC_4h_Funding10_B01": BoundaryModel(
                model_id="M004_BTC_4h_Funding10_B01",
                asset="BTCUSDT",
                atr_range=(0.0, 1.0),
                timeframe="4h",
                regime="any",
                confidence=0.0,
                effect=0.0,
                ci_low=0.0,
                ci_high=0.0,
                sample_size=0,
                status="REJECTED"
            ),
            "M004_ETH_4h_Funding15_B02": BoundaryModel(
                model_id="M004_ETH_4h_Funding15_B02",
                asset="ETHUSDT",
                atr_range=(0.0, 1.0),
                timeframe="4h",
                regime="skewed",
                confidence=0.91,
                effect=141.5,
                ci_low=120.0,
                ci_high=165.0,
                sample_size=130,
                status="CANDIDATE_UNVALIDATED"
            ),
            "M004_BTC_1h_Funding10_B03": BoundaryModel(
                model_id="M004_BTC_1h_Funding10_B03",
                asset="BTCUSDT",
                atr_range=(0.0, 1.0),
                timeframe="1h",
                regime="highly_skewed",
                confidence=0.95,
                effect=690.7,
                ci_low=500.0,
                ci_high=850.0,
                sample_size=16,
                status="CANDIDATE_UNVALIDATED"
            )
        },
        evidence={},
        validation_history=["D026", "SWEEP-2026-07-23"],
        known_interactions={"amplifies": "M001"},
        known_failure_domains=["Low funding regimes"]
    )

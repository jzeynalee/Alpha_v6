from src.core.mechanism_record import MechanismRecord, BoundaryModel, EvidenceCard
from typing import Dict

def get_m003_record() -> MechanismRecord:
    return MechanismRecord(
        metadata={
            "mechanism_id": "M003",
            "version": 3,
            "status": "CANDIDATE_UNDER_VALIDATION",
            "created": "2026-07-21",
            "last_updated": "2026-07-23"
        },
        description="Position Unwind (Open Interest vs Price divergence) on high-quality regimes.",
        causal_chain=["OI exhaustion", "Profit taking", "Forced unwinding"],
        scientific_rationale="Divergence indicates lack of new conviction.",
        falsification_criteria=["OI increases with price during reversal"],
        boundary_models={
            "M003_BTC_4h_Lookback5_B01": BoundaryModel(
                model_id="M003_BTC_4h_Lookback5_B01",
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
            "M003_BTC_4h_Lookback10_B02": BoundaryModel(
                model_id="M003_BTC_4h_Lookback10_B02",
                asset="BTCUSDT",
                atr_range=(0.0, 1.0),
                timeframe="4h",
                regime="neutral",
                confidence=0.88,
                effect=129.7, # 1.297 PF proxy
                ci_low=110.0,
                ci_high=145.0,
                sample_size=1557,
                status="CANDIDATE_UNVALIDATED"
            )
        },
        evidence={},
        validation_history=["D025", "SWEEP-2026-07-23"],
        known_interactions={},
        known_failure_domains=["Trending regimes", "Lookbacks < 5"]
    )

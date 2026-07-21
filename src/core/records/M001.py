from src.core.mechanism_record import MechanismRecord, BoundaryModel, EvidenceCard
from typing import Dict

def get_m001_record() -> MechanismRecord:
    return MechanismRecord(
        metadata={
            "mechanism_id": "M001",
            "version": 3,
            "created": "2026-07-16",
            "last_updated": "2026-07-21"
        },
        description="Liquidity Exhaustion mechanism.",
        causal_chain=["Liquidity imbalance", "Market maker withdrawal", "Mean reversion"],
        scientific_rationale="Microstructure imbalance reversal.",
        falsification_criteria=[
            "ADX > 25 (High trend)",
            "High volatility expansion (ATR > 90th percentile)"
        ],
        boundary_models={
            "BTC_4h_B01": BoundaryModel(
                model_id="M001_BTC_4h_B01",
                asset="BTCUSDT",
                atr_range=(0.35, 0.60),
                timeframe="4h",
                regime="neutral",
                confidence=0.82,
                effect=61.9,
                ci_low=26.7,
                ci_high=103.9,
                sample_size=217
            )
        },
        evidence={
            "BTC_4h": EvidenceCard(
                mean_bp=61.9,
                p_value=0.0018,
                ci=(26.7, 103.9),
                sample_size=217,
                fdr_corrected=True,
                interpretation="Statistically significant"
            )
        },
        validation_history=["D023", "EXP-2026-07-20"],
        known_interactions={"amplified_by": "M004"},
        known_failure_domains=["15m", "News regime"]
    )

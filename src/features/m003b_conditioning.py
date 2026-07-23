import pandas as pd
from src.core.mechanism_record import ConditioningMechanism, ConditioningEvidence

class PositionStressIndex(ConditioningMechanism):
    """
    Implementation of M003B: Position Stress Index.
    Outputs confidence_delta based on Price/OI divergence.
    """
    def evaluate(self, df: pd.DataFrame) -> ConditioningEvidence:
        # Calculate stress
        close_roc = df['close'].pct_change(10)
        oi_roc = df['sum_open_interest'].pct_change(10)
        stress = ((close_roc > 0.01) & (oi_roc < -0.01)) | \
                 ((close_roc < -0.01) & (oi_roc > 0.01))
        
        # Evidence: delta = +0.10 if high stress (expect reversal), -0.05 if low stress (trend strong)
        delta = stress.astype(float) * 0.10 - 0.05
        
        return ConditioningEvidence(
            confidence_delta=float(delta.iloc[-1]),
            activation_score=float(stress.iloc[-1]),
            rationale="Divergence between price and OI indicates position stress.",
            diagnostics={"stress_index": float(stress.iloc[-1])}
        )

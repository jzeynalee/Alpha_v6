# Mechanism Research Report (M002-M005)
**Date:** 2026-07-21

## 1. Executive Summary
This report summarizes the research evaluation and reconciliation of mechanisms M002 through M005. The platform focus has shifted from architectural expansion to scientific validation (Mechanism Stress Testing).

## 2. Mechanism-Specific Outcomes

### M002: Trend Continuation (Reconciled)
*   **Audit Finding:** Regime filters (SMA, LowVol) were introducing noise rather than signal.
*   **Action:** Refined the mechanism to focus solely on ROC-momentum (ROC > 0.5%).
*   **Result:** Performance improved significantly (ETH/4h PF=1.542, SOL/4h PF=1.276 baseline).
*   **Status:** Refined and active.

### M003: Position Unwind
*   **Evaluation:** Tested on BTCUSDT/15m (`oi_div_bearish`, `oi_div_bullish`).
*   **Result:** Failed to identify significant predictive horizons (p > 0.2). Experiments parked as "dormant".
*   **Interpretation:** Likely requires specific regime filtering or is not structural.

### M004: Funding Rotation
*   **Evaluation:** Pending evaluation in queue.

### M005: Volatility Compression → Expansion
*   **Evaluation:** Tested on BTCUSDT/4h (`vol_comp_low`).
*   **Result:** No significant predictive horizon (best p = 0.32). Hypothesis demoted to L0.
*   **Interpretation:** Mechanistic edge not validated at 4h on BTCUSDT.

## 3. Research Integrity & Architectural Observations
- **Provenance:** All experiments are tracked via `ExperimentManager` with `git_hash` provenance.
- **Falsification:** M003 and M005 failures provided clear signals for mechanism dormancy, adhering to our new falsification-first policy.
- **Registry:** `MechanismRegistry` successfully persisted these states, though registry-singleton synchronization remains a monitoring point.

## 4. Next Steps
1. Evaluate pending M004 queue.
2. Review parked M003 experiments for regime-specific potential.
3. Establish L4/L5 paper trading environment for validated M001.

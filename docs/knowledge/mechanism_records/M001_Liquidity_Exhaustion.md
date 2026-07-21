# MechanismRecord: M001 Liquidity Exhaustion

**Status:** L3 Cross-Market Validated
**Discovery:** Structural
**Causal Graph Edge:** Reversal (amplified by trend)

## 1. Description
After a statistically extreme price move driven by temporary liquidity imbalance, price has a tendency to revert toward its local mean as liquidity providers re-enter. Market makers withdraw liquidity during rapid moves, creating temporary vacuums. When they return, the spread compresses and price reverts. This is a microstructure phenomenon amplified by leverage in crypto.

## 2. Falsification Criteria
The mechanism is considered failed under the following conditions:
- ADX > 25 (High trend)
- High volatility expansion (ATR > 90th percentile)
- News-driven regime (detected via sentiment anomaly)
- Low liquidity environment (insufficient depth)

## 3. Validated Boundary Models
- **M001_BTC_4h_B01**:
  - Asset: BTCUSDT
  - ATR Range: [0.35, 0.60]
  - Timeframe: 4h
  - Trend Condition: ADX < 25
  - Funding Condition: neutral
  - Confidence: 0.82

## 4. Evidence Summary (BTC/4h)
- Horizon: 5
- Mean: +61.9bp
- p-value: 0.0018
- Significance: ★★★

## 5. Validation History
- L0: Economic intuition registered.
- L1: In-sample edge discovery (4h/1d).
- L2: Transaction cost robustness confirmed.
- L3: Cross-market replication (ETH, SOL, BNB, XRP) & Null model comparison validated.

## 6. Next Recommended Experiment
- **L4/L5:** Initialize paper trading journal for M001 to begin the 6-month live performance monitoring for ProductionGate readiness.

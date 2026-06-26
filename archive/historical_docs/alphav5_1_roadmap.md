# Alpha V5.1 — The Production Engineering Charter

**Status**: Ratified — 2026-06-17  
**Predecessor**: [Alpha V5 Roadmap](./alphav5_roadmap.md)

## Mission Statement

Build a modular statistical trading platform around two independent, empirically validated edges:

1. **Cross-sectional relative-value mean reversion** (Optional Module A).
2. **Volatility regime transition & magnitude forecasting** (Core Module B/C).

The system is explicitly designed so that failure in Module A does not halt Module B. All modules are protected by a global structural-break layer.

---

## Architectural Overview (Modular Failover Design)

```
Market Data Feeds (1m, 5m, 1h, 24h)
                │
                ▼
┌─────────────────────────────────────────────┐
│  Phase 0: Data Lake + Redis State Cache     │
│  (Deterministic replay, <50ms cache reads)  │
└──────────────────────┬──────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────────┐
│ Phase 1: RelVal │ │ Phase 3:    │ │ Phase 4: Volatility │
│ (Optional      │ │ Hazard      │ │ Forecast (Mandatory)│
│  Module A)     │ │ (Mandatory) │ │                     │
└────────┬────────┘ └──────┬──────┘ └──────────┬──────────┘
         │                  │                    │
         └──────────┬───────┴────────┬───────────┘
                    │                │
                    ▼                ▼
         ┌─────────────────────────────────────┐
         │  Phase 2: Global Structural Breaks  │
         │  (CUSUM, Chow, ADF drift monitor)   │
         └──────────────────┬──────────────────┘
                            │
                            ▼
         ┌─────────────────────────────────────┐
         │  Phase 5: Portfolio Allocator       │
         │  (Dynamic sizing based on Hazard)   │
         └──────────────────┬──────────────────┘
                            │
                            ▼
         ┌─────────────────────────────────────┐
         │  Phase 6: Vol Monetization (Options)│
         │  + Phase 7: Execution (TWAP/VWAP)   │
         └─────────────────────────────────────┘
```

---

## Phase 0 — Data & Orchestration (Foundational)

**Components:**
- Storage: DuckDB (local backtests) + Parquet (historical).
- Cache: Redis (real-time state).
- Synchronization: Asynchronous pub/sub. Hazard writes every 5m; RelVal/Vol read latest cached values on their 1h cycles.

**Extended Cache Schema:**

| Key | Source | Update Freq |
|---|---|---|
| `hazard_score` | Phase 3 | 5m |
| `hazard_regime` (Low/Med/High) | Phase 3 | 5m |
| `spread_zscore` (per pair) | Phase 1 | 1h |
| `half_life_estimate` (per pair) | Phase 1 | 1h |
| `funding_spread` (perp diff) | Phase 1 | 1h |
| `funding_zscore` | Phase 1 | 1h |
| `funding_velocity` (F_t − F_{t−24h}) | Phase 1 | 1h |
| `relationship_health` (0–1) | Phase 2 | 1h |
| `vol_forecast_P50/P90` | Phase 4 | 1h |
| `strategy_enabled` (Global flag) | Phase 2 | Real-time |

---

## Phase 1 — Relative Value Engine (Optional, but Preferred)

If this module fails its gates, it is permanently disabled, and its capital is reallocated to Phase 6.

**Universe:** BTC, ETH, SOL, BNB, AVAX (top 5).

**Step 1: Cointegration Gate (Johansen):**
- `statsmodels.tsa.vector_ar.vecm.coint_johansen` on 90-day window.
- Fail: p > 0.05 → pair discarded. No OLS/Kalman.

**Step 2: Dynamic Hedge Ratio (Kalman Filter):**
- State: β_t (hedge ratio).
- Observation: log(P_A) = β_t · log(P_B) + ε_t.
- Libraries: `pykalman` or `filterpy`.

**Step 3: Robust Standardization:**
- Use rolling Median Absolute Deviation (MAD): z = (spread − median_spread) / MAD.

**Step 4: Mandatory Carry Attribution (New):**
- Store decomposed PnL:
  - PricePnL = Δspread.
  - FundingPnL = (Funding_Short − Funding_Long) × Notional.
- Backtest Output: Log all three variants (Price only, Funding only, Combined).

**Feature Engineering (Funding Velocity):**
- Compute `funding_velocity` per asset.
- Store in cache. Used later to adjust `expected_half_life` in the Portfolio layer.

**Success Gate (Path A):**
- Combined (Price + Funding) Sharpe > 1.0 on ≥4 of 5 pairs.
- Sign stability > 90% in rolling walk-forward.
- If Passed: Proceed with Track A allocation (50% risk budget).
- If Failed: Set `RelVal_Healthy = False`. Move 100% of risk budget to Volatility (Phase 6).

---

## Phase 2 — Global Structural Break Engine (Critical Gatekeeper)

**Objective:** Protect both RelVal and Volatility engines from regime shifts.

**Tools:**
- CUSUM (for mean drift in spread/residuals).
- Chow Test (for beta stability in Kalman filter).
- Rolling ADF (monitor cointegration p-value drift).

**Outputs:**
- `relationship_health` (0.0 = broken, 1.0 = healthy).

**Cold Start Protocol (Post-Break):**
1. Flatten all RelVal positions immediately.
2. Pause Phase 4 (Vol Forecast) for 12 hours.
3. Reset Phase 3 (Hazard) baseline ATR to the last 48 hours only (discard pre-break vol data).
4. RelVal re-activation only allowed if rolling ADF p < 0.05 for 48 consecutive hours.

**Success Gate:**
- Historical replay must disable trading before >5% drawdown occurs from structural shifts.
- False positive shutdown rate < 10%.

---

## Phase 3 — Hazard Engine (Mandatory Core)

**Objective:** Predict the probability of volatility expansion (replaces HMM).

**Event Definition:**
- Compression: Current ATR < 20th percentile of 20-period ATR.
- Expansion: Future ATR > 1.5× 20-period mean within the next 6 hours.

**Features:** compression_score, BOS, CHOCH, Liquidity Sweep, ATR percentile, Volume z-score, Swing velocity.

**Models:**
- Primary: Cox Proportional Hazards (`lifelines`).
- Fallback: Random Survival Forest (`scikit-survival`).

**Validation:**
- C-index > 0.65 (minimum). Target > 0.70.
- Brier score calibrated.

**Output to Cache:** `hazard_score` (0–1) and `hazard_regime` (Low/Mid/High) written every 5 minutes.

---

## Phase 4 — Volatility Forecasting Engine (Mandatory Core)

**Objective:** Forecast the magnitude of future volatility (not direction).

**Horizon:** 24-hour realized volatility (aligned with Deribit daily options).

**Target:** RV_{24h} = √(Σ_{i=1}^{288} r_i²) (using 5m returns).

**Features:** All Alpha V4 features + `hazard_score` (from cache) + `funding_velocity`.

**Models:**
- Primary: XGBoost / Gradient Boosting.
- Advanced: Quantile Regression Forest (for P10/P50/P90).

**Output to Cache:** `vol_forecast_P50`, `vol_forecast_P90`.

**Success Gate:** RMSE must outperform the naive baseline (Forecast = ATR_today) by > 15%.

---

## Phase 5 — Portfolio Allocator (The Failover Logic)

**Inputs:** Reads cache from Phases 1, 3, and 4.

**Dynamic Regime Logic:**
- If `hazard_regime == Low` (bottom quartile):
  - Deploy RelVal (if healthy) at 1.0x target volatility.
  - Reduce Volatility Strategy sizing (vol compression means options are often overpriced).
- If `hazard_regime == High` (top quartile):
  - Correlation Penalty: `relval_weight *= 0.5` (prevents dual-crash correlation).
  - Increase Volatility Strategy sizing (buy straddles to capture expansion).

**The Failover Rule:**
```
if RelVal_Healthy == False:
    Disable Phase 1 allocation entirely.
    Reallocate the entire 10-15% annualized volatility risk budget to Phase 6 (Vol Monetization).
    # Note: Phase 6 alone must survive with Sharpe > 1.2.
```

**Position Sizing:**
- Fractional Kelly (capped at 2x leverage).
- Volatility targeting to 12% annualized portfolio vol.

**Success Gate:** Portfolio Max DD < 15%.

---

## Phase 6 — Volatility Monetization (Execution Strategy)

**Signal Construction:**
- Compute Volatility Risk Premium (VRP): VRP = Forecast_RV − Implied_Vol_{24h}.
- Normalize: VRP_z = VRP / Rolling_Std(VRP).

**Trading Rules:**
- Long Vol (Buy Straddle): When VRP_z > 1.5.
- Short Vol (Sell Straddle): When VRP_z < −1.5.
- Exit: Close position when VRP_z reverts to < 0.5, or at daily expiry.

**Venue:** Deribit (primary) for 24h ATM straddles.

---

## Phase 7 — Execution Layer

**Infrastructure:**
- AsyncIO + WebSockets for real-time price/orderbook.
- Redis Pub/Sub for command propagation.

**Execution Algorithms:**
- RelVal: TWAP/VWAP over 15 minutes to reduce cross-asset slippage.
- Leg Synchronization: Target < 50ms latency between short and long legs.

**Cost Model (Hardcoded):**
- Taker fee: 0.04%.
- Slippage: 0.05% per leg (projected).
- Funding: Recalculated hourly.

**Success Gate:** Paper trading for 3 months; realized PnL must be within 15% of backtest.

---

## Revised Implementation Schedule (Next 72 Hours)

| Day | Deliverables | Rationale |
|---|---|---|
| **Day 1** | `src/core/cointegration.py` + `src/core/kalman_hedge.py` + `src/core/funding_metrics.py` | Foundation for RelVal and funding features. |
| **Day 2** | `src/core/structural_breaks.py` + `src/core/hazard_engine.py` | Build break detector before full backtest to prevent false attribution of structural shifts as strategy failure. |
| **Day 3** | `src/backtest/relval_backtest.py` + `src/backtest/vol_backtest.py` | Run the full 2023-2026 walk-forward. Check both Path A and Path B success gates. |

---

## Final Success Criteria (Two Independent Paths)

| Module | Metric | Target |
|---|---|---|
| Path A (RelVal + Vol) | Portfolio Sharpe | > 1.5 |
| Path B (Volatility-only) | Portfolio Sharpe | > 1.2 |
| Global (Both Paths) | Max Drawdown | < 15% |
| Global | Hazard C-index | > 0.65 |
| Global | Vol Forecast RMSE Improvement | > 15% vs Naive |

---

## The "Stop Doing" List (Strictly Enforced)

- No 5m directional BTC classification.
- No RSI/CCI/MFI indicator discovery.
- No HMM or Markov-Switching models.
- No brute-force DSL threshold mining.
- No RelVal dependency for system survival (enshrined as a rule).

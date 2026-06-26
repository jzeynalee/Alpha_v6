# Alpha V5 — Three-Track Implementation Plan

## Summary

Alpha V5 shifts from directional prediction (falsified) to three verifiable edge types: **relative-value mean reversion** across crypto pairs, **volatility expansion forecasting**, and **event-state transition analysis**. The plan delivers three reusable Python engines, a unified verification framework for brutal stress-testing of any signal, and asset-expansion infrastructure for SOL/BNB/XRP/LINK.

---

## Key Changes (by Track)

### Track A — Relative Value Engine (50%)

**Enhance `src/core/relative_value.py`:**
- Generalize from BTC/ETH-only to N-asset pairwise spreads
- Add rolling beta (EWMA regression) and cointegration metrics (Engle-Granger residual z-score alongside raw log-spread z-score)
- Add `cross_sectional_rank()` method: for each bar, rank all pairs by spread z-score, output long/short recommendations
- Forward returns computed for each pair at multiple horizons
- Persist spread-feature DataFrames to `data/research/` for downstream consumption

**New script `scripts/discover_relative_value_v5.py`:**
- Runs all pair spread analyses
- Produces Markdown report with one table per pair showing conditional expectancy
- Calls the Verification Framework for walk-forward stability, cost robustness, capacity

**Asset expansion:**
- Add SOLUSDT, BNBUSDT, XRPUSDT, LINKUSDT to the backfill pipeline by extending `alpha_factory_config.yml` symbols list and running `scripts/backfill_lbank.py`
- The `_to_lbank_symbol()` heuristic in `src/data/lbank_data.py` already handles these symbol formats generically

### Track B — Volatility Forecasting Engine (35%)

**New module `src/core/volatility_forecaster.py`:**
- `VolatilityForecaster` class with sklearn-style API (`fit`, `predict`, `predict_proba`, `score`, `save`/`load`)
- Features: compression_score, expansion_risk, ATR percentile, structural event presence (BOS, displacement), spread volatility from Track A
- Targets:
  - `target_atr_double_Nb`: binary — does ATR ≥ 2× current within N bars?
  - `target_range_pct_Nb`: continuous — future range / current close
  - `target_vol_regime_shift`: binary — does ATR percentile cross 50th within N bars?
- Uses `PurgedWalkForward` for proper time-series train/test splits
- Outputs probabilities, not trading rules

**New script `scripts/discover_volatility_v5.py`:**
- Trains and evaluates VolatilityForecaster
- Produces report: AUC per target, feature importance, calibration curve
- Calls Verification Framework

### Track C — Event-State Transition Engine (10%)

**New module `src/core/event_transitions.py`:**
- Defines a state space from `StructuralEventDetector` outputs: COMPRESSION, EXPANSION, BOS_UP, BOS_DOWN, NEUTRAL
- `TransitionMatrix` class: estimates Markov transition probabilities `P(state_t+1 | state_t)`, `P(state_t+2 | state_t)`, etc.
- `transition_expectancy()`: for each transition path (e.g., COMPRESSION → BOS_UP → EXPANSION), compute forward return expectancy, win rate, and event count

**New script `scripts/discover_transitions_v5.py`:**
- Runs transition analysis on BTCUSDT 5m
- Produces report: transition probability matrix, expectancy per path, event frequency per path

---

## Shared Infrastructure

### Unified Verification Framework

**New module `src/validation/signal_verifier.py`:**
- `SignalVerifier` class that takes:
  - A signal DataFrame (index=bar, columns=signal values)
  - A target DataFrame (index=bar, columns=forward returns/targets)
  - Year labels derived from timestamps
- Methods:
  - `walk_forward_stability()` — splits by calendar year, checks sign consistency of mean(target | signal > threshold) per year. Reports: annual means, sign-flip count, worst-year deviation
  - `cost_robustness()` — given fee_pct and slippage_pct, computes net alpha = gross - cost. For spread trades: both legs pay fees + slippage. Reports: gross alpha, net alpha, break-even cost
  - `capacity_analysis()` — counts signal triggers per year, per month. Reports: annual event count, max monthly count, concentration (Gini of event spacing)
  - `summary()` — single dict/Markdown table with pass/fail on each dimension

### Backtest extension for pair trades

**Enhance `src/backtest/` (minimal):**
- The existing `BacktestEngine` is single-symbol. For relative-value pair trades we need a lightweight `PairBacktestEngine` that enters a long/short spread position when signal fires and tracks PnL with fees on both legs.
- Alternatively, simulate spread PnL directly from the relative-value returns DataFrame without a full event-driven backtest — simpler and sufficient for verification. Use the latter approach.

---

## Test Plan

### New tests to add
1. **`test_relative_value_v5.py`** — unit tests for multi-asset spread computation, cross-sectional ranking, cointegration metrics
2. **`test_volatility_forecaster.py`** — fit/predict/proba smoke test with synthetic data, save/load roundtrip, purged split integrity
3. **`test_event_transitions.py`** — transition matrix correctness (rows sum to 1), expectancy calculations on synthetic state sequences
4. **`test_signal_verifier.py`** — walk-forward sign consistency on synthetic yearly data with known sign, cost robustness pass/fail with known cost, capacity Gini calculation

### Verification gates before declaring victory on any signal
- Walk-forward: same sign every calendar year (2023–2026)
- Cost robustness: net alpha > 0 after 10bp fee + 5bp slippage per leg
- Capacity: ≥ 50 events/year for a signal to be tradeable

---

## Assumptions & Defaults

- **Data source**: LBank (existing pipeline). SOL/BNB/XRP/LINK data will be backfilled using the existing `scripts/backfill_lbank.py` with `--symbols` flag. We assume these pairs exist on LBank.
- **Timeframe**: 5m OHLCV (consistent with existing discoveries). Higher-TF analysis can be added later.
- **Horizons**: 6, 12, 24, 48 bars for forward targets (consistent with existing research).
- **Fees/slippage**: 10bp fee per leg + 5bp slippage (conservative retail crypto). Configurable in Verification Framework.
- **Walk-forward years**: 2023, 2024, 2025, 2026 (if data allows). Minimum 3 years for stability test.
- **No trading rules yet**: Track B outputs probabilities, not signals. Execution design is deferred until forecast skill is proven.
- **BTC/ETH pair** remains the highest-confidence relative-value signal. Other pairs are tested for generalization.
- **Existing `RelativeValueEngine`** is preserved; the new generalized engine is an additive module, not a replacement (backward compatibility).
- **Code style**: Follow existing project conventions — type hints, dataclasses, numpy/pandas, same logging patterns.

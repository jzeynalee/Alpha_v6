# Alpha Factory V4 — Three-Stage Pipeline Plan

**Date**: 2026-06-13  
**Status**: Phases 1-3 Implemented, Phase 4 (Testing) Pending

---

## 1. Motivation

### 1.1 Current Architecture (V3) — A Suppressing System

```
OHLCV → AlphaFactory (6 layers) → DeterAlpha (8-step gate) → 1 signal per (symbol, tf)
```

The V3 pipeline produces **exactly one alpha per `(symbol, timeframe)`**. The ML model in Layer 4
generates one alpha_raw, which is then gated by DeterAlpha. When DeterAlpha's causal filter says
"no", the system produces nothing. This is a **suppressing system** — it can only say "trade" or
"don't trade" on a single signal hypothesis. It has no mechanism for signal diversity.

### 1.2 Goal

Generate **several scalping alphas per day** by introducing a signal generator upstream of the
existing pipeline, creating:

```
signal_factory → alpha_factory → deter_alpha → trade execution
  (generate)      (operationalize)   (validate)
```

### 1.3 Why Three Stages?

| Stage | Responsibility | When It Runs | Output |
|-------|---------------|-------------|--------|
| **Signal Factory** | Discover which feature combinations predict zone direction | Offline (weekly) | `strategies_hub` JSON with 60 strategies |
| **Alpha Factory** | Execution sizing: spread, slippage, fill probability, capacity | Online (per bar) | Sized alpha per strategy |
| **DeterAlpha** | Causal validation: does the signal's feature set causally predict regime? | Online (per bar) | Gate decision per strategy |

Each stage has a distinct concern. Mixing them creates the current bottleneck.

---

## 2. Signal Factory Simulation (Already Built)

Located at `scripts/signal_factory_simulation.py` (1809 lines). This is the **offline strategy
discovery engine**.

### 2.1 How It Works

```
OHLCV CSV → features (220+ cols) → HA smoothing → swing detection → zone construction
→ zone labeling (bull/bear/neutral by ATR threshold) → feature voting (DSL rules)
→ per-feature stats (Wilson_lb × MI × ln(1+Support)) → leader selection
→ 625 core strategies (product of 4 group leaders × 3 directions)
→ scoring (PF for directional, StabilityFactor for neutral) → greedy expansion to length 8
→ Jaccard diversity filter → top 20 per direction → strategies_hub JSON
```

### 2.2 Strategy Format (from hub JSON)

```json
{
  "direction": "bull",
  "features": ["adx", "ema_200", "cmf", "tsi"],
  "length": 4,
  "support": 142,
  "ps": 0.62,
  "wilson_lb": 0.54,
  "lift": 1.32,
  "pf": 1.15,
  "score": 1.87
}
```

A strategy says: "When ALL of these features vote BULL at the current bar, go long."
The voting rules come from `src/config/features_config.yml`.

### 2.3 Live Evaluation Concept

At each bar, for each active strategy:
1. Evaluate each feature's DSL rule against the current feature row
2. If ALL features vote in the strategy's direction → the strategy fires
3. The `direction` (+1/-1) becomes a candidate signal
4. Pass to Alpha Factory for execution sizing
5. Pass to DeterAlpha for causal validation

---

## 3. Implementation Phases

### Phase 1: Strategy Hub Loader & Live Evaluator

**New file**: `src/core/signal_factory.py`

#### 1.1 StrategyHubLoader class

```
StrategyHubLoader
├── load(hub_path: Path) → List[LiveStrategy]
├── LiveStrategy dataclass:
│   ├── strategy_id: str          # e.g. "BTCUSDT_5_bull_001"
│   ├── direction: int            # +1, -1, 0
│   ├── features: Tuple[str, ...] # sorted tuple
│   ├── wilson_lb: float
│   ├── score: float
│   └── pf: float
├── RuleEvaluator (from signal_factory_simulation.py, extracted)
└── evaluate_strategy(strategy, feature_row, compiled_rules) → bool
```

#### 1.2 Changes to AlphaFactory.__init__

```python
# New member
self.signal_hub: Optional[SignalHubLoader] = None

# New config entries
signal_hub_path: Optional[str] = None     # path to strategies_hub JSON
signal_hub_max_strategies: int = 60       # cap on active strategies
```

#### 1.3 Changes to _process_bar_sync_unsafe

Before Layer 4 compute_alpha, add:

```python
# ── Signal Factory: generate candidate signals ──
signal_candidates = []
if self.signal_hub is not None and features_df is not None:
    signal_candidates = self.signal_hub.evaluate_all(
        symbol, timeframe, features_df.iloc[-1]
    )
# signal_candidates = [(strategy_id, direction, confidence), ...]
```

---

### Phase 2: Multi-Strategy DeterAlpha

#### 2.1 Per-Strategy DeterAlpha State

Currently `DeterAlphaPipeline` is one instance shared across all keys. Change to:

```python
class DeterAlphaPipeline:
    # Add per-strategy state dict
    _per_strategy_state: Dict[str, Dict] = {}
    
    def update(self, ..., strategy_id: str = "_default_") -> DeterAlphaResult:
        st = self._get_or_create_state(strategy_id)
        # ... existing logic, keyed by strategy_id
```

This means swing detectors, region labelers, precision EWMAs, and causal sets are tracked
separately for each strategy. A momentum strategy's causal validation is independent of a
mean-reversion strategy's.

#### 2.2 Per-Strategy Causal Feature Columns

Each strategy has its own feature set. Instead of using the full 220+ column set for causal
discovery, use only the strategy's features:

```python
# In _run_deter_alpha:
causal_columns = list(strategy.features)  # only the strategy's features
```

This makes causal refit faster (4-8 columns instead of 220) and more relevant (the causal
question is "does this specific feature set cause the regime?", not "do any of 220 features?").

#### 2.3 Per-Strategy Gate Thresholds

```yaml
# deter_alpha_config.yaml (new per-variant section)
variants:
  momentum:
    c_threshold: 0.80
    te_threshold: 0.05
    refit_every_n_bars: 240
  mean_reversion:
    c_threshold: 0.60
    te_threshold: 0.03
    refit_every_n_bars: 120
  breakout:
    c_threshold: 0.70
    te_threshold: 0.08
    refit_every_n_bars: 180
```

Fallback: use defaults from existing config if no variant-specific override.

---

### Phase 3: Multi-Variant Alpha Generation

#### 3.1 Strategy ID Scheme

Change from `"{symbol}_{timeframe}"` to `"{symbol}_{timeframe}_{variant}"`.

Examples:
- `BTCUSDT_5_bull_001`
- `BTCUSDT_5_bear_012`
- `ETHUSDT_60_bull_003`

#### 3.2 Signal Candidates → Alpha

For each strategy that fires at a bar, Layer 4 needs to produce an alpha:

```python
for candidate in signal_candidates:
    strategy_id, direction, confidence = candidate
    
    # Layer 4: execution sizing
    alpha_exec = self.layer4.compute_alpha_for_signal(
        symbol=symbol, timeframe=timeframe,
        direction=direction,           # pre-determined direction
        confidence=confidence,         # from signal_factory
        features_df=features_df,
        position_size=position_size,
        bid_ask_spread=bid_ask,
        # ... other execution params
    )
    
    # DeterAlpha: causal validation
    deter_result = self.deter_alpha.update(
        ...,
        strategy_id=strategy_id,
        causal_feature_columns=list(candidate.features),
    )
    
    # Final gate
    if deter_result.final_decision != 0:
        gated_signal = alpha_exec * np.sign(deter_result.final_decision)
        self.layer6.receive_signal(strategy_id, gated_signal, current_ts)
```

#### 3.3 Latency Budget

With N=60 strategies, per-bar evaluation must stay under 50ms:

| Operation | Per-Strategy Cost | N=60 Total |
|-----------|-------------------|------------|
| Feature voting (boolean checks) | ~5 μs | ~0.3 ms |
| Alpha compute (model inference) | ~0.5 ms* | ~0.5 ms* |
| DeterAlpha gating | ~2 ms* | ~2 ms* |
| **Total** | | **~3 ms** |

*Model inference and DeterAlpha can be batched: one predict_proba call for all strategies,
one causal refit cycle. The dominant costs don't scale linearly with N.

#### 3.4 Heuristic Alpha Path (No Per-Strategy ML Model Needed)

For rule-based signal factory strategies, the ML model is not required. Layer 4's heuristic
fallback already does:

```python
alpha_raw = 0.1 * (momentum_prob - 0.5) * css
```

For signal factory strategies, replace this with a confidence-weighted direction:

```python
alpha_raw = direction * confidence * css
```

Where `confidence` comes from the strategy's Wilson_lb × lift at discovery time (decayed by
time since discovery).

---

### Phase 4: Strategy Lifecycle Integration

#### 4.1 Auto-Admission

`StrategyRepository._bootstrap_strategy()` already handles unknown strategy IDs. With the new
`{symbol}_{timeframe}_{variant}` scheme, new strategies from an updated hub are auto-admitted.

#### 4.2 Performance Tracking

Layer 6 already tracks per-strategy rolling IR, drawdown, and kill-switch. No changes needed
— the existing performance tracking works on `strategy_id`, and the new variant IDs are just
more strategy_ids.

#### 4.3 Session Filter

```python
SESSION_HOURS = {
    "Asia":    (0, 8),     # 00:00–08:00 UTC
    "London":  (7, 16),    # 07:00–16:00 UTC
    "NY":      (12, 21),   # 12:00–21:00 UTC
    "Overlap": (12, 16),   # 12:00–16:00 UTC
}

class LiveStrategy:
    allowed_sessions: List[str] = ["Asia", "London", "NY"]  # default: all
```

Strategies discovered on Asian-session data would be tagged with `allowed_sessions: ["Asia"]`
and only fire during those hours.

#### 4.4 Periodic Hub Refresh

```python
# In AlphaFactory or orchestrator:
async def refresh_signal_hub(self):
    """Re-run signal_factory_simulation and hot-reload strategies."""
    result = await run_signal_factory_simulation(...)
    self.signal_hub = StrategyHubLoader.load(result.hub_path)
    # Old strategies auto-retire if absent from new hub
```

---

### Phase 5: Testing & Validation

#### 5.1 Unit Tests

- Test `StrategyHubLoader.load()` with a sample hub JSON
- Test `evaluate_strategy()` against known feature rows
- Test that strategy_id parsing handles 3-token variant IDs
- Test that per-strategy DeterAlpha state is isolated

#### 5.2 Integration Test

- Full pipeline: load hub → process 1000 bars → assert multiple signals per day
- Verify no cross-strategy state pollution in DeterAlpha
- Verify Layer 6 correctly tracks 60 strategies

#### 5.3 Latency Benchmark

- Measure per-bar time with 0/10/30/60 active strategies
- Ensure p99 stays under 50ms budget
- Profile feature voting vs model inference vs causal refit

#### 5.4 Backtest Comparison

- Run V3 pipeline (1 signal) vs V4 pipeline (60 signals) on same historical data
- Compare: total trades/day, Sharpe, max drawdown, win rate
- Verify diversity: correlation matrix of strategy returns should have mean |r| < 0.3

---

## 4. File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `src/core/signal_factory.py` | Strategy hub loader + live evaluator |
| `src/core/session_filter.py` | Time-of-day session filter |
| `tests/test_signal_factory.py` | Unit tests for hub loader/evaluator |

### Modified Files

| File | Change |
|------|--------|
| `src/core/alpha_factory.py` | Add `signal_hub` member, wire into `_process_bar_sync_unsafe`, loop strategies |
| `src/core/deter_alpha.py` | Per-strategy state dict, per-strategy causal columns, per-strategy thresholds |
| `src/core/layers/decision_layer.py` | New `direction`-aware compute_alpha path for signal factory strategies |
| `src/core/layers/strategy_repo.py` | Parse 3-token strategy IDs in `_bootstrap_strategy` |
| `scripts/signal_factory_simulation.py` | Extract `RuleEvaluator` to shared module, add `--export-live-hub` flag |
| `src/config/alpha_factory_config.yaml` | Add `signal_hub` section, `variants` section for per-strategy config |

---

## 5. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| 60 strategies overfit to discovery period | Degraded live performance | Weekly hub refresh, Wilson_lb penalizes small-sample strategies |
| Per-bar latency exceeds 50ms | Missed bars, stale signals | Batch model inference, pre-compute feature votes once per bar |
| Cross-strategy correlation → concentrated risk | Portfolio drawdown | Existing Jaccard filter + Layer 6 cluster constraint (max 3 per cluster) |
| DeterAlpha cold start for new strategies | First N bars ungated | Warm DeterAlpha with historical feature data during hub load |
| Signal factory discovers spurious patterns | Low-quality alphas admitted | SurvivalGate filters before admission; per-strategy kill-switch retires bad strategies |

---

## 6. Success Criteria

1. **≥3 trades/day** on average (currently 0–1)
2. **p99 latency < 50ms** with 60 active strategies
3. **Mean pairwise strategy correlation < 0.3** (diverse alpha sources)
4. **No regression**: V3 single-strategy performance unchanged when hub is empty/disabled
5. **Graceful degradation**: system operates correctly when hub file is missing or malformed

---

## 7. Implementation Log (2026-06-13)

### Files Created
| File | Lines | Purpose |
|------|-------|---------|
| `src/core/signal_factory.py` | 646 | Live strategy evaluator: loads hub JSON, compiles DSL rules, evaluates strategies per bar |
| `src/core/price_action.py` | 427 | Price action alpha: swing proximity, volatility context, momentum, DOM-based conviction scoring |

### Files Modified
| File | Change |
|------|--------|
| `src/core/deter_alpha.py` | `DeterAlphaPipeline` now has per-strategy state isolation. `update()` and `record_outcome()` accept `strategy_id`. Each strategy gets its own swing detector, region labeler, causal analyser, deterministic filter, and scheduler. Glob-pattern config overrides (`variant_overrides`) supported. |
| `src/core/alpha_factory.py` | Added `SignalHub` and `PriceActionAlpha` imports. `__init__` loads hub (when `signal_factory.enabled: true`). `_process_bar_sync_unsafe` evaluates all signal_factory strategies after the legacy alpha path, computing price-action alpha and per-strategy deter_alpha for each firing strategy. Added `_run_deter_alpha_for_strategy()` helper. |
| `src/core/layers/strategy_repo.py` | `_bootstrap_strategy` parses 3-token variant IDs (`symbol_timeframe_variant`). Legacy 2-token IDs fall back to `variant="legacy"`. |
| `src/config/alpha_factory_config.yml` | Added `signal_factory`, `price_action`, and `deter_alpha.variant_overrides` configuration sections. |

### How to Enable
1. Run `scripts/signal_factory_simulation.py` to generate a `strategies_hub` JSON
2. Set `signal_factory.enabled: true` in `alpha_factory_config.yml`
3. Point `signal_factory.hub_path` to the generated JSON
4. Restart the Alpha Factory

### Backward Compatibility
- When `signal_factory.enabled` is `false` (default), the system operates exactly as V3
- `DeterAlphaPipeline.update()` without `strategy_id` uses singleton components (V3 behavior)
- `StrategyRepository._bootstrap_strategy` handles legacy 2-token IDs seamlessly

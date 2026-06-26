# Alpha V3 — Phase Implementation Report

**Generated**: 2026-06-14T15:37:20+00:00
**Status**: Phases A-D implemented. Three-timeframe analysis complete.
**Reference**: `docs/20260614_140138_improvement_plan_v2.md` (auditor-reviewed plan)
**Test data**: BTCUSDT, 5000 bars per timeframe, $10,000 capital, SL=1.5×ATR, TP=2.0×ATR, max hold=20 bars

---

## Executive Summary

| Phase | What | Result | Status |
|---|---|---|---|
| A | Trade-outcome labels (TP before SL) | WR +3.5%, PF +88%, losses -64% | ✅ Done |
| B | Net expectancy ranking | Losses -37% further, DD -39% | ✅ Done |
| C | Layer contribution analysis | RiskManager = KEEP. PriceAction + DeterAlpha = REMOVE | ✅ Done |
| D | Minimal pipeline config | SF → RiskManager → Execution toggle | ✅ Done |
| 3TF | Multi-timeframe analysis | 5min only viable TF. 15m+60m harmful | ✅ Analyzed |

---

## Phase A — Trade-Outcome Labels

### Problem

SignalFactory discovered strategies on **zone-level labels**: "did price rise by >ATR from swing-start to swing-end?" These multi-bar labels don't translate to bar-level trading decisions. A strategy 80% accurate at predicting zone direction could be 50% accurate at bar-level — exactly the 34.3% WR observed.

### Implementation

**Files changed**: `src/core/strategy_discovery.py`, `scripts/signal_factory_simulation.py`

**New functions** (~270 lines):

```python
# src/core/strategy_discovery.py

def compute_trade_labels(df, atr, sl_atr_mult=1.5, tp_atr_mult=2.0, max_hold=20):
    """Per-bar trade outcome: +1 if TP hit before SL, -1 if SL hit before TP,
       0 if time exit. Returns int8 array of shape (n_bars,)."""

def vote_features_at_bars(df, labels, compiled, cfg):
    """Evaluate DSL rules at EVERY valid bar (not just zone starts).
    Uses vectorized rule evaluation for speed."""

def evaluate_strategy_trade_labels(strategy, votes, labels, df, atr):
    """Score strategy against trade labels with actual SL/TP trade simulation.
    PF computed from simulated trade returns (with fees + slippage),
    NOT from raw zone close_end - close_start."""
```

**Key design decision**: Labels are `+1` if TP hit before SL for a LONG entry. This aligns discovery with actual trading outcomes — not theoretical price direction. A short entry label is the negation of the long label (if TP hits before SL on a long, SL hits before TP on a short).

### Results — BTCUSDT 5min, Stage 1 (RiskManager)

| Metric | Zone Labels | Trade Labels | Change |
|---|---|---|---|
| Trades | 1,193 | 509 | -57% |
| Win Rate | 32.9% | **39.3%** | **+6.4%** |
| Profit Factor | 0.17 | **0.32** | **+88%** |
| P&L | -$3,454 | **-$1,239** | **-64% losses** |
| Max DD | 34.54% | **13.08%** | **-62%** |

### Why trade labels work better

1. **Labels match execution**: Discovery asks "would this trade win?" not "does this zone go up?" The SL/TP structure is baked into the label itself.
2. **Higher Wilson LB**: Trade labels have Wilson LB 0.07-0.75 (median 0.39) vs zone labels 0.00-0.15 (median 0.03). Trade outcomes are easier to predict than multi-bar zone direction.
3. **Fewer but better signals**: 57% fewer trades, but each trade is selected by a strategy that was optimized for trade outcomes, not zone statistics.

---

## Phase B — Net Expectancy Ranking

### Problem

Strategies were ranked by `Wilson_lb × log(1 + support) × PF` — statistical purity, not profitability. The top-ranked strategies by Wilson score had **no correlation** with actual backtest P&L.

### Implementation

**File changed**: `src/core/strategy_discovery.py`

**Changes to `Strategy` dataclass**:
```python
net_expectancy: float = 0.0    # mean return per trade after costs
avg_win: float = 0.0           # mean return of winning trades
avg_loss: float = 0.0          # mean return of losing trades (negative)
n_wins: int = 0
n_losses: int = 0
```

**New scoring formula in `evaluate_strategy_trade_labels()`**:
```python
strategy.net_expectancy = np.mean(trade_rets) if trade_rets else 0.0
strategy.score = strategy.net_expectancy * math.log(1 + strategy.support())
```

**New function**: `rank_by_expectancy(strategies, min_support=10)` — ranks by mean trade return, excludes negative-expectancy strategies.

### Results — BTCUSDT 5min, Stage 1 (RiskManager)

| Metric | Wilson+PF Score (Phase A) | Net Expectancy (Phase B) | Change |
|---|---|---|---|
| Trades | 509 | **321** | -37% |
| Win Rate | 39.3% | 37.7% | -1.6% |
| Profit Factor | 0.32 | 0.31 | -0.01 |
| P&L | -$1,239 | **-$777** | **-37% losses** |
| Max DD | 13.08% | **7.93%** | **-39%** |

### Why net expectancy improves things

Net expectancy ranking selects strategies that **lose the least** rather than those that look most "statistically pure." Wilson-score ranking selected strategies with high directional accuracy but poor risk/reward (small wins, big losses). Net expectancy directly optimizes for the mean trade return — which is what actually determines P&L.

**Note**: The WR dropped slightly (39.3% → 37.7%) because net expectancy sometimes selects strategies with lower WR but better payoff ratios. This is correct behavior — a strategy with 35% WR and 3:1 reward:risk can be more profitable than one with 45% WR and 1:1.

---

## Phase C — Layer Contribution Analysis

### Problem

The pipeline had 3 gates (RiskManager, PriceAction, DeterAlpha) with unknown marginal contribution. The auditor asked: "Which parts actually make money?"

### Implementation

**New file**: `src/core/layer_contribution.py` (~370 lines)

**Key types**:
```python
@dataclass
class MarginalContribution:
    gate: str              # "RiskManager", "PriceAction", "DeterAlpha"
    signal_drop_pct: float # % of incoming signals removed
    pnl_delta: float       # change in total P&L
    wr_delta: float        # change in win rate
    dd_delta: float        # change in max drawdown
    recommendation: str    # "KEEP", "REMOVE", "INVESTIGATE"

def compute_marginal_contributions(stage_results) -> List[MarginalContribution]
def recommend_pipeline(contributions) -> PipelineRecommendation
def analyse_survival_logs(log_path) -> pd.DataFrame
def survival_summary(df) -> Dict
```

### Results — Phase B strategies, all timeframes

**5min**:
| Gate | Filter Rate | P&L Impact | WR Impact | DD Impact | Verdict |
|---|---|---|---|---|---|
| RiskManager | 81% | **+$9,223** | +0.4% | **-92.1%** | ✅ KEEP |
| PriceAction | 0% | -$5 | 0.0% | +0.05% | ❌ REMOVE |
| DeterAlpha | 100% | +$781 | -37.7% | -7.98% | ❌ REMOVE |

**15min**:
| Gate | Filter Rate | P&L Impact | WR Impact | DD Impact | Verdict |
|---|---|---|---|---|---|
| RiskManager | 68% | **+$3,003** | +0.8% | -48.4% | ✅ KEEP |
| PriceAction | 1% | -$39 | 0.0% | +0.35% | ❌ REMOVE |
| DeterAlpha | 100% | +$1,323 | -41.9% | -34.0% | ❌ REMOVE |

**60min**:
| Gate | Filter Rate | P&L Impact | WR Impact | DD Impact | Verdict |
|---|---|---|---|---|---|
| RiskManager | 57% | **+$1,475** | +0.6% | -33.8% | ✅ KEEP |
| PriceAction | 1% | -$19 | 0.0% | +0.19% | ❌ REMOVE |
| DeterAlpha | 100% | +$1,455 | -45.2% | -32.5% | ❌ REMOVE |

### Verdict

- **RiskManager**: Universally positive. Reduces trades by 57-81%, saves $1,475-$9,223 per timeframe, cuts drawdown by 34-92%. **KEEP everywhere.**
- **PriceAction**: Universally zero. Filters 0-1% of signals with no measurable impact on any metric. **REMOVE everywhere.**
- **DeterAlpha**: Universally broken. Blocks 100% of signals across all timeframes. Zero causal validation passes. **REMOVE everywhere.**

---

## Phase D — Minimal Pipeline

### Problem

The full pipeline burns CPU on useless gates (PriceAction, DeterAlpha) that provide zero or negative contribution.

### Implementation

**File changed**: `src/core/alpha_factory.py`

**Config toggle**:
```yaml
# alpha_factory_config.yaml
pipeline:
  mode: "minimal"   # "full" (default) or "minimal"
```

In minimal mode, the V4 loop skips PriceAction and DeterAlpha entirely:

```
SignalFactory → RiskManager → pre-sized TradeSignal → Execution
```

The RiskManager's existing gates (proba_alpha, drawdown, circuit breaker, daily limits, exposure) provide all necessary risk protection. PriceAction and DeterAlpha add computation cost with zero benefit.

### Wilson LB Recalibration

| | Zone Labels | Trade Labels |
|---|---|---|
| Wilson LB range | 0.00–0.15 | **0.07–0.75** |
| Median | 0.03 | **0.39** |
| % above 0.65 | 0% | **~18%** |

The `RiskManager.min_proba_alpha=0.65` default was impossible with zone labels (0% pass rate). With trade labels, it automatically becomes a functional gate filtering ~82% of signals and passing only the top 18% by Wilson LB. **No code change needed** — the trade-label retraining fixed the calibration automatically.

### Performance

The minimal pipeline (Stage 1) metrics are identical to the full pipeline because PriceAction and DeterAlpha were already contributing nothing. The benefit is operational: fewer computations per bar, lower latency, simpler debugging.

---

## Three-Timeframe Implementation

### Method

The system does **not** combine timeframes in a coordinated way. It runs three **independent** trading systems sharing one capital pool.

**1. Bar Resampling** (`src/data/orchestrator.py` — `MultiTimeframeResampler`):
```
Every 5min bar  → "micro" (1×)
Every 3 micro bars  → "intermediate" (3×5min = 15min)
Every 12 micro bars → "macro" (12×5min = 60min)
```
The resampler accumulates 5min rows and emits aggregated OHLCV bars when the count reaches the multiplier. Higher-TF bars are computed from the same underlying 5min data.

**2. Strategy Discovery** (`scripts/signal_factory_simulation.py`):
Each timeframe CSV is processed independently. The hub stores strategies per TF key:
```json
{
  "timeframes": {
    "5":  {"strategies": [60 strategies]},
    "15": {"strategies": [59 strategies]},
    "60": {"strategies": [55 strategies]}
  }
}
```
There is **zero** information sharing between timeframes during discovery. Each TF's strategies are built from that TF's zones, labels, and features.

**3. Signal Evaluation** (`src/core/signal_factory.py` — `SignalHub`):
```python
self.strategies = {
    ("BTCUSDT", "5"):  [60 LiveStrategy],
    ("BTCUSDT", "15"): [59 LiveStrategy],
    ("BTCUSDT", "60"): [55 LiveStrategy],
}

def evaluate(self, symbol, timeframe, feature_row, features_df):
    key = (symbol, timeframe)
    strategies = self.strategies.get(key, [])  # only that TF's strategies
```
No cross-timeframe evaluation. A 5min bar only evaluates 5min strategies. A 60min bar only evaluates 60min strategies.

**4. Trade Execution** (`src/core/alpha_factory.py`):
Each timeframe's signals flow independently:
```
5min bar  → SignalHub(5min)  → RiskManager → Execution
15min bar → SignalHub(15min) → RiskManager → Execution
60min bar → SignalHub(60min) → RiskManager → Execution
```
No position netting. No conflict resolution. A 5min long and 60min short can fire simultaneously and both execute.

### Three-Timeframe Results — Stage 1 (RiskManager)

| Metric | 5min | 15min | 60min | All 3 Combined |
|---|---|---|---|---|
| Trades | 321 | 1,085 | 1,475 | 2,881 |
| Win Rate | 37.7% | 41.9% | 45.2% | 43.1% |
| Profit Factor | 0.31 | 0.46 | 0.83 | — |
| P&L | **-$777** | -$3,306 | -$3,084 | **-$7,167** |
| Max DD | **7.93%** | 34.03% | 32.52% | — |

### Why higher timeframes lose more money despite higher WR

ATR-based SL/TP creates a paradox: higher timeframes have larger ATR values, so:
- SL is further from entry (1.5 × larger ATR)
- More room for adverse price movement before stop-out
- Larger realized losses when stopped out

A 60min bar covers 12× the price range of a 5min bar. Winning 45.2% of trades with 1.5×ATR stops on 60min data produces larger average losses than winning 37.7% on 5min data with tighter stops.

### Recommendation

**Disable 15min and 60min trading.** The 5min timeframe is the only viable one:
- Lowest absolute loss (-$777 vs -$3,306 and -$3,084)
- Lowest drawdown (7.93% vs 34.03% and 32.52%)
- Best risk-adjusted profile
- Trading all 3 simultaneously is 9× worse than 5min alone

```yaml
# Recommended config
signal_factory:
  enabled: true
  active_timeframes: ["5"]    # only trade 5min signals
```

---

## Cumulative Progress Tracking

| Metric | Baseline (zone, Wilson, full pipeline) | After Phase D (trade labels, net expectancy, minimal, 5min only) | Improvement |
|---|---|---|---|
| Trades | 1,193 | 321 | -73% |
| Win Rate | 32.9% | 37.7% | +4.8% |
| Profit Factor | 0.17 | 0.31 | +82% |
| P&L | -$3,454 | **-$777** | **-77% losses** |
| Max DD | 34.54% | **7.93%** | **-77% drawdown** |
| Gates in pipeline | 4 | 2 | -50% complexity |

---

## Files Changed

| File | Phase | What |
|---|---|---|
| `src/core/strategy_discovery.py` | A, B | `compute_trade_labels()`, `vote_features_at_bars()`, `evaluate_strategy_trade_labels()`, `rank_by_expectancy()`, `Strategy` fields |
| `src/core/layer_contribution.py` | C | **New** — `MarginalContribution`, `recommend_pipeline()`, `analyse_survival_logs()` |
| `src/core/alpha_factory.py` | D | `pipeline.mode` config toggle, minimal V4 loop path |
| `src/core/signal_factory.py` | A, B | `DSLParseError` import from `strategy_discovery` |
| `src/trading/nobitex_trader.py` | D | Pre-sized `TradeSignal` fields, dual-path `execute_signal()` |
| `src/risk/risk_manager.py` | D | `TradeRequest.margin_level` fix for audit |
| `scripts/signal_factory_simulation.py` | A | `--trade-labels` flag, branched `process_timeframe()` |
| `scripts/signal_factory_holdout.py` | A | Filtered pool export (`strategies_pool_final_*.json`) |

---

*Generated by Deep Code on 2026-06-14.*

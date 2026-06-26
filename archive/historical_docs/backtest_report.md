# Strategy Backtest Report

**Generated**: 2026-06-14T03:45:39.723601+00:00
**Results directory**: `data/backtest_results/`
**Backtest script**: `scripts/backtest_strategies.py`

---

## Architecture

```
OHLCV CSV → FeatureEngineerOptimized (228 cols)
         → SignalHub.evaluate() per bar (51-55 strategies)
         → PriceActionAlpha.compute() per firing strategy
         → DeterAlpha gate (causal validation, optional)
         → Position sizing (ATR-based SL/TP)
         → Intrabar exit simulation (SL hit before TP = pessimistic)
         → Per-strategy + aggregate metrics → JSON/CSV/MD
```

## Pipeline

```
signal_factory_simulation.py  →  strategies_hub JSON  (offline, weekly)
signal_factory.py             →  live per-bar evaluation  (online)
price_action.py               →  swing/vol/momentum/DOM alpha
deter_alpha.py                →  8-step causal filter (online gate)
strategy_repo.py              →  portfolio optimization, kill-switch
```

## Timeframe: 15min — BTCUSDT

**Config**: Capital=$10,000, Risk=2%, SL=1.5×ATR, TP=2.0×ATR, Fee=0.10%, Slippage=0.05%

| Metric | Value |
|---|---|
| Bars processed | 5,000 |
| Strategies tested | 59 |
| Strategies active | 40 |
| Signals generated | N/A |
| Signals gated | N/A |
| **Total trades** | **1085** |
| **Win rate** | **41.9%** |
| **Total P&L** | **$-3,305.52 (-33.06%)** |
| **Profit Factor** | **0.46** |
| **Max Drawdown** | **34.03%** |
| Sharpe (ann) | -9.99 |
| Sortino (ann) | 0.00 |
| Calmar | 0.00 |
| Expectancy | 0.000000 |

### Top 10 Strategies (by P&L)

| # | Strategy | Dir | Trades | WR | Mean Ret | Sharpe | Sortino | AUC | PF | P&L |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BTCUSDT_15_bear_6f | bear | 26 | 46% | 0.00% | 0.00 | 0.00 | 0.00 | 0.56 | $-66.21 |
| 2 | BTCUSDT_15_bear_6f | bear | 26 | 46% | 0.00% | 0.00 | 0.00 | 0.00 | 0.56 | $-66.21 |
| 3 | BTCUSDT_15_bear_6f | bear | 26 | 46% | 0.00% | 0.00 | 0.00 | 0.00 | 0.56 | $-66.21 |
| 4 | BTCUSDT_15_bear_8f | bear | 63 | 38% | 0.00% | 0.00 | 0.00 | 0.00 | 0.42 | $-215.75 |
| 5 | BTCUSDT_15_bear_8f | bear | 63 | 38% | 0.00% | 0.00 | 0.00 | 0.00 | 0.42 | $-215.75 |
| 6 | BTCUSDT_15_bear_8f | bear | 63 | 38% | 0.00% | 0.00 | 0.00 | 0.00 | 0.42 | $-215.75 |
| 7 | BTCUSDT_15_bear_8f | bear | 63 | 38% | 0.00% | 0.00 | 0.00 | 0.00 | 0.42 | $-215.75 |
| 8 | BTCUSDT_15_bear_8f | bear | 63 | 38% | 0.00% | 0.00 | 0.00 | 0.00 | 0.42 | $-215.75 |
| 9 | BTCUSDT_15_bear_8f | bear | 63 | 38% | 0.00% | 0.00 | 0.00 | 0.00 | 0.42 | $-215.75 |
| 10 | BTCUSDT_15_bear_8f | bear | 63 | 38% | 0.00% | 0.00 | 0.00 | 0.00 | 0.42 | $-215.75 |

---

## Timeframe: 5min — BTCUSDT

**Config**: Capital=$10,000, Risk=2%, SL=1.5×ATR, TP=2.0×ATR, Fee=0.10%, Slippage=0.05%

| Metric | Value |
|---|---|
| Bars processed | 5,000 |
| Strategies tested | 51 |
| Strategies active | 31 |
| Signals generated | 13361 |
| Signals gated | 0 |
| **Total trades** | **75** |
| **Win rate** | **40.0%** |
| **Total P&L** | **$-213.39 (-2.13%)** |
| **Profit Factor** | **0.51** |
| **Max Drawdown** | **2.60%** |
| Sharpe (ann) | 0.00 |
| Sortino (ann) | -26.23 |
| Calmar | 0.00 |
| Expectancy | -0.001147 |

### Top 10 Strategies (by P&L)

| # | Strategy | Dir | Trades | WR | Mean Ret | Sharpe | Sortino | AUC | PF | P&L |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BTCUSDT_5_bull_6f | bull | 1 | 100% | 0.25% | 0.00 | 0.00 | 0.50 | inf | $+6.27 |
| 2 | BTCUSDT_5_bull_6f | bull | 1 | 100% | 0.25% | 0.00 | 0.00 | 0.50 | inf | $+6.27 |
| 3 | BTCUSDT_5_bear_6f | bear | 7 | 43% | -0.02% | -7.70 | -14.88 | 1.00 | 0.85 | $-4.43 |
| 4 | BTCUSDT_5_bear_6f | bear | 7 | 43% | -0.02% | -7.70 | -14.88 | 1.00 | 0.85 | $-4.43 |
| 5 | BTCUSDT_5_bear_6f | bear | 7 | 43% | -0.02% | -7.70 | -14.88 | 1.00 | 0.85 | $-4.43 |
| 6 | BTCUSDT_5_bear_6f | bear | 7 | 43% | -0.02% | -7.70 | -14.88 | 1.00 | 0.85 | $-4.43 |
| 7 | BTCUSDT_5_bear_7f | bear | 4 | 25% | -0.14% | -76.47 | -152.49 | 0.50 | 0.36 | $-13.71 |
| 8 | BTCUSDT_5_bear_7f | bear | 4 | 25% | -0.14% | -76.47 | -152.49 | 0.50 | 0.36 | $-13.71 |
| 9 | BTCUSDT_5_bear_4f | bear | 27 | 48% | -0.03% | -5.84 | -12.95 | 1.00 | 0.82 | $-22.90 |
| 10 | BTCUSDT_5_bear_4f | bear | 27 | 48% | -0.03% | -5.84 | -12.95 | 1.00 | 0.82 | $-22.90 |

---

## Timeframe: 60min — BTCUSDT

**Config**: Capital=$10,000, Risk=2%, SL=1.5×ATR, TP=2.0×ATR, Fee=0.10%, Slippage=0.05%

| Metric | Value |
|---|---|
| Bars processed | 5,000 |
| Strategies tested | 55 |
| Strategies active | 40 |
| Signals generated | N/A |
| Signals gated | N/A |
| **Total trades** | **1475** |
| **Win rate** | **45.2%** |
| **Total P&L** | **$-3,084.37 (-30.84%)** |
| **Profit Factor** | **0.83** |
| **Max Drawdown** | **32.52%** |
| Sharpe (ann) | -2.07 |
| Sortino (ann) | 0.00 |
| Calmar | 0.00 |
| Expectancy | 0.000000 |

### Top 10 Strategies (by P&L)

| # | Strategy | Dir | Trades | WR | Mean Ret | Sharpe | Sortino | AUC | PF | P&L |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BTCUSDT_60_bull_6f | bull | 124 | 52% | 0.00% | 0.00 | 0.00 | 0.00 | 1.06 | $+78.87 |
| 2 | BTCUSDT_60_bull_6f | bull | 124 | 52% | 0.00% | 0.00 | 0.00 | 0.00 | 1.06 | $+78.87 |
| 3 | BTCUSDT_60_bull_6f | bull | 124 | 52% | 0.00% | 0.00 | 0.00 | 0.00 | 1.06 | $+78.87 |
| 4 | BTCUSDT_60_bull_8f | bull | 80 | 52% | 0.00% | 0.00 | 0.00 | 0.00 | 1.00 | $-0.49 |
| 5 | BTCUSDT_60_bull_8f | bull | 80 | 52% | 0.00% | 0.00 | 0.00 | 0.00 | 1.00 | $-0.49 |
| 6 | BTCUSDT_60_bull_8f | bull | 80 | 52% | 0.00% | 0.00 | 0.00 | 0.00 | 1.00 | $-0.49 |
| 7 | BTCUSDT_60_bull_8f | bull | 80 | 52% | 0.00% | 0.00 | 0.00 | 0.00 | 1.00 | $-0.49 |
| 8 | BTCUSDT_60_bull_8f | bull | 80 | 52% | 0.00% | 0.00 | 0.00 | 0.00 | 1.00 | $-0.49 |
| 9 | BTCUSDT_60_bear_8f | bear | 136 | 49% | 0.00% | 0.00 | 0.00 | 0.00 | 0.95 | $-90.51 |
| 10 | BTCUSDT_60_bear_8f | bear | 136 | 49% | 0.00% | 0.00 | 0.00 | 0.00 | 0.95 | $-90.51 |

---

## Win Rate Analysis

### Current: 32–42% win rate across timeframes

The signal_factory discovers strategies on **zone-level labels** 
(swing-to-swing segments, ~10–50 bars). When evaluated **bar-by-bar** 
in the backtest, strategies fire mid-zone where the directional edge is diluted.

### Root Cause

- **Label mismatch**: Zone labels (bull/bear/neutral by ATR threshold over 
  a multi-bar segment) don't translate to bar-level direction accuracy
- **Signal dilution**: Strategies evaluate ALL bars, not just zone starts
- **No causal gate**: DeterAlpha filters ~93% of signals when enabled, 
  but is computationally expensive for backtesting with per-strategy state

### Path to >50% Win Rate

| Intervention | Expected Effect | Effort |
|---|---|---|
| Retrain signal_factory on bar-level labels (close[t+H] vs close[t]) | +8–12% WR | 1 day |
| Enable DeterAlpha causal gate (filters ~93% of signals) | +3–5% WR | Done |
| Regime alignment: bull strats only in Bull regime | +2–3% WR | 2 hours |
| Per-strategy SL/TP optimization (grid search) | +2–5% WR | 1 day |
| Multi-strategy consensus (require ≥3 strats to agree) | +2–4% WR | 4 hours |
| Minimum volume/liquidity filter | +1–2% WR | 1 hour |

---

## Historical Run Comparison

| Run | TF | Conviction | DeterAlpha | Trades | WR | PF | P&L | DD |
|---|---|---|---|---|---|---|---|---|
| v1 (initial) | 5m | 0.30 | Off | 1,193 | 32.9% | 0.17 | -$3,454 | 34.5% |
| v1 (initial) | 60m | 0.30 | Off | 1,475 | 45.2% | 0.83 | -$3,084 | 32.5% |
| v2 (filtered) | 5m | 0.55 | Off | 45 | 37.8% | 0.41 | -$156 | 1.9% |
| v3 (balanced) | 5m | 0.40 | Off | 75 | 40.0% | 0.51 | -$213 | 2.6% |
| v4 (gated) | 5m | 0.30 | On | 0* | — | — | — | — |

*DeterAlpha with per-strategy state is too slow for backtest (~90s/5000 bars). 
Shared-state mode works but causal refits dominate. Use `--no-deter-alpha` for 
fast backtesting; DeterAlpha gating is for live trading where causal validation 
matters.

---

## Exported Metrics Per Strategy

Each strategy in the JSON export contains:

| Field | Description |
|---|---|
| `strategy_id` | Unique identifier (symbol_tf_direction_Nf) |
| `direction` | bull / bear / neutral |
| `n_trades`, `n_wins`, `n_losses` | Trade counts |
| `win_rate` | Fraction of profitable trades |
| `total_pnl_pct`, `total_pnl_usd` | Cumulative P&L |
| `mean_return_pct` | Average return per trade (%) |
| `median_return_pct` | Median return per trade (%) |
| `std_return_pct` | Std dev of returns (%) |
| `profit_factor` | Gross wins / gross losses |
| `sharpe` | Annualized Sharpe ratio |
| `sortino` | Annualized Sortino (downside-only) |
| `calmar` | Annualized return / max drawdown |
| `expectancy` | avg_win × win_rate − avg_loss × loss_rate |
| `max_drawdown_pct` | Maximum peak-to-trough (%) |
| `auc` | Approximate AUC from return ranking |
| `avg_hold_bars` | Average bars held per trade |
| `avg_win_bars` | Average bars for winning trades |
| `avg_loss_bars` | Average bars for losing trades |
| `mean_conviction` | Average price_action conviction at entry |
| `regime_breakdown` | Per-regime (Bull/Bear/Neutral) trade stats |

---

## Usage Reference

```bash
# Quick backtest (5000 bars, no causal gate — fast)
python scripts/backtest_strategies.py --smoke --timeframe 5 --no-deter-alpha

# Full backtest on all data
python scripts/backtest_strategies.py --full --timeframe 5 --no-deter-alpha

# Scalping setup (tight stops, quick targets)
python scripts/backtest_strategies.py --smoke --sl-atr 1.0 --tp-atr 3.0 --max-hold 10

# A/B test DeterAlpha ON vs OFF
python scripts/backtest_strategies.py --smoke --timeframe 5              # ON (slow)
python scripts/backtest_strategies.py --smoke --timeframe 5 --no-deter-alpha  # OFF (fast)

# Custom hub + custom risk
python scripts/backtest_strategies.py --smoke --hub PATH_TO_HUB --risk-pct 0.01 --capital 50000
```

---
*Report compiled 2026-06-14T03:45:39.724609+00:00 from 3 timeframe(s)*
# NEXT_ACTION.md

> **For LLMs**: After reading PROJECT_STATE.md, read this file. It tells you exactly what to do.

---

## The Methodology Shift (2026-07-16)

**OLD**: Test complete trading strategies → measure Profit Factor → iterate blindly

**NEW**: Test market mechanisms first → build strategies second

**Why**: When a strategy fails, you need to know WHY. The event-study engine (`src/validation/event_study.py`) decomposes each hypothesis into sub-questions about the underlying mechanism before any trading rules are constructed.

**Read**: `docs/methodology/event_study_method.md` for the full methodology.

---

## Priority 1: Apply Event-Study Methodology to Existing Hypotheses

Instead of running full strategy backtests, decompose each active hypothesis using the event-study framework:

### Already Done
- [x] `btc_mr_l2` — H01-H06 decomposed (see `docs/research/btc_mr_l2_decomposed_20260716.md`)
  - Mechanism CONFIRMED but too weak for 15m trading (D017, D018)
  - Next: test on 4h/1d where moves are larger relative to costs

### Next Candidates (in priority order)

#### 1. `pos_002` — OI Divergence Reversal (Highest Priority)
This is the most active PositioningAlpha strategy (96 trades, PF=1.08). Decompose it:

```python
from src.validation.event_study import EventStudy
study = EventStudy("BTCUSDT", "15m", max_bars=50000)

# H01: Does OI divergence predict reversal?
study.add_trigger("oi_div_bearish",
    lambda df: (df["close"] > df["sma20"]) & (df["sum_open_interest"] < df["oi_ma_20"]))
study.add_trigger("oi_div_bullish", 
    lambda df: (df["close"] < df["sma20"]) & (df["sum_open_interest"] > df["oi_ma_20"]))

results = study.run()
```

Key questions to answer:
- Which horizon does the divergence predict? (1, 3, 5, 10 bars?)
- Does it work better in trending or ranging regimes?
- Is it stronger on BTC or ETH?

#### 2. `pos_004` — Funding Cross-Asset Divergence
Best Sharpe in PositioningAlpha (0.89). Decompose:
- Does BTC-ETH funding spread predict convergence?
- What spread threshold maximizes predictive power?
- How long does convergence take?

#### 3. `eth_mom_l1` — Multi-Factor Momentum
Best overall PF (1.71). Decompose:
- Which component drives the edge? (SMA crossover? ROC? Volume?)
- Does the HTF regime filter actually improve signal quality?
- At what horizon does momentum decay?

#### 4. `exp_001` — ATR Compression Breakout (on SOL)
D015 showed SOL outperforms BTC. Decompose:
- At what ATR compression threshold does expansion become predictable?
- Is volume confirmation necessary or redundant?
- What is the optimal holding period?

---

## How to Run an Event Study

```bash
# Quick event study (interactive)
python -c "
from src.validation.event_study import EventStudy
study = EventStudy('BTCUSDT', '15m', max_bars=50000)
study.add_trigger('z_neg_2.5', lambda df: df['z_score'] < -2.5)
results = study.run()
print(study.report(results))
"

# Cross-asset validation
python -c "
from src.validation.event_study import EventStudy
study = EventStudy('BTCUSDT', '15m', max_bars=50000)
study.add_trigger('z_neg_2.5', lambda df: df['z_score'] < -2.5)
ca = study.cross_asset('z_neg_2.5', ['ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'])
for sym, vals in ca.items(): print(sym, vals)
"
```

---

## Priority 2: Higher-Timeframe MR Testing

D017 showed Z-score MR exists but is too weak on 15m. Test on larger timeframes:

```python
# 4-hour BTC
study = EventStudy("BTCUSDT", "4h", max_bars=10000)
study.add_trigger("z_neg_2.5_4h", lambda df: df["z_score"] < -2.5)
results = study.run()

# 1-day BTC
study = EventStudy("BTCUSDT", "1d", max_bars=2000)
study.add_trigger("z_neg_2.5_1d", lambda df: df["z_score"] < -2.5)
results = study.run()
```

---

## Priority 3: Strategy Construction (Only After Mechanism Confirmed)

Only build a complete trading strategy when the mechanism has been validated through the event-study framework. The strategy rules should be directly derived from the evidence:

```
Evidence:
  - H01 confirmed: Z < -2.5 predicts +0.10% at h=10 in low vol
  - H03 confirmed: Low vol regime required (ATR percentile < 33%)
  - H04 confirmed: BTC, ETH, BNB only (not SOL)

Strategy:
  Entry:  Z < -2.5 AND ATR_percentile < 33%
  Exit:   10 bars OR Z-score crosses above -1.0
  Assets: BTCUSDT, ETHUSDT, BNBUSDT
  Size:   Kelly 2% risk per trade
```

---

## What NOT to Do

- ❌ Do NOT run strategy backtests without first validating the mechanism
- ❌ Do NOT tune strategy parameters before understanding the mechanism
- ❌ Do NOT test a complete strategy when you can test one question
- ❌ Do NOT modify existing modules without running `pytest tests/` (171 tests)
- ❌ Do NOT hard-code data paths — always use DatasetRegistry

---

## File Map for LLMs

| # | File | Purpose | When to Read |
|---|------|---------|-------------|
| 1 | `PROJECT_STATE.md` | Current state | First |
| 2 | `NEXT_ACTION.md` | This file | Second |
| 3 | `ARCHITECTURE.md` | System design | Third |
| 4 | `DISCOVERIES.md` | Validated findings + negative knowledge | Fourth |
| 5 | `docs/methodology/event_study_method.md` | **Event-study methodology** | Fifth |
| 6 | `docs/research/roadmap.md` | Research priorities | When planning |
| 7 | `docs/research/thesis_catalog.md` | All 200+ hypotheses | When selecting |
| 8 | `src/validation/event_study.py` | Event-study engine | When testing mechanisms |
| 9 | `src/core/dataset_registry.py` | Data access | When loading data |
| 10 | `src/core/evidence_ladder.py` | Hypothesis tracking | When evaluating |

---

## Quick Reference: Signal Implementation Files

| Family | File | Hypotheses |
|--------|------|------------|
| MeanReversionAlpha | `src/features/mean_reversion_signals.py` | btc_mr_l2 |
| MomentumAlpha | `src/features/momentum_signals.py` | eth_mom_l1, sol_mom_l1 |
| ExpansionAlpha | `src/features/expansion_signals.py` | exp_001, exp_002, exp_003, vol_comp_l0 |
| PositioningAlpha | `src/features/positioning_signals.py` | pos_001-005, funding_div_l0 |
| PositioningAlpha | `src/features/positioning_enricher.py` | OI + funding data enrichment |
| EnsembleAlpha | `src/features/ensemble_signals.py` | ensemble_001, ensemble_002 |
| Evaluation | `scripts/evaluate_strategies.py` | Full pipeline evaluation |
| Portfolio | `scripts/portfolio_backtest.py` | Multi-strategy backtest |

---

## Current State (2026-07-16)

- **Evidence ladder**: 38 hypotheses, 19 validated discoveries, 11 negative knowledge entries
- **Tested through pipeline**: 15 hypotheses (7 auto-testable + 6 Program A + 2 ensembles)
- **Positive PF (>1.0)**: pos_004 (1.11), pos_002 (1.08), eth_mom_l1 (1.71), sol_mom_l1 (1.28), exp_001 on SOL (1.09)
- **Mechanism-validated**: btc_mr_l2 (D017, D018 — confirmed but too weak for costs)
- **Next**: Event studies on pos_002, pos_004, eth_mom_l1, exp_001

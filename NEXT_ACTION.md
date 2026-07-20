# NEXT_ACTION.md

> **For LLMs**: After reading PROJECT_STATE.md, read this file. It tells you exactly what to do.
> **ARCHITECTURE FREEZE v1.0** — No new modules. No new registries. No new graphs. Only bug fixes and experiments.

---

## The Methodology (2026-07-16)

Every hypothesis must trace a causal chain: **Cause → Mechanism → Observable → Prediction**.

```
Liquidity Crunch → M001 (Liquidity Exhaustion) → Z-score → Reversal
Institutional Flow → M002 (Trend Continuation) → Momentum → Continuation
Profit Taking     → M003 (Position Unwind)      → OI Div   → Reversal
```

**Read**: `docs/methodology/event_study_method.md` for the full methodology.

---

## Priority 1: Event Study on RP003 — Position Unwind (OI Divergence)

**Why first**: pos_002 produced PF=1.08 with 96 trades — the most active positive strategy. But the mechanism was never validated. Confirming or rejecting M003 will reduce more uncertainty than refining already-understood M001.

### H01: Does OI divergence predict reversal?

```python
from src.validation.event_study import EventStudy
from src.features.positioning_enricher import enrich_ohlcv, clear_cache
from src.core.dataset_registry import registry
clear_cache()

# Load and enrich BTC 15m data
df = registry.get_ohlcv("binance", "BTCUSDT", "15m")
df = df.iloc[-50000:].copy().reset_index()
df = enrich_ohlcv(df, "BTCUSDT")
df = df.reset_index()

study = EventStudy("BTCUSDT", "15m", max_bars=50000)

# Bearish OI divergence: price up + OI down → short
study.add_trigger("oi_div_bearish", lambda d:
    (d["close"] > d["sma20"]) & (d["sum_open_interest"] < d["oi_ma_20"]))

# Bullish OI divergence: price down + OI up → long
study.add_trigger("oi_div_bullish", lambda d:
    (d["close"] < d["sma20"]) & (d["sum_open_interest"] > d["oi_ma_20"]))

results = study.run()

# H03: Regime dependence (where does it work?)
# boundaries = study.find_boundaries("oi_div_bearish", "atr_percentile")

# H04/H05: Cross-asset + interaction
# ca = study.cross_asset("oi_div_bearish", ["ETHUSDT", "SOLUSDT", "BNBUSDT"])
# interaction = study.interaction_study("oi_div_bearish", "atr_percentile", "regime_trend")
```

**Questions to answer**:
- Does OI divergence predict reversal at p < 0.05?
- At which horizon (1, 3, 5, 10, 20)?
- Which regime? (vol, trend, volume)
- Which assets? (ETH, SOL, BNB)
- What's the OI_div × vol_regime interaction?

---

## Priority 2: Event Study on RP002 — Trend Continuation (Momentum)

**Why second**: M002 is our highest-confidence mechanism (0.140) but has zero completed sub-hypotheses. eth_mom_l1 produced PF=1.71 — the best individual result — but we don't know WHICH component drives it.

### Decompose the multi-factor momentum signal

```python
study = EventStudy("ETHUSDT", "1h", max_bars=20000)

# SMA crossover (10/30)
study.add_trigger("sma_golden_cross", lambda d:
    (d["sma10"].shift(1) <= d["sma30"].shift(1)) & (d["sma10"] > d["sma30"]))

# Rate of Change (5-bar > 0.2%)
study.add_trigger("roc_strong", lambda d:
    (d["close"] - d["close"].shift(5)) / d["close"].shift(5) > 0.002)

# Volume confirmation
study.add_trigger("volume_above_median", lambda d:
    d["volume"] > d["volume"].rolling(20).median())

# HTF regime alignment (SMA50 > SMA100)
study.add_trigger("htf_bull_aligned", lambda d:
    d["sma50"] > d["sma100"])

# Combined (current eth_mom_l1 signal)
study.add_trigger("momentum_full", lambda d:
    ((d["sma10"].shift(1) <= d["sma30"].shift(1)) & (d["sma10"] > d["sma30"]) |
     (d["sma10"] > d["sma30"]) & ((d["close"]-d["close"].shift(5))/d["close"].shift(5) > 0.002)) &
    (d["volume"] > d["volume"].rolling(20).median() * 0.8) &
    (d["sma50"] > d["sma100"]))

results = study.run()
```

**Questions to answer**:
- Which component (SMA crossover, ROC, volume, HTF) contributes most?
- Are components additive or redundant?
- At what horizon does momentum decay?
- Does it work on SOL?

---

## Priority 3: Mechanism Replication

After a mechanism is confirmed on one asset, replicate across others **before** building a strategy:

```
BTC → ETH → SOL → BNB → XRP → DOGE
```

Only after replication across 3+ assets should strategy construction begin.

---

## Priority 4: Interaction Studies (Only After Individual Mechanisms Are Validated)

```python
# H202: M001 + M002 + M003 — top-ranked by research cost optimizer
study.interaction_study("z_neg_2.5", "regime_trend", "oi_divergence")
```

---

## Priority 5: Strategy Construction (Only After Mechanism Validated + Replicated)

Only when a mechanism has been:
1. Confirmed via event study (H01-H04)
2. Found to be economically viable (effect size > transaction costs)
3. Replicated across 3+ assets

Should a strategy be built. The strategy rules must be directly derived from the evidence, not optimized:

```
Evidence:
  - H01: OI divergence predicts +8bp at h=5, p=0.03
  - H03: Works best in neutral trend, low vol
  - H04: Confirmed on BTC + ETH, NOT on SOL

Strategy:
  Entry:  OI divergence AND atr_percentile < 33% AND regime_trend = neutral
  Exit:   5 bars OR OI convergence (close crosses SMA20)
  Assets: BTCUSDT, ETHUSDT
```

---

## What NOT to Do

- ❌ Do NOT add new architecture modules (Freeze v1.0)
- ❌ Do NOT run strategy backtests without first validating the mechanism
- ❌ Do NOT tune strategy parameters before understanding the mechanism
- ❌ Do NOT test hypotheses without a causal chain in the graph
- ❌ Do NOT build strategies before replicating mechanisms across 3+ assets
- ❌ Do NOT modify existing modules without running `pytest tests/` (171 tests)

---

## Quick Reference

| Tool | How to Use |
|------|-----------|
| Event study | `from src.validation.event_study import EventStudy` |
| Mechanism confidence | `from src.core.mechanism_registry import registry` |
| Causal chains | `from src.core.causal_graph import causal_graph` |
| Auto hypothesis gen | `causal_graph.suggest_hypotheses()` |
| Cost-optimized ranking | `registry.research_cost_optimize()` |
| OI data enrichment | `from src.features.positioning_enricher import enrich_ohlcv` |
| Full pipeline eval | `python scripts/evaluate_strategies.py --hypothesis pos_002` |
| Test suite | `pytest tests/` (171 tests) |

---

## Current State (2026-07-16)

| Component | Status |
|-----------|--------|
| Architecture | **Freeze v1.0** — 6 signal families, mechanism registry (M001-M005), causal graph, event-study engine |
| Evidence ladder | 38 hypotheses, 19 validated discoveries (9 structural, 9 tactical), 11 negative knowledge |
| RP001 (Liquidity Exhaustion) | **Completed** — mechanism confirmed but too weak for 15m |
| RP002 (Trend Continuation) | **Not started** — highest-confidence mechanism, 0/6 hypotheses |
| RP003 (Position Unwind) | **In progress** — OI divergence, best active strategy |
| Next | Execute RP003 event study, then RP002, then interaction H202 |

# Alpha_v6 — Project State

> **For LLMs**: Read this file first. It tells you everything you need to know in one page.

## What Is This?

Alpha_v6 is an **institutional Alpha Research Platform** for cryptocurrency markets.

It systematically generates, tests, rejects, and refines trading hypotheses. It is NOT a trading bot — it is a research factory that produces validated alpha streams, which can then be deployed by a separate execution layer.

## Current Status (2026-06-26)

| Metric | Value |
|--------|-------|
| Active hypotheses | 36 |
| Archived hypotheses | 5 |
| Research programs | 10 |
| Potential hypotheses | ~200 |
| Deployed to production | 0 |

### Evidence Ladder

```
L0 (intuition)     ████████████████████████████████ 33
L1 (in-sample)     ██ 2
L2 (costs)         █ 1
L3 (walk-forward)  ░ 0
L4 (cross-asset)   ░ 0
L5 (paper trading) ░ 0
L6 (production)    ░ 0
```

**No hypothesis has yet reached production.**

## Core Infrastructure (Ready)

| Module | Purpose |
|--------|---------|
| `dataset_registry.py` | Centralized data access (65 datasets, 3 exchanges) |
| `evidence_ladder.py` | L0-L6 classification + multi-dimensional scoring |
| `research_pipeline.py` | 10-stage automated hypothesis evaluation |
| `alpha_engine.py` | Portfolio allocation (Kelly, risk parity, vol targeting) |
| `experiment_manager.py` | Standardized experiment execution |
| `knowledge_base.py` | Persistent research findings (8 observations) |
| `paper_trading.py` | Stage 9 monitoring skeleton |
| `production_gate.py` | Stage 10 deployment safety (10 checks + circuit breakers) |
| `backtest/engine.py` | Event-driven backtester with realistic costs |

## Data Available

- **65 datasets** across binance, lbank, nobitex
- **8 symbols**: BTC, ETH, SOL, BNB, XRP, DOGE, LINK, TON
- **5 timeframes**: 5m, 15m, 1h, 4h, 1d
- **Funding rate** data available for binance

## Research Programs (Priority Order)

| # | Program | Expected Value | Hypotheses |
|---|---------|---------------|------------|
| A | Open Interest + Funding | ★★★★★ | ~35 |
| B | Cross-Sectional Momentum | ★★★★★ | ~30 |
| C | Volatility Expansion | ★★★★☆ | ~20 |
| D | Liquidations | ★★★★☆ | ~15 |
| E | Market Microstructure | ★★★★☆ | ~30 |
| F | Multi-Timeframe Context | ★★★☆☆ | ~15 |
| G | Relative Value | ★★★☆☆ | ~15 |
| H | Machine Learning | ★★☆☆☆ | ~30 |
| I | Portfolio Construction | ★★☆☆☆ | ~15 |
| J | Execution Research | ★★☆☆☆ | ~20 |

## Key Discoveries (Knowledge Base)

1. BTC ≠ ETH — strategies don't transfer blindly
2. Z-score > percentage stretch for mean-reversion
3. Walk-forward kills 30-60% of in-sample PF
4. Transaction costs destroy many apparent alphas
5. Funding alone is weak — must combine with OI
6. MTF context significantly impacts LTF strategy performance
7. SOL has distinct momentum characteristics from BTC
8. Microstructure differs meaningfully across assets

## Test Coverage

**171 tests, all passing.**

## Immediate Goal

Get ONE hypothesis through all 10 pipeline stages into production with minimal capital — to validate the execution infrastructure. Not to make money. To prove the pipeline works end-to-end.

## Entry Files for LLMs

| # | File | Purpose |
|---|------|---------|
| 1 | `PROJECT_STATE.md` | Current state — read first |
| 2 | `NEXT_ACTION.md` | Exact instructions — read second |
| 3 | `ARCHITECTURE.md` | System design — read third |
| 4 | `DISCOVERIES.md` | **Validated empirical findings** — scientific notebook |

## Auto-Generated Research Papers

Every experiment automatically produces a paper in `docs/research/results/`:

```
docs/research/results/
  2026-06-26_btc_mr_l2_BTCUSDT_15m.md
  2026-06-27_eth_mom_l1_ETHUSDT_60m.md
  ...
```

Each paper contains: Hypothesis, Data, Method, Results, Statistics, Limitations, Decision, Next Step.

## Knowledge Graph

Structured relationships between all research entities. Seeded with 40+ edges.
Queryable: "Which hypotheses are invalid because D005 is true?"

```python
from src.core.knowledge_graph import knowledge_graph
knowledge_graph.load()
knowledge_graph.query("btc_mr_l2")  # all related entities
knowledge_graph.query_question("failed hypotheses involving funding")
```

## Research Roadmap

Sequential priorities at `docs/research/roadmap.md`:
**Now: ONE hypothesis to production → Program A (OI+Funding) → Program B (Cross-Sectional) → ...**

## Research Scoreboard

```bash
python scripts/show_scoreboard.py          # Full display
python scripts/show_scoreboard.py --compact # Single line
python scripts/show_scoreboard.py --json    # JSON output
```

Tracks research productivity: hypotheses proposed, experiments completed, rejections, discoveries confirmed, pipeline progression by level.


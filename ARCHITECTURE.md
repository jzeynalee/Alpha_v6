# ARCHITECTURE.md

> **For LLMs**: Read this third. It describes the system design at every level.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Alpha_v6 Research Platform                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  Dataset      │    │  Experiment   │    │  Research Knowledge  │   │
│  │  Registry     │───▶│  Manager      │───▶│  Base                │   │
│  │               │    │               │    │                      │   │
│  │ 65 datasets   │    │ Full lifecycle│    │ 8+ observations      │   │
│  │ 3 exchanges   │    │ data→signal→  │    │ confidence levels    │   │
│  │ 8 symbols     │    │ backtest→     │    │ hypothesis links     │   │
│  └──────────────┘    │ evaluate→     │    └──────────────────────┘   │
│                       │ ladder update │                              │
│  ┌──────────────┐    └──────────────┘    ┌──────────────────────┐   │
│  │  Evidence     │                       │  Alpha Engine         │   │
│  │  Ladder       │◀──────────────────────│                       │   │
│  │               │                       │  Kelly sizing         │   │
│  │ L0-L6 levels  │                       │  Risk parity          │   │
│  │ 8-axis score  │                       │  Correlation budget   │   │
│  │ 41 hypotheses │                       │  Vol targeting        │   │
│  └──────────────┘                       └──────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Research Pipeline (10 stages)                                 │   │
│  │                                                               │   │
│  │  1. Economic Explanation  →  2. In-Sample  →  3. Walk-Forward│   │
│  │  4. Bootstrap            →  5. Outlier     →  6. Costs        │   │
│  │  7. Regime Stability     →  8. Cross-Asset →  9. Paper Trading│   │
│  │  10. Production Gate                                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  Backtest     │    │  Production   │    │  LLM Interface        │   │
│  │  Engine       │    │  Gate         │    │                       │   │
│  │               │    │               │    │  project_memory.py    │   │
│  │ Event-driven  │    │ 10 checks     │    │  context_builder.py   │   │
│  │ Realistic     │    │ Circuit       │    │  repo_summary.py      │   │
│  │ costs/fills   │    │ breakers      │    │  prompt_generator.py  │   │
│  └──────────────┘    └──────────────┘    └──────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
Alpha_v6/
│
├── PROJECT_STATE.md          ← LLM reads FIRST
├── NEXT_ACTION.md            ← LLM reads SECOND
├── ARCHITECTURE.md           ← LLM reads THIRD (this file)
│
├── docs/
│   ├── research/             ← Roadmaps, thesis catalog, research log
│   ├── architecture/         ← System design, data flow, experiment pipeline
│   ├── knowledge/            ← Observations, economic theories, microstructure
│   ├── methodology/          ← Research methodologies, statistical proofs
│   │   └── event_study_method.md
│   └── reports/              ← Experiment reports (auto-generated)
│
├── data/
│   ├── raw/                  ← OHLCV, funding, OI (symlink to v5 data)
│   ├── processed/            ← Derived datasets
│   ├── features/             ← Cached features
│   ├── experiments/          ← Experiment results (one dir per experiment)
│   ├── paper_trading/        ← Paper trading journals
│   └── production/           ← Production state
│
├── src/
│   ├── core/                 ← Platform infrastructure (not strategies)
│   ├── data/                 ← Data collection, validation, versioning
│   ├── features/             ← Feature engineering
│   ├── hypotheses/           ← Hypothesis definitions per research program
│   ├── experiments/          ← Experiment execution scripts
│   ├── strategies/           ← Strategy implementations (alpha families)
│   ├── portfolio/            ← Portfolio construction
│   ├── execution/            ← Order execution (TWAP, VWAP, maker/taker)
│   ├── evaluation/           ← Performance metrics, attribution
│   ├── production/           ← Production monitoring, alerts
│   ├── backtest/             ← Backtest engine
│   ├── risk/                 ← Risk management
│   ├── validation/           ← Hypothesis validation
│   ├── cv/                   ← Cross-validation (walk-forward)
│   ├── utils/                ← Utilities
│   └── llm/                  ← LLM-friendly interface
│       ├── project_memory.py
│       ├── context_builder.py
│       ├── repo_summary.py
│       └── prompt_generator.py
│
├── scripts/                  ← CLI entry points
├── tests/                    ← Test suite
└── archive/                  ← Historical v5 docs (not in working tree)
    ├── reports/
    ├── roadmaps/
    └── historical_docs/
```

## Core Modules (Long-Term Assets)

### `src/core/dataset_registry.py`
**Centralized data access. No module should ever write `Path("data/raw")`.**
- Scans data directory tree, builds inventory
- `registry.get_ohlcv(exchange, symbol, timeframe)` — the ONE way to load data
- Supports binance, lbank, nobitex; 65+ datasets indexed

### `src/core/evidence_ladder.py`
**Hypothesis classification + multi-dimensional scoring.**
- `EvidenceLevel`: L0 (intuition) through L6 (production)
- `HypothesisRecord`: Full lifecycle tracking with stage results
- `EvidenceScore`: 8-axis weighted scoring (v2)
- JSON persistence at `data/experiments/evidence_ladder.json`

### `src/core/research_pipeline.py`
**10-stage automated hypothesis evaluation.**
- Runs stages in order, auto-promotes on success, demotes to L0 on failure
- Built-in evaluators: bootstrap, outlier robustness, regime stability
- `PipelineContext`: Configurable thresholds for each stage

### `src/core/experiment_manager.py`
**Standardized experiment execution.**
- `ExperimentSpec`: What to run (hypothesis + symbol + timeframe + stages)
- `ExperimentManager`: Full lifecycle: data→signal→backtest→evaluate→ladder
- Batch runner, family runner, L0 runner

### `src/core/knowledge_base.py`
**Persistent research findings.**
- `Observation`: Finding with confidence level (1-5), supporting experiments, domain
- 8 seeded discoveries from 2025-2026 research
- Query by domain, confidence, related hypothesis; citation support

### `src/core/alpha_engine.py`
**Multi-strategy portfolio allocator.**
- Kelly sizing + risk parity + correlation budget + vol targeting
- Evidence-level multipliers (L3=0.25×, L4=0.50×, L5=0.75×, L6=1.0×)
- Regime-aware allocation, drawdown scaling, entropy penalty

### `src/core/paper_trading.py`
**Stage 9 monitoring skeleton.**
- `PaperTradingTracker`: Trade journal, daily snapshots, live metrics
- Promotion readiness: days ≥ 30, PF > 1.0

### `src/core/production_gate.py`
**Stage 10 deployment safety.**
- `ProductionGate`: 10 safety checks + per-bar circuit breakers
- Kill switch, daily loss limit, drawdown limit, consecutive loss limit

## Research Pipeline (10 Stages)

| Stage | Name | Gate | Evidence Level |
|-------|------|------|---------------|
| 1 | Economic Explanation | Manual | L0 |
| 2 | In-Sample Discovery | Automated | L1 |
| 3 | Walk-Forward Validation | Automated | L3 |
| 4 | Bootstrap | Automated | L3 |
| 5 | Outlier Robustness | Automated | L3 |
| 6 | Transaction Costs | Automated | L2 |
| 7 | Regime Stability | Automated | L4 |
| 8 | Cross-Asset Validation | Automated | L4 |
| 9 | Paper Trading | Semi-auto | L5 |
| 10 | Production | Semi-auto | L6 |

Failure at any stage → demote to L0 (research backlog).

## Data Flow

```
Exchange APIs
    ↓
data/raw/ (OHLCV, funding, OI CSV files)
    ↓
DatasetRegistry (indexed inventory)
    ↓
ExperimentManager (loads data, runs backtest)
    ↓
EvidenceLadder (records results, promotes/demotes)
    ↓
AlphaEngine (allocates to validated streams)
    ↓
ProductionGate (safety checks)
    ↓
Execution (live trading)
```

## Design Principles

1. **No hard-coded paths** — always use DatasetRegistry
2. **No standalone reports** — findings go in KnowledgeBase
3. **No hypothesis conclusion in name** — the ladder tells you
4. **One experiment format** — ExperimentManager is the only way to run
5. **Tests before changes** — 171+ tests must pass before any merge
6. **LLM-friendly entry points** — PROJECT_STATE.md + NEXT_ACTION.md + ARCHITECTURE.md

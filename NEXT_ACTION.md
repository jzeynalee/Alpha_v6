# NEXT_ACTION.md

> **For LLMs**: After reading PROJECT_STATE.md, read this file. It tells you exactly what to do.

## Priority 1: Get ONE Hypothesis to Production

The immediate goal is NOT to build more infrastructure or invent more hypotheses.

It is to push **one hypothesis** through all 10 pipeline stages:

```
Stage 1  ✓ Economic Explanation (33/33 passed)
Stage 2  — In-Sample Discovery
Stage 3  — Walk-Forward Validation
Stage 4  — Bootstrap
Stage 5  — Outlier Robustness
Stage 6  — Transaction Costs
Stage 7  — Regime Stability
Stage 8  — Cross-Asset Validation
Stage 9  — Paper Trading
Stage 10 — Production Gate
```

**Recommended candidate**: `btc_mr_l2` (BTC Mean-Reversion, already at L2)
- Has economic rationale
- Survived transaction costs in v5
- Failed walk-forward — needs re-discovery with better regime filtering
- BTC has deepest data, lowest costs, best execution quality

## Next Steps

1. **Run In-Sample Discovery Experiment for `btc_mr_l2`**:
   ```python
   from src.core.experiment_manager import ExperimentManager
   manager = ExperimentManager()
   manager.run_single(hypothesis="btc_mr_l2", symbol="BTCUSDT", timeframe="15m")
   ```

2. **Check the Status of the Experiment**:
   ```bash
   python scripts/show_status.py          # Pipeline summary
   python scripts/show_evidence_scores.py # Multi-dimensional scores
   ```

3. **Populate the Knowledge Base with the Experiment Results**:
   ```python
   from src.core.knowledge_base import knowledge_base, Observation
   knowledge_base.add(Observation(
       observation_id="obs_009",
       statement="OI expansion + price breakout predicts continuation on 15m BTC",
       domain="open_interest",
       confidence=2,
       supporting_experiments=["exp_pos_001_btc_15m"],
       related_hypotheses=["pos_001"],
   ))
   ```

## Priority 2: Run Experiments on Program A (Open Interest + Funding)

The highest-expected-value research program. Use the experiment manager:

```python
from src.core.experiment_manager import ExperimentManager
manager = ExperimentManager()
manager.run_family("PositioningAlpha", symbol="BTCUSDT", timeframe="15m")
```

## Priority 3: Populate the Knowledge Base

Every time an experiment produces a finding, add it:

```python
from src.core.knowledge_base import knowledge_base, Observation
knowledge_base.add(Observation(
    observation_id="obs_009",
    statement="OI expansion + price breakout predicts continuation on 15m BTC",
    domain="open_interest",
    confidence=2,
    supporting_experiments=["exp_pos_001_btc_15m"],
    related_hypotheses=["pos_001"],
))
```

## How to Run Experiments

### 1. Single Hypothesis
```bash
python -m src.experiments.run_single --hypothesis btc_mr_l2 --symbol BTCUSDT --timeframe 15m
```

### 2. Entire Family
```bash
python -m src.experiments.run_family --family PositioningAlpha
```

### 3. All L0 Hypotheses
```bash
python -m src.experiments.run_batch --level L0
```

## How to Check Status

```bash
python scripts/show_status.py          # Pipeline summary
python scripts/show_evidence_scores.py # Multi-dimensional scores
python scripts/show_knowledge_base.py  # KB findings
```

## What NOT to Do

- ❌ Do NOT invent new hypotheses before running experiments on existing ones
- ❌ Do NOT build more infrastructure before validating the pipeline end-to-end
- ❌ Do NOT hard-code data paths — always use DatasetRegistry
- ❌ Do NOT create standalone MD/PDF reports — record findings in Knowledge Base
- ❌ Do NOT modify existing modules without running the full test suite

## Current Blockers

1. **Need OHLCV data**: Run `python scripts/backfill_binance_ohlcv.py` if data is stale
2. **Need funding rate data**: Run `python scripts/backfill_binance_OFD.py` for Program A

## File Map for LLMs

| File | Purpose | When to Read |
|------|---------|-------------|
| `PROJECT_STATE.md` | Current status | First |
| `NEXT_ACTION.md` | This file | Second |
| `ARCHITECTURE.md` | System design | Third |
| `docs/research/roadmap.md` | Full research roadmap | When planning |
| `docs/research/thesis_catalog.md` | All 200+ hypotheses | When selecting experiments |
| `docs/knowledge/observations.md` | What we know | Before designing tests |
| `src/core/dataset_registry.py` | Data access | When loading data |
| `src/core/experiment_manager.py` | Experiment runner | When running experiments |
| `src/core/evidence_ladder.py` | Hypothesis tracking | When evaluating results |


## Key Documents

| # | File | Purpose |
|---|------|---------|
| 1 | `PROJECT_STATE.md` | Current state — read first |
| 2 | `NEXT_ACTION.md` | Exact instructions — read second |
| 3 | `ARCHITECTURE.md` | System design — read third |
| 4 | `DISCOVERIES.md` | Validated findings + negative knowledge — read fourth |
| 5 | `docs/research/roadmap.md` | **Sequential research priorities** — read fifth |
| 6 | `docs/research/thesis_catalog.md` | All 200+ hypotheses |

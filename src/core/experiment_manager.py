# src/core/experiment_manager.py
"""
Experiment Manager — standardized execution of every hypothesis (Research Platform v2).

Replaces ad-hoc backtest scripts with a single, reproducible experiment runner.
Every experiment:
  1. Loads data via DatasetRegistry (no hard-coded paths)
  2. Generates signals from the hypothesis's strategy definition
  3. Runs the BacktestEngine with standard config
  4. Evaluates results against the 10-stage pipeline
  5. Updates the Evidence Ladder

Design
------
- ``ExperimentSpec`` defines what to run (hypothesis + dataset + pipeline stages).
- ``ExperimentManager`` orchestrates the full lifecycle.
- Results are stored in ``data/experiments/{experiment_id}/`` for reproducibility.
- Supports batch experiments across families, symbols, and timeframes.

Usage
-----
    from src.core.experiment_manager import ExperimentManager, ExperimentSpec

    manager = ExperimentManager()
    spec = ExperimentSpec(
        hypothesis_id="pos_001",
        symbol="BTCUSDT",
        timeframe="15m",
        stages=[2, 3, 4, 5, 6],  # In-sample through transaction costs
    )
    result = manager.run(spec)
    print(result.summary())
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.core.dataset_registry import registry as data_registry
from src.core.evidence_ladder import (
    EvidenceLadder,
    EvidenceLevel,
    HypothesisRecord,
    StageResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Experiment Spec
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExperimentSpec:
    """Defines one experiment to run."""
    hypothesis_id: str
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    exchange: str = ""           # Auto-detect if empty
    stages: List[int] = field(default_factory=lambda: [2, 3, 4, 5, 6])
    # Backtest config overrides
    initial_cash: float = 10_000.0
    fee_pct: float = 0.001
    slippage_pct: float = 0.0005
    # Pipeline context overrides
    min_walk_forward_windows: int = 12
    min_regime_count: int = 2
    min_cross_assets: int = 2
    # Signal source (callable or strategy name)
    signal_fn: Optional[Callable] = None  # Callable[[pd.DataFrame], BacktestSignal]
    strategy_name: str = ""               # Named strategy from registry
    # Metadata
    experiment_id: str = ""
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
#  Experiment Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExperimentResult:
    """Full result of one experiment run."""
    experiment_id: str
    hypothesis_id: str
    symbol: str
    timeframe: str
    status: str = "pending"  # pending | running | completed | failed
    started_at: str = ""
    completed_at: str = ""

    # Backtest metrics
    profit_factor: float = 0.0
    sharpe: float = 0.0
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    closed_trades: int = 0
    bars_processed: int = 0

    # Pipeline stage results
    stages_passed: int = 0
    stages_failed: int = 0
    stages_run: int = 0
    final_level: str = "L0"
    stage_details: List[Dict[str, Any]] = field(default_factory=list)

    # Errors
    error: str = ""

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    @property
    def passed(self) -> bool:
        return self.status == "completed" and self.stages_failed == 0

    def summary(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis_id": self.hypothesis_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "status": self.status,
            "profit_factor": round(self.profit_factor, 4),
            "sharpe": round(self.sharpe, 4),
            "win_rate": round(self.win_rate, 4),
            "total_return_pct": round(self.total_return_pct, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "closed_trades": self.closed_trades,
            "stages_passed": self.stages_passed,
            "stages_failed": self.stages_failed,
            "final_level": self.final_level,
            "error": self.error[:200] if self.error else "",
        }

    def render(self) -> str:
        s = self.summary()
        lines = [
            "═══ Experiment Result ═══",
            f"  Experiment:   {s['experiment_id']}",
            f"  Hypothesis:   {s['hypothesis_id']}",
            f"  Symbol:       {s['symbol']} @ {s['timeframe']}",
            f"  Status:       {s['status']}",
            f"  PF:           {s['profit_factor']:.3f}",
            f"  Sharpe:       {s['sharpe']:.3f}",
            f"  Win Rate:     {s['win_rate']:.1%}",
            f"  Return:       {s['total_return_pct']:.2f}%",
            f"  Max DD:       {s['max_drawdown_pct']:.2f}%",
            f"  Trades:       {s['closed_trades']}",
            f"  Stages:       {s['stages_passed']}P/{s['stages_failed']}F/{s['stages_run']}R",
            f"  Final Level:  {s['final_level']}",
        ]
        if s["error"]:
            lines.append(f"  Error:        {s['error']}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  Experiment Manager
# ═══════════════════════════════════════════════════════════════════════════════

class ExperimentManager:
    """
    Standardized experiment execution engine.

    Parameters
    ----------
    ladder : EvidenceLadder, optional
        The evidence ladder to read/write hypothesis state.
        Creates one from the default path if not provided.
    output_dir : str, optional
        Directory for experiment result files.
    """

    DEFAULT_OUTPUT_DIR = "data/experiments"

    def __init__(
        self,
        ladder: Optional[EvidenceLadder] = None,
        output_dir: Optional[str] = None,
    ) -> None:
        self.ladder = ladder or EvidenceLadder()
        if not self.ladder.is_loaded:
            self.ladder.load()
        self.output_dir = Path(output_dir or self.DEFAULT_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Main runner ────────────────────────────────────────────────────────────

    def run(self, spec: ExperimentSpec) -> ExperimentResult:
        """
        Execute one experiment end-to-end.

        Steps:
          1. Validate the hypothesis exists in the ladder
          2. Load OHLCV data via DatasetRegistry
          3. Create signal source (from spec or auto-generate)
          4. Run BacktestEngine
          5. Record metrics in hypothesis record
          6. Run pipeline stages
          7. Save experiment result to disk
        """
        # Generate experiment ID
        if not spec.experiment_id:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            spec.experiment_id = f"{spec.hypothesis_id}_{spec.symbol}_{spec.timeframe}_{ts}"

        result = ExperimentResult(
            experiment_id=spec.experiment_id,
            hypothesis_id=spec.hypothesis_id,
            symbol=spec.symbol,
            timeframe=spec.timeframe,
            status="running",
        )

        # ── Step 1: Validate hypothesis ────────────────────────────────────
        record = self.ladder.get(spec.hypothesis_id)
        if record is None:
            result.status = "failed"
            result.error = f"Hypothesis '{spec.hypothesis_id}' not found in ladder."
            self._save_result(result)
            return result

        if record.archived:
            result.status = "failed"
            result.error = f"Hypothesis '{spec.hypothesis_id}' is archived."
            self._save_result(result)
            return result

        # ── Step 2: Load data ──────────────────────────────────────────────
        exchange = spec.exchange or self._detect_exchange(spec.symbol, spec.timeframe)
        ohlcv = data_registry.get_ohlcv(exchange, spec.symbol, spec.timeframe)
        if ohlcv is None:
            result.status = "failed"
            result.error = (
                f"No OHLCV data found for {spec.symbol}/{spec.timeframe} "
                f"(exchange={exchange}). Available: "
                f"{data_registry.list_datasets()[:5]}"
            )
            self._save_result(result)
            return result

        logger.info(
            "Experiment %s: loaded %d bars for %s/%s",
            spec.experiment_id, len(ohlcv), spec.symbol, spec.timeframe,
        )

        # ── Step 3: Signal source ──────────────────────────────────────────
        signal_fn = spec.signal_fn
        if signal_fn is None:
            signal_fn = self._auto_signal_source(record)

        if signal_fn is None:
            result.status = "failed"
            result.error = (
                f"No signal source for hypothesis '{spec.hypothesis_id}' "
                f"(family={record.family}). Provide spec.signal_fn or "
                f"register a strategy."
            )
            self._save_result(result)
            return result

        # ── Step 4: Run backtest ───────────────────────────────────────────
        try:
            bt_metrics = self._run_backtest(
                ohlcv, signal_fn, spec, record
            )
            result.profit_factor = bt_metrics.get("profit_factor", 0.0)
            result.sharpe = bt_metrics.get("sharpe", 0.0)
            result.win_rate = bt_metrics.get("win_rate", 0.0)
            result.total_return_pct = bt_metrics.get("total_return_pct", 0.0)
            result.max_drawdown_pct = bt_metrics.get("max_drawdown_pct", 0.0)
            result.closed_trades = bt_metrics.get("closed_trades", 0)
            result.bars_processed = bt_metrics.get("bars_processed", 0)
        except Exception as exc:
            logger.exception("Backtest failed for %s", spec.experiment_id)
            result.status = "failed"
            result.error = f"Backtest failed: {exc}"
            self._save_result(result)
            return result

        # ── Step 5: Record metrics in hypothesis ───────────────────────────
        self._record_metrics(record, bt_metrics)

        # ── Step 6: Run pipeline stages ────────────────────────────────────
        from src.core.research_pipeline import ResearchPipeline, PipelineContext

        ctx = PipelineContext(
            min_walk_forward_windows=spec.min_walk_forward_windows,
            min_regime_count=spec.min_regime_count,
            min_cross_assets=spec.min_cross_assets,
            auto_promote=True,
            stop_on_failure=False,  # Run all requested stages
        )
        pipeline = ResearchPipeline(self.ladder, context=ctx)
        pipeline_result = pipeline.run_hypothesis(
            spec.hypothesis_id,
            requested_stages=spec.stages,
        )

        result.stages_passed = pipeline_result.get("stages_passed", 0)
        result.stages_failed = pipeline_result.get("stages_failed", 0)
        result.stages_run = pipeline_result.get("stages_run", 0)
        result.final_level = pipeline_result.get("final_level", "L0")
        result.stage_details = pipeline_result.get("results", [])

        # ── Step 7: Done ───────────────────────────────────────────────────
        result.status = "completed"
        result.completed_at = datetime.now(timezone.utc).isoformat()
        self._save_result(result)

        logger.info(
            "Experiment %s COMPLETED: PF=%.2f, stages=%dP/%dF, level=%s",
            spec.experiment_id, result.profit_factor,
            result.stages_passed, result.stages_failed, result.final_level,
        )
        return result

    # ── Batch runner ───────────────────────────────────────────────────────────

    def run_batch(
        self,
        specs: List[ExperimentSpec],
    ) -> List[ExperimentResult]:
        """Run multiple experiments sequentially."""
        results = []
        for i, spec in enumerate(specs):
            logger.info(
                "Batch experiment %d/%d: %s",
                i + 1, len(specs), spec.hypothesis_id,
            )
            result = self.run(spec)
            results.append(result)
        return results

    def run_family(
        self,
        family: str,
        symbol: str = "BTCUSDT",
        timeframe: str = "15m",
        stages: Optional[List[int]] = None,
    ) -> List[ExperimentResult]:
        """Run all hypotheses in a given alpha family."""
        records = self.ladder.list_by_family(family)
        if not records:
            logger.warning("No hypotheses found for family: %s", family)
            return []

        specs = [
            ExperimentSpec(
                hypothesis_id=r.hypothesis_id,
                symbol=symbol,
                timeframe=timeframe,
                stages=stages or [2, 6],
            )
            for r in records if not r.archived
        ]
        return self.run_batch(specs)

    def run_all_l0(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "15m",
        stages: Optional[List[int]] = None,
    ) -> List[ExperimentResult]:
        """Run all L0 hypotheses."""
        records = self.ladder.list_by_level(EvidenceLevel.L0)
        specs = [
            ExperimentSpec(
                hypothesis_id=r.hypothesis_id,
                symbol=symbol,
                timeframe=timeframe,
                stages=stages or [2, 6],
            )
            for r in records if not r.archived
        ]
        return self.run_batch(specs)

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_exchange(symbol: str, timeframe: str) -> str:
        """Detect which exchange has data for this symbol/timeframe."""
        # Try binance first (current primary source)
        for ex in ("binance", "nobitex", "lbank"):
            if data_registry.resolve(symbol, timeframe, exchange=ex):
                return ex
        return ""  # Let registry fallback handle it

    @staticmethod
    def _auto_signal_source(record: HypothesisRecord) -> Optional[Callable]:
        """Generate a signal function based on hypothesis family."""
        family = record.family.lower()

        if "meanreversion" in family:
            def mr_signal(window: pd.DataFrame):
                from src.backtest.signal_source import BacktestSignal
                if len(window) < 20:
                    return BacktestSignal.flat()
                close = window["close"]
                sma = close.rolling(20).mean()
                std = close.rolling(20).std()
                if pd.isna(sma.iloc[-1]) or pd.isna(std.iloc[-1]) or std.iloc[-1] == 0:
                    return BacktestSignal.flat()
                z = (close.iloc[-1] - sma.iloc[-1]) / std.iloc[-1]
                if z < -1.5:
                    return BacktestSignal(direction=1, proba_alpha=0.70)
                elif z > 1.5:
                    return BacktestSignal(direction=-1, proba_alpha=0.70)
                return BacktestSignal.flat()
            return mr_signal

        elif "momentum" in family:
            def mom_signal(window: pd.DataFrame):
                from src.backtest.signal_source import BacktestSignal
                if len(window) < 20:
                    return BacktestSignal.flat()
                close = window["close"]
                sma = close.rolling(20).mean()
                if pd.isna(sma.iloc[-1]):
                    return BacktestSignal.flat()
                if close.iloc[-1] > sma.iloc[-1]:
                    return BacktestSignal(direction=1, proba_alpha=0.65)
                return BacktestSignal.flat()
            return mom_signal

        elif "expansion" in family or "volatility" in family:
            def vol_signal(window: pd.DataFrame):
                from src.backtest.signal_source import BacktestSignal
                if len(window) < 20:
                    return BacktestSignal.flat()
                close = window["close"]
                atr = (window["high"] - window["low"]).rolling(14).mean()
                atr_20 = atr.rolling(20).mean()
                if pd.isna(atr.iloc[-1]) or pd.isna(atr_20.iloc[-1]) or atr_20.iloc[-1] == 0:
                    return BacktestSignal.flat()
                # Compression: ATR < 0.7 * 20-period average → expect expansion
                if atr.iloc[-1] < 0.7 * atr_20.iloc[-1]:
                    # Direction from momentum
                    mom = close.iloc[-1] - close.iloc[-5]
                    direction = 1 if mom > 0 else -1
                    return BacktestSignal(direction=direction, proba_alpha=0.60)
                return BacktestSignal.flat()
            return vol_signal

        return None

    @staticmethod
    def _run_backtest(
        ohlcv: pd.DataFrame,
        signal_fn: Callable,
        spec: ExperimentSpec,
        record: HypothesisRecord,
    ) -> Dict[str, Any]:
        """Run the backtest engine and return metrics."""
        from src.backtest.engine import BacktestEngine, BacktestConfig

        config = BacktestConfig(
            initial_cash=spec.initial_cash,
            fee_pct=spec.fee_pct,
            slippage_pct=spec.slippage_pct,
            warmup_bars=50,
            allow_short=True,
        )
        engine = BacktestEngine(signal_source=signal_fn, config=config)
        bt_result = engine.run(ohlcv)

        return {
            "profit_factor": bt_result.profit_factor,
            "sharpe": bt_result.sharpe,
            "win_rate": bt_result.win_rate,
            "total_return_pct": bt_result.total_return_pct,
            "max_drawdown_pct": bt_result.equity_max_drawdown_pct,
            "closed_trades": bt_result.closed_trades,
            "bars_processed": bt_result.bars_processed,
            "exposure_pct": bt_result.exposure_pct,
        }

    @staticmethod
    def _record_metrics(
        record: HypothesisRecord,
        metrics: Dict[str, Any],
    ) -> None:
        """Record backtest metrics into the hypothesis record."""
        pf = metrics.get("profit_factor", 0.0)
        sharpe = metrics.get("sharpe", 0.0)

        record.metrics["in_sample"] = {
            "profit_factor": pf,
            "sharpe": sharpe,
            "win_rate": metrics.get("win_rate", 0.0),
            "total_return_pct": metrics.get("total_return_pct", 0.0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
            "closed_trades": metrics.get("closed_trades", 0),
            "source": "experiment_manager",
        }

        record.metrics["transaction_costs"] = {
            "pf_gross": pf,
            "pf_net": pf,
            "annual_turnover": 0.0,
        }

        record.updated_at = datetime.now(timezone.utc).isoformat()

    def _save_result(self, result: ExperimentResult) -> None:
        """Save experiment result to disk."""
        exp_dir = self.output_dir / result.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "experiment_id": result.experiment_id,
            "hypothesis_id": result.hypothesis_id,
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "status": result.status,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "summary": result.summary(),
            "stage_details": result.stage_details,
            "error": result.error,
        }

        with open(exp_dir / "result.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        # Also save to summary directory
        summary_path = self.output_dir / "summaries" / f"{result.experiment_id}.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(result.summary(), f, ensure_ascii=False, indent=2)

        # ── Auto-generate research paper ───────────────────────────────────
        self._generate_research_paper(result)

    def _generate_research_paper(self, result: ExperimentResult) -> None:
        """
        Auto-generate a research paper in docs/research/results/.

        Each paper follows a standard template: Hypothesis, Data, Method,
        Results, Statistics, Limitations, Decision, Next Step.
        """
        papers_dir = Path("docs/research/results")
        papers_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        hypothesis_id = result.hypothesis_id
        paper_path = papers_dir / f"{date_str}_{hypothesis_id}_{result.symbol}_{result.timeframe}.md"

        summary = result.summary()
        status_icon = "✓" if result.passed else "✗"

        content = f"""# Experiment: {result.hypothesis_id}

**Date**: {date_str}
**Status**: {status_icon} {result.status}
**Experiment ID**: {result.experiment_id}

---

## Hypothesis

**Family**: (from evidence ladder)
**Hypothesis ID**: {result.hypothesis_id}

## Data

- **Symbol**: {result.symbol}
- **Timeframe**: {result.timeframe}
- **Bars processed**: {summary.get('bars_processed', 'N/A')}

## Method

- Backtest engine with event-driven simulation
- Fee: {getattr(self, '_last_spec', None) or '0.1%'}
- Stages run: {result.stages_run}

## Results

| Metric | Value |
|--------|-------|
| Profit Factor | {summary['profit_factor']:.3f} |
| Sharpe | {summary['sharpe']:.3f} |
| Win Rate | {summary['win_rate']:.1%} |
| Total Return | {summary['total_return_pct']:.2f}% |
| Max Drawdown | {summary['max_drawdown_pct']:.2f}% |
| Closed Trades | {summary['closed_trades']} |

## Pipeline Stages

- **Stages passed**: {result.stages_passed}
- **Stages failed**: {result.stages_failed}
- **Final evidence level**: {result.final_level}

### Stage Details

"""
        for sd in result.stage_details:
            icon = "✓" if sd.get("passed", False) else "✗"
            content += f"- [{icon}] Stage {sd.get('stage', '?')}: {sd.get('name', 'Unknown')}\n"
            if sd.get("notes"):
                content += f"  - {sd['notes'][:200]}\n"

        content += f"""
## Limitations

- Single-symbol backtest ({result.symbol} only)
- Does not account for regime changes
- Transaction costs may be underestimated
- No live trading verification (Stage 9)

## Decision

"""
        if result.passed:
            content += f"- **PASSED**: Hypothesis advances to {result.final_level}\n"
            content += f"- Next: run remaining pipeline stages (up to Stage 8)\n"
        elif result.stages_failed > 0:
            content += f"- **FAILED** at {result.stages_failed} stage(s)\n"
            content += f"- Hypothesis returned to research backlog (L0)\n"
            content += f"- Consider: refine economic rationale, adjust parameters, or test different timeframe\n"
        else:
            content += f"- **ERROR**: {summary.get('error', 'Unknown error')}\n"
            content += f"- Fix the error and re-run\n"

        content += f"""
## Next Step

"""
        if result.passed:
            content += f"- Run next pipeline stages for {result.hypothesis_id}\n"
        else:
            content += f"- Review failure reason and re-hypothesize\n"

        content += f"""
---

*Auto-generated by ExperimentManager at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*
"""

        with open(paper_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Research paper generated: %s", paper_path)

    def list_experiments(self) -> List[Dict[str, Any]]:
        """List all completed experiments."""
        summaries_dir = self.output_dir / "summaries"
        if not summaries_dir.exists():
            return []
        experiments = []
        for f in sorted(summaries_dir.glob("*.json"), reverse=True):
            try:
                with open(f) as fh:
                    experiments.append(json.load(fh))
            except Exception:
                pass
        return experiments


__all__ = [
    "ExperimentManager",
    "ExperimentSpec",
    "ExperimentResult",
]

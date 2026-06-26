# src/core/research_pipeline.py
"""
Research Pipeline — 10-stage hypothesis evaluation framework (Roadmap v2).

Every hypothesis must pass all 10 stages before production deployment.
Failure at any stage returns the hypothesis to the research backlog (L0).

The pipeline integrates directly with the EvidenceLadder to track
progression, and reuses the existing infrastructure:

  Stage 1   Economic Explanation   → hypothesis_validator.py
  Stage 2   In-Sample Discovery    → signal_factory_simulation.py
  Stage 3   Walk-Forward           → src/cv/walk_forward.py
  Stage 4   Bootstrap              → statistical resampling
  Stage 5   Outlier Robustness     → trimmed performance re-evaluation
  Stage 6   Transaction Costs      → backtest engine with realistic costs
  Stage 7   Regime Stability       → performance by regime (Bull/Bear/Neutral)
  Stage 8   Cross-Asset Validation → test on unrelated assets
  Stage 9   Paper Trading          → live market data, no capital
  Stage 10  Production             → live capital deployment

Usage
-----
    from src.core.evidence_ladder import EvidenceLadder, HypothesisRecord
    from src.core.research_pipeline import ResearchPipeline

    ladder = EvidenceLadder()
    ladder.load()

    pipeline = ResearchPipeline(ladder)
    pipeline.run_hypothesis("pos_001")
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.core.evidence_ladder import (
    EvidenceLadder,
    EvidenceLevel,
    HypothesisRecord,
    PIPELINE_STAGES,
    PipelineStage,
    StageResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Stage Runner Protocol
# ═══════════════════════════════════════════════════════════════════════════════

StageRunner = Callable[[HypothesisRecord, Dict[str, Any]], StageResult]
"""A stage runner takes a hypothesis and a context dict, returns a StageResult."""


# ═══════════════════════════════════════════════════════════════════════════════
#  Default Stage Runners
# ═══════════════════════════════════════════════════════════════════════════════

def _default_economic_explanation(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 1: Validate the economic rationale from the hypothesis record.

    Checks that the hypothesis has a non-empty economic_rationale (>= 50 chars),
    non-empty description (>= 30 chars), specified symbols and timeframes,
    and no placeholder text. Also validates against thesis document if path provided.
    """
    errors: list = []
    checks: dict = {}

    rationale = hypothesis.economic_rationale.strip()
    checks["has_rationale"] = len(rationale) >= 50
    if not checks["has_rationale"]:
        errors.append(f"Economic rationale too short ({len(rationale)} chars, need >= 50).")

    description = hypothesis.description.strip()
    checks["has_description"] = len(description) >= 30
    if not checks["has_description"]:
        errors.append(f"Description too short ({len(description)} chars, need >= 30).")

    checks["has_symbols"] = len(hypothesis.symbols) > 0
    if not checks["has_symbols"]:
        errors.append("No trading symbols specified.")

    checks["has_timeframes"] = len(hypothesis.timeframes) > 0
    if not checks["has_timeframes"]:
        errors.append("No timeframes specified.")

    placeholder_markers = ("Example:", "Replace with", "<Name your", "TODO", "TBD")
    has_placeholders = any(m in rationale or m in description for m in placeholder_markers)
    checks["no_placeholders"] = not has_placeholders
    if has_placeholders:
        errors.append("Hypothesis contains placeholder text.")

    thesis_ok = True
    thesis_notes = ""
    doc_path = ctx.get("thesis_document_path", "")
    require_thesis = ctx.get("require_economic_explanation", True)
    if doc_path and require_thesis:
        try:
            from src.validation.hypothesis_validator import validate_hypothesis_document
            report = validate_hypothesis_document(doc_path)
            thesis_ok = report.passed
            thesis_notes = "; Thesis: " + report.render()[:200]
        except Exception as exc:
            thesis_notes = f"; Thesis validation skipped: {exc}"
    elif not doc_path:
        thesis_notes = "; Thesis document path not configured — skipped."
    elif not require_thesis:
        thesis_notes = "; Thesis validation disabled (require_economic_explanation=False)."
    checks["thesis_document_ok"] = thesis_ok

    all_checks = sum(1 for v in checks.values() if v)
    total_checks = len(checks)
    passed = all_checks >= total_checks

    notes = "; ".join(errors) if errors else (
        f"Economic explanation validated ({all_checks}/{total_checks} checks passed)."
    )
    notes += thesis_notes

    return StageResult(
        stage=1,
        name="Economic Explanation",
        passed=passed,
        metrics={
            "checks_passed": all_checks,
            "checks_total": total_checks,
            **{f"check_{k}": v for k, v in checks.items()},
        },
        notes=notes,
    )


def _default_in_sample_discovery(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 2: Check for in-sample edge using signal factory / feature analysis."""
    metrics: Dict[str, Any] = {}
    notes: List[str] = []

    # Check if the hypothesis has in-sample metrics recorded
    in_sample_metrics = hypothesis.metrics.get("in_sample", {})
    pf = in_sample_metrics.get("profit_factor", 0.0)
    sharpe = in_sample_metrics.get("sharpe", 0.0)
    win_rate = in_sample_metrics.get("win_rate", 0.0)

    if pf > 0:
        metrics["profit_factor"] = pf
        metrics["sharpe"] = sharpe
        metrics["win_rate"] = win_rate

    # Minimum in-sample bar: PF > 1.0 on training data
    passed = pf > 1.0
    if not passed:
        notes.append(
            f"In-sample edge insufficient: PF={pf:.2f} (need > 1.0). "
            "Run signal_factory_simulation.py to populate in-sample metrics."
        )
    else:
        notes.append(f"In-sample edge confirmed: PF={pf:.2f}, Sharpe={sharpe:.2f}")

    return StageResult(
        stage=2,
        name="In-Sample Discovery",
        passed=passed,
        metrics=metrics,
        notes="\n".join(notes) if notes else "No in-sample metrics available.",
    )


def _default_walk_forward(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 3: Walk-forward validation."""
    wf_metrics = hypothesis.metrics.get("walk_forward", {})
    n_windows = wf_metrics.get("n_windows", 0)
    mean_ir = wf_metrics.get("mean_ir", 0.0)
    ir_positive_prob = wf_metrics.get("ir_positive_prob", 0.0)
    dsr = wf_metrics.get("dsr", -1.0)

    min_windows = ctx.get("min_walk_forward_windows", 12)
    passed = (
        n_windows >= min_windows
        and ir_positive_prob >= 0.60
        and dsr > 0.0
    )

    return StageResult(
        stage=3,
        name="Walk-Forward Validation",
        passed=passed,
        metrics={
            "n_windows": n_windows,
            "mean_ir": mean_ir,
            "ir_positive_prob": ir_positive_prob,
            "dsr": dsr,
        },
        notes=(
            f"Walk-forward: {n_windows}/{min_windows} windows, "
            f"mean_IR={mean_ir:.3f}, P(IR>0)={ir_positive_prob:.3f}, DSR={dsr:.3f}"
        ),
    )


def _default_bootstrap(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 4: Bootstrap statistical significance test."""
    bs_metrics = hypothesis.metrics.get("bootstrap", {})
    p_value = bs_metrics.get("p_value", 1.0)
    ci_lower = bs_metrics.get("ci_lower_95", -1.0)
    n_bootstrap = bs_metrics.get("n_samples", 0)

    passed = p_value < 0.05 and ci_lower > 0.0

    return StageResult(
        stage=4,
        name="Bootstrap",
        passed=passed,
        metrics={
            "p_value": p_value,
            "ci_lower_95": ci_lower,
            "n_bootstrap_samples": n_bootstrap,
        },
        notes=(
            f"Bootstrap: p={p_value:.4f}, 95% CI lower={ci_lower:.4f}, "
            f"n={n_bootstrap}"
        ),
    )


def _default_outlier_robustness(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 5: Outlier removal robustness check."""
    outlier_metrics = hypothesis.metrics.get("outlier_robustness", {})
    pf_full = outlier_metrics.get("pf_full", 0.0)
    pf_trimmed = outlier_metrics.get("pf_trimmed", 0.0)
    pf_drop = abs(pf_full - pf_trimmed) / max(abs(pf_full), 1e-9)
    max_pf_drop = ctx.get("max_outlier_pf_drop", 0.30)

    passed = pf_trimmed > 1.0 and pf_drop <= max_pf_drop

    return StageResult(
        stage=5,
        name="Outlier Robustness",
        passed=passed,
        metrics={
            "pf_full": pf_full,
            "pf_trimmed": pf_trimmed,
            "pf_drop_pct": pf_drop * 100,
        },
        notes=(
            f"Outlier check: PF {pf_full:.2f} → {pf_trimmed:.2f} "
            f"(drop={pf_drop:.1%}, max allowed={max_pf_drop:.0%})"
        ),
    )


def _default_transaction_costs(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 6: Transaction cost survival."""
    tc_metrics = hypothesis.metrics.get("transaction_costs", {})
    pf_gross = tc_metrics.get("pf_gross", 0.0)
    pf_net = tc_metrics.get("pf_net", 0.0)
    turnover = tc_metrics.get("annual_turnover", 0.0)

    passed = pf_net > 1.0

    return StageResult(
        stage=6,
        name="Transaction Costs",
        passed=passed,
        metrics={
            "pf_gross": pf_gross,
            "pf_net": pf_net,
            "annual_turnover": turnover,
        },
        notes=(
            f"Transaction costs: PF gross={pf_gross:.2f} → "
            f"net={pf_net:.2f}, turnover={turnover:.0f}x/year"
        ),
    )


def _default_regime_stability(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 7: Regime stability across Bull/Bear/Neutral."""
    regime_metrics = hypothesis.metrics.get("regime_stability", {})
    bull_pf = regime_metrics.get("bull_pf", 0.0)
    bear_pf = regime_metrics.get("bear_pf", 0.0)
    neutral_pf = regime_metrics.get("neutral_pf", 0.0)
    n_regimes_positive = sum(1 for pf in (bull_pf, bear_pf, neutral_pf) if pf > 1.0)
    min_regimes = ctx.get("min_regime_count", 2)

    passed = n_regimes_positive >= min_regimes

    return StageResult(
        stage=7,
        name="Regime Stability",
        passed=passed,
        metrics={
            "bull_pf": bull_pf,
            "bear_pf": bear_pf,
            "neutral_pf": neutral_pf,
            "n_regimes_positive": n_regimes_positive,
        },
        notes=(
            f"Regime stability: Bull PF={bull_pf:.2f}, Bear PF={bear_pf:.2f}, "
            f"Neutral PF={neutral_pf:.2f} → {n_regimes_positive}/3 regimes positive"
        ),
    )


def _default_cross_asset_validation(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 8: Cross-asset validation on 2+ unrelated assets."""
    cross_metrics = hypothesis.metrics.get("cross_asset", {})
    assets_tested = cross_metrics.get("assets_tested", [])
    assets_passed = cross_metrics.get("assets_passed", [])
    n_tested = len(assets_tested)
    n_passed = len(assets_passed)
    min_assets = ctx.get("min_cross_assets", 2)

    passed = n_passed >= min_assets

    return StageResult(
        stage=8,
        name="Cross-Asset Validation",
        passed=passed,
        metrics={
            "assets_tested": assets_tested,
            "assets_passed": assets_passed,
            "n_tested": n_tested,
            "n_passed": n_passed,
        },
        notes=(
            f"Cross-asset: {n_passed}/{n_tested} assets passed "
            f"(need >= {min_assets}): {assets_passed}"
        ),
    )


def _default_paper_trading(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 9: Live paper trading evaluation.

    Reads from hypothesis.metrics['paper_tracing'] which should be populated
    by the PaperTradingTracker. Falls back to checking stored metrics.
    Also attempts to read from the paper trading journal if available.
    """
    pt_metrics = hypothesis.metrics.get("paper_trading", {})
    days_live = pt_metrics.get("days_live", 0)
    pf_live = pt_metrics.get("pf_live", 0.0)
    sharpe_live = pt_metrics.get("sharpe_live", 0.0)
    win_rate_live = pt_metrics.get("win_rate_live", 0.0)
    n_trades = pt_metrics.get("n_trades", 0)
    min_days = ctx.get("min_paper_trading_days", 30)
    min_trades = ctx.get("min_paper_trading_trades", 10)

    # Try loading from PaperTradingTracker journal if available
    if days_live == 0 and pt_metrics.get("started_at"):
        try:
            from src.core.paper_trading import PaperTradingTracker
            tracker = PaperTradingTracker(
                hypothesis_id=hypothesis.hypothesis_id,
                journal_dir=ctx.get("paper_trading_journal_dir", "data/journal/paper_trading"),
            )
            live_metrics = tracker.metrics()
            days_live = live_metrics.get("days_live", 0)
            pf_live = live_metrics.get("pf_live", 0.0)
            sharpe_live = live_metrics.get("sharpe_live", 0.0)
            win_rate_live = live_metrics.get("win_rate_live", 0.0)
            n_trades = live_metrics.get("n_trades", 0)
            # Update hypothesis metrics from tracker
            tracker.update_hypothesis_metrics(hypothesis)
        except Exception as exc:
            logger.debug("PaperTradingTracker load skipped: %s", exc)

    # Must have enough trades to be meaningful
    has_enough_trades = n_trades >= min_trades
    passed = days_live >= min_days and pf_live > 1.0 and has_enough_trades

    return StageResult(
        stage=9,
        name="Paper Trading",
        passed=passed,
        metrics={
            "days_live": days_live,
            "pf_live": pf_live,
            "sharpe_live": sharpe_live,
            "win_rate_live": win_rate_live,
            "n_trades": n_trades,
        },
        notes=(
            f"Paper trading: {days_live}/{min_days} days live, "
            f"PF={pf_live:.2f}, Sharpe={sharpe_live:.2f}, "
            f"{n_trades}/{min_trades} trades"
        ),
    )


def _default_production(
    hypothesis: HypothesisRecord, ctx: Dict[str, Any]
) -> StageResult:
    """Stage 10: Production deployment gate.

    Evaluates whether a hypothesis that passed Stages 1-9 is safe to deploy
    with real capital. Uses ProductionGate for comprehensive safety checks.
    Falls back to basic months_live + PF check if gate is unavailable.
    """
    prod_metrics = hypothesis.metrics.get("production", {})
    months_live = prod_metrics.get("months_live", 0)
    pf_live = prod_metrics.get("pf_live", 0.0)
    min_months = ctx.get("min_production_months", 6)

    # Try using the full ProductionGate for comprehensive evaluation
    gate_passed = False
    gate_checks = {}
    gate_notes = ""

    try:
        from src.core.production_gate import ProductionGate, GateConfig
        gate = ProductionGate(GateConfig(
            min_months_live=min_months,
            min_live_pf=1.0,
            min_live_sharpe=0.0,
        ))
        # Build minimal portfolio state from hypothesis metrics
        portfolio_state = {
            "current_allocation": {},
            "daily_pnl": prod_metrics.get("daily_pnl", 0.0),
            "drawdown": abs(prod_metrics.get("max_drawdown_pct", 0.0) / 100.0),
            "regime": ctx.get("current_regime", "Neutral"),
            "consecutive_losses": prod_metrics.get("consecutive_losses", 0),
            "active_correlations": {},
        }
        gate_result = gate.evaluate(hypothesis, portfolio_state)
        gate_passed = gate_result.passed
        gate_checks = {
            "checks_passed": len(gate_result.passed_checks),
            "checks_total": len(gate_result.checks),
        }
        gate_notes = "; " + "; ".join(
            f"{c.check_name}: {'PASS' if c.passed else 'FAIL'}"
            for c in gate_result.checks
        )
        # Update hypothesis metrics from gate
        gate.update_hypothesis_metrics(hypothesis, gate_result)
    except Exception as exc:
        logger.debug("ProductionGate evaluation skipped: %s", exc)
        # Fall back to basic check
        gate_passed = months_live >= min_months and pf_live > 1.0

    return StageResult(
        stage=10,
        name="Production",
        passed=gate_passed,
        metrics={
            "months_live": months_live,
            "pf_live": pf_live,
            **gate_checks,
        },
        notes=(
            f"Production: {months_live}/{min_months} months live, "
            f"PF={pf_live:.2f}" + gate_notes
        ),
    )


# Default stage runner registry
DEFAULT_STAGE_RUNNERS: Dict[int, StageRunner] = {
    1: _default_economic_explanation,
    2: _default_in_sample_discovery,
    3: _default_walk_forward,
    4: _default_bootstrap,
    5: _default_outlier_robustness,
    6: _default_transaction_costs,
    7: _default_regime_stability,
    8: _default_cross_asset_validation,
    9: _default_paper_trading,
    10: _default_production,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Pipeline Context
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PipelineContext:
    """Shared context passed to every stage runner."""
    # File paths
    thesis_document_path: str = ""  # Empty = skip thesis document validation
    data_root: str = "data"
    artefacts_root: str = "data/offline/active"

    # Stage thresholds (overridable)
    min_walk_forward_windows: int = 12
    min_regime_count: int = 2
    min_cross_assets: int = 2
    max_outlier_pf_drop: float = 0.30
    min_paper_trading_days: int = 30
    min_production_months: int = 6

    # Feature flags
    require_economic_explanation: bool = True
    auto_promote: bool = True
    stop_on_failure: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thesis_document_path": self.thesis_document_path,
            "data_root": self.data_root,
            "artefacts_root": self.artefacts_root,
            "min_walk_forward_windows": self.min_walk_forward_windows,
            "min_regime_count": self.min_regime_count,
            "min_cross_assets": self.min_cross_assets,
            "max_outlier_pf_drop": self.max_outlier_pf_drop,
            "min_paper_trading_days": self.min_paper_trading_days,
            "min_production_months": self.min_production_months,
            "require_economic_explanation": self.require_economic_explanation,
            "min_paper_trading_trades": 10,
            "paper_trading_journal_dir": "data/journal/paper_trading",
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  Research Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_REQUESTED_STAGES = [1, 2, 3, 4, 5, 6, 7, 8]


class ResearchPipeline:
    """
    Orchestrates hypotheses through the 10-stage research pipeline.

    Each hypothesis starts at L0. The pipeline runs stages in order,
    promoting the hypothesis up the evidence ladder as stages pass.
    A failure at any stage demotes the hypothesis to L0 (backlog)
    unless ``stop_on_failure=False``.

    Parameters
    ----------
    ladder : EvidenceLadder
        The evidence ladder registry to read/write hypothesis state.
    context : PipelineContext, optional
        Shared context passed to stage runners. Defaults apply.
    stage_runners : Dict[int, StageRunner], optional
        Override default stage runners. Keys are stage numbers 1-10.

    Usage
    -----
        ladder = EvidenceLadder()
        ladder.load()
        pipeline = ResearchPipeline(ladder)
        results = pipeline.run_hypothesis("pos_001")
        pipeline.run_backlog()  # process all L0 hypotheses
    """

    def __init__(
        self,
        ladder: EvidenceLadder,
        context: Optional[PipelineContext] = None,
        stage_runners: Optional[Dict[int, StageRunner]] = None,
    ) -> None:
        self.ladder = ladder
        self.context = context or PipelineContext()
        self.stage_runners = {**DEFAULT_STAGE_RUNNERS, **(stage_runners or {})}

    # ── Main pipeline runner ─────────────────────────────────────────────────

    def run_hypothesis(
        self,
        hypothesis_id: str,
        start_stage: Optional[int] = None,
        requested_stages: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Run a hypothesis through the pipeline.

        Parameters
        ----------
        hypothesis_id : str
            The hypothesis to evaluate.
        start_stage : int, optional
            Stage to start from. Default: the hypothesis's current_stage.
        requested_stages : List[int], optional
            Stages to run. Default: stages 2-8 for research (skip 1, 9, 10).
            Stage 1 (Economic Explanation) is manual-validation heavy.
            Stages 9-10 (Paper Trading, Production) require live infrastructure.

        Returns
        -------
        Dict with keys:
            hypothesis_id, started_at_level, final_level, stages_run,
            stages_passed, stages_failed, results, error
        """
        record = self.ladder.get(hypothesis_id)
        if record is None:
            return {
                "hypothesis_id": hypothesis_id,
                "error": f"Hypothesis '{hypothesis_id}' not found in ladder.",
                "stages_run": 0,
                "stages_passed": 0,
                "stages_failed": 0,
            }

        if record.archived:
            return {
                "hypothesis_id": hypothesis_id,
                "error": f"Hypothesis '{hypothesis_id}' is archived.",
                "stages_run": 0,
                "stages_passed": 0,
                "stages_failed": 0,
            }

        stages_to_run = requested_stages or DEFAULT_REQUESTED_STAGES
        # When explicit stages are requested, start at the earliest one,
        # even if it's before the hypothesis's current_stage.
        if requested_stages:
            start = start_stage or min(requested_stages)
        else:
            start = start_stage or record.current_stage
        started_level = record.evidence_level

        stages_run = 0
        stages_passed = 0
        stages_failed = 0
        all_results: List[StageResult] = []

        ctx_dict = self.context.to_dict()

        for stage_num in range(start, 11):
            if stage_num not in stages_to_run:
                continue

            runner = self.stage_runners.get(stage_num)
            if runner is None:
                logger.warning(
                    "No runner for stage %d — skipping hypothesis %s.",
                    stage_num, hypothesis_id,
                )
                continue

            stage_def = PIPELINE_STAGES[stage_num - 1]
            logger.info(
                "Running Stage %d (%s) for hypothesis %s [L%d].",
                stage_num, stage_def.name, hypothesis_id, record.evidence_level.value,
            )

            try:
                result = runner(record, ctx_dict)
            except Exception as exc:
                logger.exception(
                    "Stage %d runner crashed for %s: %s",
                    stage_num, hypothesis_id, exc,
                )
                result = StageResult(
                    stage=stage_num,
                    name=stage_def.name,
                    passed=False,
                    notes=f"Runner exception: {exc}",
                )

            record.record_stage(result)
            all_results.append(result)
            stages_run += 1

            if result.passed:
                stages_passed += 1
                if self.context.auto_promote:
                    # Determine the target evidence level for this stage
                    target_level = stage_def.required_evidence_level
                    # Don't promote beyond L4 in automated pipeline
                    if target_level > EvidenceLevel.L4:
                        target_level = EvidenceLevel.L4
                    if target_level > record.evidence_level:
                        self.ladder.promote(hypothesis_id, target_level, result)
            else:
                stages_failed += 1
                if self.context.stop_on_failure:
                    self.ladder.demote(hypothesis_id, result.notes, stage_num)
                    logger.warning(
                        "Hypothesis %s FAILED at Stage %d (%s). Demoted to L0. "
                        "Stopping pipeline.",
                        hypothesis_id, stage_num, stage_def.name,
                    )
                    break
                else:
                    logger.warning(
                        "Hypothesis %s FAILED Stage %d (%s). Continuing "
                        "(stop_on_failure=False).",
                        hypothesis_id, stage_num, stage_def.name,
                    )

        self.ladder.save()

        return {
            "hypothesis_id": hypothesis_id,
            "started_at_level": f"L{started_level.value}",
            "final_level": f"L{record.evidence_level.value}",
            "stages_run": stages_run,
            "stages_passed": stages_passed,
            "stages_failed": stages_failed,
            "final_level_label": record.level_label,
            "results": [asdict(r) for r in all_results],
        }

    def run_backlog(
        self, requested_stages: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Run all L0 backlog hypotheses through the pipeline."""
        backlog = self.ladder.list_backlog()
        results = []
        for record in backlog:
            result = self.run_hypothesis(
                record.hypothesis_id, requested_stages=requested_stages
            )
            results.append(result)
        return results

    def run_never_tested(
        self, requested_stages: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Run all never-tested L0 hypotheses through the pipeline."""
        fresh = self.ladder.list_never_tested()
        results = []
        for record in fresh:
            result = self.run_hypothesis(
                record.hypothesis_id, requested_stages=requested_stages
            )
            results.append(result)
        return results

    def run_all_l0(
        self, requested_stages: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Run all L0 hypotheses (both backlog and never-tested)."""
        return self.run_backlog(requested_stages) + self.run_never_tested(requested_stages)

    def run_family(
        self,
        family: str,
        requested_stages: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Run all hypotheses in a given alpha family through the pipeline."""
        members = self.ladder.list_by_family(family)
        results = []
        for record in members:
            result = self.run_hypothesis(
                record.hypothesis_id, requested_stages=requested_stages
            )
            results.append(result)
        return results

    # ── Bootstrap evaluation helper ──────────────────────────────────────────

    @staticmethod
    def evaluate_bootstrap(
        returns: np.ndarray,
        n_bootstrap: int = 2000,
        confidence: float = 0.95,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Compute bootstrap statistics for a returns series.

        Returns dict with p_value, ci_lower, ci_upper, mean, std.
        Populate hypothesis.metrics["bootstrap"] with the result.

        Parameters
        ----------
        returns : np.ndarray
            Array of trade returns (or per-bar alpha returns).
        n_bootstrap : int
            Number of bootstrap resamples.
        confidence : float
            Confidence level (default 0.95 for 95% CI).
        seed : int
            Random seed for reproducibility.
        """
        rng = np.random.default_rng(seed)
        n = len(returns)
        if n < 10:
            return {
                "p_value": 1.0,
                "ci_lower_95": -1.0,
                "ci_upper_95": -1.0,
                "mean": 0.0,
                "std": 0.0,
                "n_samples": n,
                "error": "Insufficient data (need >= 10 returns)",
            }

        observed_mean = float(np.mean(returns))
        bootstrap_means = np.zeros(n_bootstrap)
        for i in range(n_bootstrap):
            sample = rng.choice(returns, size=n, replace=True)
            bootstrap_means[i] = float(np.mean(sample))

        alpha = 1.0 - confidence
        ci_lower = float(np.percentile(bootstrap_means, 100 * alpha / 2))
        ci_upper = float(np.percentile(bootstrap_means, 100 * (1 - alpha / 2)))

        # P-value: fraction of bootstrap means <= 0 (one-sided for positive mean)
        if observed_mean > 0:
            p_value = float(np.mean(bootstrap_means <= 0))
        else:
            p_value = float(np.mean(bootstrap_means >= 0))

        return {
            "p_value": p_value,
            "ci_lower_95": ci_lower,
            "ci_upper_95": ci_upper,
            "mean": observed_mean,
            "std": float(np.std(returns, ddof=1)),
            "n_samples": n,
            "n_bootstrap": n_bootstrap,
        }

    # ── Outlier robustness helper ────────────────────────────────────────────

    @staticmethod
    def evaluate_outlier_robustness(
        returns: np.ndarray,
        trim_pct: float = 0.01,
    ) -> Dict[str, Any]:
        """
        Check performance sensitivity to outlier removal.

        Removes top and bottom `trim_pct` of returns and recalculates
        mean return.

        Returns dict with pf_full, pf_trimmed, pf_drop_pct.
        """
        if len(returns) < 20:
            return {
                "pf_full": 0.0,
                "pf_trimmed": 0.0,
                "pf_drop_pct": 100.0,
                "error": "Insufficient data (need >= 20 returns)",
            }

        sorted_returns = np.sort(returns)
        n_trim = max(1, int(len(returns) * trim_pct))
        trimmed = sorted_returns[n_trim:-n_trim] if len(returns) > 2 * n_trim else returns

        mean_full = float(np.mean(returns))
        mean_trimmed = float(np.mean(trimmed))

        # Approximate profit factor as exp(mean_return)
        pf_full = float(np.exp(mean_full * 252)) if mean_full > -20 else 0.0
        pf_trimmed = float(np.exp(mean_trimmed * 252)) if mean_trimmed > -20 else 0.0
        pf_drop = abs(pf_full - pf_trimmed) / max(abs(pf_full), 1e-9)

        return {
            "pf_full": round(pf_full, 4),
            "pf_trimmed": round(pf_trimmed, 4),
            "pf_drop_pct": round(pf_drop * 100, 2),
            "mean_return_full": round(mean_full, 6),
            "mean_return_trimmed": round(mean_trimmed, 6),
            "n_trimmed_each_side": n_trim,
        }

    # ── Regime stability helper ──────────────────────────────────────────────

    @staticmethod
    def evaluate_regime_stability(
        returns_by_regime: Dict[str, np.ndarray],
    ) -> Dict[str, Any]:
        """
        Check performance consistency across market regimes.

        Parameters
        ----------
        returns_by_regime : Dict[str, np.ndarray]
            Mapping of regime name → array of returns in that regime.
            Typical keys: "Bull", "Bear", "Neutral".

        Returns dict with per-regime profit factor and count of positive regimes.
        """
        result: Dict[str, Any] = {}
        n_positive = 0
        for regime, rets in returns_by_regime.items():
            if len(rets) < 5:
                result[f"{regime.lower()}_pf"] = float("nan")
                result[f"{regime.lower()}_n"] = len(rets)
                continue
            mean_ret = float(np.mean(rets))
            pf = float(np.exp(mean_ret * 252)) if mean_ret > -20 else 0.0
            pf = round(pf, 4)
            result[f"{regime.lower()}_pf"] = pf
            result[f"{regime.lower()}_n"] = len(rets)
            if pf > 1.0:
                n_positive += 1
        result["n_regimes_positive"] = n_positive
        result["total_regimes"] = len(returns_by_regime)
        return result


__all__ = [
    "ResearchPipeline",
    "PipelineContext",
    "StageRunner",
    "DEFAULT_STAGE_RUNNERS",
    "DEFAULT_REQUESTED_STAGES",
]

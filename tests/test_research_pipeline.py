# tests/test_research_pipeline.py
"""
Tests for src/core/research_pipeline.py — 10-stage Research Pipeline.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.core.evidence_ladder import (
    EvidenceLadder,
    EvidenceLevel,
    HypothesisRecord,
    StageResult,
)
from src.core.research_pipeline import (
    PipelineContext,
    ResearchPipeline,
)


@pytest.fixture
def ladder(tmp_path):
    """Fresh ladder using a temporary file to avoid overwriting production data."""
    return EvidenceLadder(path=str(tmp_path / "test_evidence_ladder.json"))


@pytest.fixture
def pipeline(ladder):
    """Research pipeline with default context."""
    ctx = PipelineContext(
        require_economic_explanation=False,  # Skip Stage 1 for tests
        auto_promote=True,
        stop_on_failure=True,
    )
    return ResearchPipeline(ladder, context=ctx)


@pytest.fixture
def hypothesis():
    """A hypothesis with in-sample edge and walk-forward metrics seeded."""
    return HypothesisRecord(
        hypothesis_id="test_001",
        name="Test Hypothesis",
        family="TestFamily",
        description="A test hypothesis",
        economic_rationale="Test rationale",
        evidence_level=EvidenceLevel.L0,
        symbols=["BTCUSDT"],
        timeframes=["60"],
        metrics={
            "in_sample": {"profit_factor": 1.3, "sharpe": 0.8, "win_rate": 0.55},
            "walk_forward": {
                "n_windows": 15,
                "mean_ir": 0.5,
                "ir_positive_prob": 0.75,
                "dsr": 1.2,
            },
            "bootstrap": {
                "p_value": 0.01,
                "ci_lower_95": 0.02,
                "n_samples": 1000,
            },
            "outlier_robustness": {
                "pf_full": 1.3,
                "pf_trimmed": 1.15,
            },
            "transaction_costs": {
                "pf_gross": 1.4,
                "pf_net": 1.15,
                "annual_turnover": 12.0,
            },
            "regime_stability": {
                "bull_pf": 1.3,
                "bear_pf": 1.1,
                "neutral_pf": 0.9,
            },
            "cross_asset": {
                "assets_tested": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                "assets_passed": ["BTCUSDT", "ETHUSDT"],
            },
        },
    )


class TestResearchPipeline:
    def test_run_hypothesis_not_found(self, pipeline):
        result = pipeline.run_hypothesis("nonexistent")
        assert "error" in result
        assert result["stages_run"] == 0

    def test_run_hypothesis_archived(self, pipeline, ladder, hypothesis):
        hypothesis.archived = True
        ladder.register(hypothesis)
        result = pipeline.run_hypothesis("test_001")
        assert "archived" in result.get("error", "")

    def test_run_hypothesis_passes_stages(self, pipeline, ladder, hypothesis):
        """A hypothesis with seeded metrics should pass stages 2-6."""
        ladder.register(hypothesis)
        result = pipeline.run_hypothesis("test_001")
        assert result["stages_run"] > 0
        assert result["stages_passed"] > 0
        # Should pass at least stages 2-6 (in-sample, WF, bootstrap, outlier, costs)
        assert result["stages_passed"] >= 5

    def test_hypothesis_fails_and_demotes(self, pipeline, ladder):
        """A hypothesis without metrics should fail and be demoted to L0."""
        record = HypothesisRecord(
            hypothesis_id="test_fail",
            name="Failing Hypothesis",
            family="TestFamily",
            # No metrics — all stages should fail
        )
        ladder.register(record)
        result = pipeline.run_hypothesis("test_fail")
        assert result["stages_failed"] >= 1
        # Should be demoted to L0
        updated = ladder.get("test_fail")
        assert updated.evidence_level == EvidenceLevel.L0
        assert updated.retry_count >= 1

    def test_run_backlog(self, pipeline, ladder):
        r1 = HypothesisRecord(hypothesis_id="a", name="A", family="F")
        r1.retry_count = 1
        r2 = HypothesisRecord(hypothesis_id="b", name="B", family="F")
        r2.retry_count = 0
        r3 = HypothesisRecord(hypothesis_id="c", name="C", family="F",
                              evidence_level=EvidenceLevel.L3)
        ladder.register(r1)
        ladder.register(r2)
        ladder.register(r3)

        results = pipeline.run_backlog()
        # Only "a" should be in backlog
        assert len(results) == 1
        assert results[0]["hypothesis_id"] == "a"

    def test_run_never_tested(self, pipeline, ladder):
        r1 = HypothesisRecord(hypothesis_id="a", name="A", family="F")
        r1.retry_count = 0
        r2 = HypothesisRecord(hypothesis_id="b", name="B", family="F")
        r2.retry_count = 1
        ladder.register(r1)
        ladder.register(r2)

        results = pipeline.run_never_tested()
        assert len(results) == 1
        assert results[0]["hypothesis_id"] == "a"

    def test_run_all_l0(self, pipeline, ladder):
        r1 = HypothesisRecord(hypothesis_id="a", name="A", family="F")
        r1.retry_count = 0
        r2 = HypothesisRecord(hypothesis_id="b", name="B", family="F")
        r2.retry_count = 1
        r3 = HypothesisRecord(hypothesis_id="c", name="C", family="F",
                              evidence_level=EvidenceLevel.L3)
        ladder.register(r1)
        ladder.register(r2)
        ladder.register(r3)

        results = pipeline.run_all_l0()
        assert len(results) == 2  # Both L0 hypotheses

    def test_run_family(self, pipeline, ladder):
        r1 = HypothesisRecord(hypothesis_id="a", name="A", family="PositioningAlpha")
        r2 = HypothesisRecord(hypothesis_id="b", name="B", family="ExpansionAlpha")
        r3 = HypothesisRecord(hypothesis_id="c", name="C", family="PositioningAlpha")
        for r in [r1, r2, r3]:
            ladder.register(r)

        results = pipeline.run_family("PositioningAlpha")
        assert len(results) == 2

    def test_stop_on_failure(self, ladder):
        """With stop_on_failure=True, pipeline stops at first failure."""
        ctx = PipelineContext(
            require_economic_explanation=False,
            auto_promote=True,
            stop_on_failure=True,
        )
        pipeline = ResearchPipeline(ladder, context=ctx)

        # Only in-sample metrics (pass stage 2), nothing else
        record = HypothesisRecord(
            hypothesis_id="partial",
            name="Partial",
            family="TestFamily",
            metrics={
                "in_sample": {"profit_factor": 1.3, "sharpe": 0.8, "win_rate": 0.55},
                # No walk_forward metrics → Stage 3 will fail
            },
        )
        ladder.register(record)
        result = pipeline.run_hypothesis("partial")
        # Stage 2 should pass, Stage 3 should fail, pipeline stops
        assert result["stages_passed"] == 1
        assert result["stages_failed"] == 1
        assert result["stages_run"] == 2  # Stage 2 + Stage 3

    def test_continue_on_failure(self, ladder):
        """With stop_on_failure=False, pipeline continues after failure."""
        ctx = PipelineContext(
            require_economic_explanation=False,
            auto_promote=True,
            stop_on_failure=False,
        )
        pipeline = ResearchPipeline(ladder, context=ctx)

        record = HypothesisRecord(
            hypothesis_id="partial",
            name="Partial",
            family="TestFamily",
            metrics={
                "in_sample": {"profit_factor": 1.3, "sharpe": 0.8, "win_rate": 0.55},
            },
        )
        ladder.register(record)
        result = pipeline.run_hypothesis("partial")
        # Should run more stages even after failures
        assert result["stages_run"] > 2

    def test_custom_stage_runner(self, ladder):
        """Custom stage runner replaces default."""
        def custom_runner(hypothesis, ctx):
            return StageResult(
                stage=2, name="Custom In-Sample", passed=True,
                metrics={"custom_score": 999},
                notes="Custom runner executed",
            )

        pipeline = ResearchPipeline(
            ladder,
            context=PipelineContext(require_economic_explanation=False),
            stage_runners={2: custom_runner},
        )
        record = HypothesisRecord(
            hypothesis_id="custom",
            name="Custom",
            family="TestFamily",
            metrics={"in_sample": {"profit_factor": 1.3}},
        )
        ladder.register(record)
        result = pipeline.run_hypothesis("custom")
        # The custom runner always passes stage 2
        assert result["stages_passed"] >= 1

    def test_pipeline_saves_ladder(self, ladder, hypothesis):
        """Pipeline should save the ladder after running."""
        ctx = PipelineContext(
            require_economic_explanation=False,
            auto_promote=True,
            stop_on_failure=True,
        )
        pipeline = ResearchPipeline(ladder, context=ctx)
        ladder.register(hypothesis)
        pipeline.run_hypothesis("test_001")
        # After running, the hypothesis should be at a higher level
        updated = ladder.get("test_001")
        assert updated.evidence_level > EvidenceLevel.L0

    def test_requested_stages_subset(self, ladder, hypothesis):
        """Only run a subset of stages."""
        pipeline = ResearchPipeline(
            ladder,
            context=PipelineContext(require_economic_explanation=False),
        )
        ladder.register(hypothesis)
        # Only run stages 2 and 3
        result = pipeline.run_hypothesis("test_001", requested_stages=[2, 3])
        assert result["stages_run"] == 2


class TestBootstrapEvaluator:
    def test_positive_mean(self):
        returns = np.array([0.01, 0.02, -0.005, 0.015, 0.008, -0.003] * 5)
        result = ResearchPipeline.evaluate_bootstrap(returns)
        assert "p_value" in result
        assert "ci_lower_95" in result
        assert "ci_upper_95" in result
        assert result["mean"] > 0
        assert result["p_value"] <= 1.0

    def test_insufficient_data(self):
        returns = np.array([0.01])
        result = ResearchPipeline.evaluate_bootstrap(returns)
        assert "error" in result

    def test_negative_mean(self):
        returns = np.array([-0.01, -0.02, -0.005, -0.015, -0.008, -0.003] * 5)
        result = ResearchPipeline.evaluate_bootstrap(returns)
        assert result["mean"] < 0

    def test_reproducibility(self):
        returns = np.random.default_rng(42).normal(0.001, 0.02, 100)
        r1 = ResearchPipeline.evaluate_bootstrap(returns, seed=42)
        r2 = ResearchPipeline.evaluate_bootstrap(returns, seed=42)
        assert r1["p_value"] == r2["p_value"]


class TestOutlierRobustnessEvaluator:
    def test_normal_returns(self):
        returns = np.random.default_rng(42).normal(0.001, 0.02, 100)
        result = ResearchPipeline.evaluate_outlier_robustness(returns)
        assert "pf_full" in result
        assert "pf_trimmed" in result
        assert "pf_drop_pct" in result

    def test_with_outliers(self):
        """Returns with extreme outliers should show significant PF drop."""
        returns = np.array([0.001] * 98 + [0.50, -0.40])  # 2% extreme outliers
        result = ResearchPipeline.evaluate_outlier_robustness(returns)
        assert result["pf_drop_pct"] > 0

    def test_insufficient_data(self):
        returns = np.array([0.01] * 5)
        result = ResearchPipeline.evaluate_outlier_robustness(returns)
        assert "error" in result


class TestRegimeStabilityEvaluator:
    def test_all_regimes_positive(self):
        returns = {
            "Bull": np.array([0.02] * 20),
            "Bear": np.array([0.01] * 20),
            "Neutral": np.array([0.005] * 20),
        }
        result = ResearchPipeline.evaluate_regime_stability(returns)
        assert result["n_regimes_positive"] == 3

    def test_one_regime_negative(self):
        returns = {
            "Bull": np.array([0.02] * 20),
            "Bear": np.array([-0.03] * 20),
            "Neutral": np.array([0.005] * 20),
        }
        result = ResearchPipeline.evaluate_regime_stability(returns)
        assert result["n_regimes_positive"] == 2

    def test_insufficient_regime_data(self):
        returns = {"Bull": np.array([0.01] * 3)}  # Only 3 samples
        result = ResearchPipeline.evaluate_regime_stability(returns)
        assert result["bull_pf"] == 0.0 or result.get("bull_n", 0) < 5


class TestPipelineContext:
    def test_defaults(self):
        ctx = PipelineContext()
        assert ctx.min_walk_forward_windows == 12
        assert ctx.min_regime_count == 2
        assert ctx.min_cross_assets == 2
        assert ctx.auto_promote is True
        assert ctx.stop_on_failure is True

    def test_to_dict(self):
        ctx = PipelineContext()
        d = ctx.to_dict()
        assert d["min_walk_forward_windows"] == 12
        assert d["min_regime_count"] == 2

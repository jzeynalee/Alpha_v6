# tests/test_production_gate.py
"""Tests for Production Gate (Stage 10)."""

import pytest

from src.core.evidence_ladder import HypothesisRecord, EvidenceLevel
from src.core.production_gate import (
    ProductionGate,
    GateConfig,
    GateCheckResult,
    ProductionGateResult,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def gate():
    return ProductionGate(GateConfig())


@pytest.fixture
def valid_hypothesis():
    """A hypothesis with L5 (paper trading passed) and 6+ months live."""
    record = HypothesisRecord(
        hypothesis_id="prod_001",
        name="Production Ready Alpha",
        family="PositioningAlpha",
        evidence_level=EvidenceLevel.L5,
    )
    record.metrics["production"] = {
        "months_live": 7,
        "pf_live": 1.35,
        "sharpe_live": 0.85,
        "max_drawdown_pct": 8.5,
        "daily_pnl": 0.001,
        "consecutive_losses": 2,
    }
    return record


@pytest.fixture
def healthy_portfolio_state():
    return {
        "current_allocation": {"prod_001": 0.05},
        "daily_pnl": 0.005,
        "drawdown": 0.03,
        "regime": "Bull",
        "consecutive_losses": 1,
        "active_correlations": {"prod_001": 0.30},
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  GateConfig Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateConfig:
    def test_defaults(self):
        config = GateConfig()
        assert config.min_months_live == 6
        assert config.min_live_pf == 1.0
        assert config.max_allocation_pct == 0.10
        assert config.kill_switch is False
        assert "Bull" in config.allowed_regimes
        assert "Bear" in config.allowed_regimes

    def test_custom(self):
        config = GateConfig(
            min_months_live=12,
            max_allocation_pct=0.05,
            kill_switch=True,
        )
        assert config.min_months_live == 12
        assert config.kill_switch is True


# ═══════════════════════════════════════════════════════════════════════════════
#  GateCheckResult Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateCheckResult:
    def test_pass(self):
        r = GateCheckResult(
            check_name="test_check",
            passed=True,
            reason="All good",
            value=5,
            threshold=3,
        )
        assert r.passed is True
        assert r.check_name == "test_check"

    def test_fail(self):
        r = GateCheckResult(
            check_name="test_check",
            passed=False,
            reason="Too low",
            value=2,
            threshold=3,
        )
        assert r.passed is False


# ═══════════════════════════════════════════════════════════════════════════════
#  ProductionGateResult Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestProductionGateResult:
    def test_all_passed(self):
        checks = [
            GateCheckResult("c1", True, "ok"),
            GateCheckResult("c2", True, "ok"),
        ]
        result = ProductionGateResult(
            hypothesis_id="h1",
            passed=True,
            checks=checks,
        )
        assert result.passed is True
        assert len(result.failed_checks) == 0
        assert len(result.passed_checks) == 2

    def test_some_failed(self):
        checks = [
            GateCheckResult("c1", True, "ok"),
            GateCheckResult("c2", False, "fail"),
        ]
        result = ProductionGateResult(
            hypothesis_id="h1",
            passed=False,
            checks=checks,
        )
        assert result.passed is False
        assert len(result.failed_checks) == 1
        assert result.failed_checks[0].check_name == "c2"

    def test_render(self):
        checks = [
            GateCheckResult("check_a", True, "Passed"),
            GateCheckResult("check_b", False, "Failed"),
        ]
        result = ProductionGateResult("h1", False, checks)
        text = result.render()
        assert "BLOCKED" in text or "FAIL" in text
        assert "h1" in text


# ═══════════════════════════════════════════════════════════════════════════════
#  ProductionGate Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestProductionGate:
    def test_create(self, gate):
        assert gate.config.min_months_live == 6
        assert gate.config.kill_switch is False

    def test_evaluate_all_pass(self, gate, valid_hypothesis, healthy_portfolio_state):
        result = gate.evaluate(valid_hypothesis, healthy_portfolio_state)
        assert result.passed is True
        assert len(result.checks) == 10

    def test_evaluate_insufficient_months(self, gate, valid_hypothesis, healthy_portfolio_state):
        valid_hypothesis.metrics["production"]["months_live"] = 2
        result = gate.evaluate(valid_hypothesis, healthy_portfolio_state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("min_months_live" in c.check_name for c in failed)

    def test_evaluate_low_pf(self, gate, valid_hypothesis, healthy_portfolio_state):
        valid_hypothesis.metrics["production"]["pf_live"] = 0.85
        result = gate.evaluate(valid_hypothesis, healthy_portfolio_state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("profit_factor" in c.check_name for c in failed)

    def test_evaluate_negative_sharpe(self, gate, valid_hypothesis, healthy_portfolio_state):
        valid_hypothesis.metrics["production"]["sharpe_live"] = -0.5
        result = gate.evaluate(valid_hypothesis, healthy_portfolio_state)
        assert result.passed is False

    def test_evaluate_over_allocation(self, gate, valid_hypothesis):
        state = {
            "current_allocation": {"prod_001": 0.15},  # 15% > 10% max
            "daily_pnl": 0.0,
            "drawdown": 0.0,
            "regime": "Neutral",
            "consecutive_losses": 0,
            "active_correlations": {},
        }
        result = gate.evaluate(valid_hypothesis, state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("allocation" in c.check_name for c in failed)

    def test_evaluate_high_correlation(self, gate, valid_hypothesis):
        state = {
            "current_allocation": {},
            "daily_pnl": 0.0,
            "drawdown": 0.0,
            "regime": "Neutral",
            "consecutive_losses": 0,
            "active_correlations": {"prod_001": 0.85},  # > 0.70 budget
        }
        result = gate.evaluate(valid_hypothesis, state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("correlation" in c.check_name for c in failed)

    def test_evaluate_kill_switch(self, valid_hypothesis, healthy_portfolio_state):
        gate = ProductionGate(GateConfig(kill_switch=True))
        result = gate.evaluate(valid_hypothesis, healthy_portfolio_state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("kill_switch" in c.check_name for c in failed)

    def test_evaluate_daily_loss_limit(self, gate, valid_hypothesis):
        state = {
            "current_allocation": {},
            "daily_pnl": -0.05,  # -5% > 3% limit
            "drawdown": 0.0,
            "regime": "Neutral",
            "consecutive_losses": 0,
            "active_correlations": {},
        }
        result = gate.evaluate(valid_hypothesis, state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("daily_loss" in c.check_name for c in failed)

    def test_evaluate_drawdown_limit(self, gate, valid_hypothesis):
        state = {
            "current_allocation": {},
            "daily_pnl": 0.0,
            "drawdown": 0.20,  # 20% > 15% limit
            "regime": "Neutral",
            "consecutive_losses": 0,
            "active_correlations": {},
        }
        result = gate.evaluate(valid_hypothesis, state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("drawdown" in c.check_name for c in failed)

    def test_evaluate_consecutive_losses(self, gate, valid_hypothesis):
        state = {
            "current_allocation": {},
            "daily_pnl": 0.0,
            "drawdown": 0.0,
            "regime": "Neutral",
            "consecutive_losses": 10,  # > 8 limit
            "active_correlations": {},
        }
        result = gate.evaluate(valid_hypothesis, state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("consecutive_losses" in c.check_name for c in failed)

    def test_evaluate_disallowed_regime(self, gate, valid_hypothesis):
        state = {
            "current_allocation": {},
            "daily_pnl": 0.0,
            "drawdown": 0.0,
            "regime": "Crash",
            "consecutive_losses": 0,
            "active_correlations": {},
        }
        result = gate.evaluate(valid_hypothesis, state)
        assert result.passed is False
        failed = [c for c in result.checks if not c.passed]
        assert any("regime_permission" in c.check_name for c in failed)

    def test_evaluate_empty_hypothesis(self, gate):
        record = HypothesisRecord(
            hypothesis_id="empty",
            name="Empty",
            family="Test",
        )
        state = {
            "current_allocation": {},
            "daily_pnl": 0.0,
            "drawdown": 0.0,
            "regime": "Neutral",
            "consecutive_losses": 0,
            "active_correlations": {},
        }
        result = gate.evaluate(record, state)
        assert result.passed is False
        # Should fail on months_live and pf_live

    # ── Circuit breaker tests ──────────────────────────────────────────────────

    def test_check_circuit_breakers_pass(self, gate):
        state = {
            "daily_pnl": 0.01,
            "drawdown": 0.05,
            "consecutive_losses": 2,
        }
        result = gate.check_circuit_breakers(state)
        assert result.passed is True

    def test_check_circuit_breakers_kill_switch(self):
        gate = ProductionGate(GateConfig(kill_switch=True))
        state = {"daily_pnl": 0.01, "drawdown": 0.05, "consecutive_losses": 2}
        result = gate.check_circuit_breakers(state)
        assert result.passed is False
        assert "kill_switch" in result.check_name

    def test_check_circuit_breakers_daily_loss(self, gate):
        state = {
            "daily_pnl": -0.04,  # exceeds 3%
            "drawdown": 0.05,
            "consecutive_losses": 2,
        }
        result = gate.check_circuit_breakers(state)
        assert result.passed is False
        assert "daily_loss" in result.check_name

    def test_check_circuit_breakers_drawdown(self, gate):
        state = {
            "daily_pnl": 0.01,
            "drawdown": 0.20,  # exceeds 15%
            "consecutive_losses": 2,
        }
        result = gate.check_circuit_breakers(state)
        assert result.passed is False
        assert "drawdown" in result.check_name

    def test_check_circuit_breakers_consecutive(self, gate):
        state = {
            "daily_pnl": 0.01,
            "drawdown": 0.05,
            "consecutive_losses": 10,  # exceeds 8
        }
        result = gate.check_circuit_breakers(state)
        assert result.passed is False
        assert "consecutive" in result.check_name

    # ── Kill switch management ─────────────────────────────────────────────────

    def test_enable_kill_switch(self, gate):
        gate.enable_kill_switch("Testing")
        assert gate.config.kill_switch is True

    def test_disable_kill_switch(self, gate):
        gate.enable_kill_switch("Testing")
        gate.disable_kill_switch()
        assert gate.config.kill_switch is False

    # ── Update hypothesis metrics ──────────────────────────────────────────────

    def test_update_hypothesis_metrics(self, gate, valid_hypothesis, healthy_portfolio_state):
        result = gate.evaluate(valid_hypothesis, healthy_portfolio_state)
        gate.update_hypothesis_metrics(valid_hypothesis, result)
        prod = valid_hypothesis.metrics["production"]
        assert prod["gate_passed"] is True
        assert prod["gate_checks_passed"] == 10
        assert prod["gate_checks_total"] == 10
        assert "gate_timestamp" in prod

    def test_update_hypothesis_metrics_on_failure(self, gate):
        record = HypothesisRecord(
            hypothesis_id="fail_001",
            name="Failing",
            family="Test",
        )
        state = {
            "current_allocation": {},
            "daily_pnl": 0.0,
            "drawdown": 0.0,
            "regime": "Neutral",
            "consecutive_losses": 0,
            "active_correlations": {},
        }
        result = gate.evaluate(record, state)
        gate.update_hypothesis_metrics(record, result)
        prod = record.metrics["production"]
        assert prod["gate_passed"] is False
        assert prod["gate_checks_passed"] < prod["gate_checks_total"]

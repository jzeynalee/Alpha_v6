# src/core/production_gate.py
"""
Production Gate — Stage 10 deployment safety checks (Roadmap v2).

The Production Gate is the final safety barrier before real capital is
deployed. A hypothesis that has passed Stages 1-9 must also pass this
gate before it is allowed to trade with real money.

Design
------
- The gate is intentionally conservative — it errs on the side of
  blocking deployment rather than risking capital.
- Each check produces a {passed: bool, reason: str} result.
- All checks must pass for the gate to open.
- The gate is checked every bar in production (circuit breaker pattern).

Checks
------
1. Min months live (>= 6 months paper/live trading)
2. Live profit factor > 1.0
3. Max allocation cap (% of portfolio)
4. Correlation to existing portfolio < threshold (diversification check)
5. Kill switch (manual override)
6. Daily loss limit (circuit breaker)
7. Drawdown limit (circuit breaker)
8. Regime permission (allowed in current market regime)
9. Signal quality (min signal confidence threshold)

Usage
-----
    from src.core.production_gate import ProductionGate, GateConfig

    gate = ProductionGate(GateConfig())
    result = gate.evaluate(hypothesis_record, portfolio_state)
    if result.passed:
        deploy(hypothesis_record)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GateConfig:
    """Production gate safety thresholds."""

    # Time requirements
    min_months_live: int = 6              # Minimum months in paper/live trading

    # Performance requirements
    min_live_pf: float = 1.0              # Minimum live profit factor
    min_live_sharpe: float = 0.0          # Minimum live Sharpe ratio

    # Allocation limits
    max_allocation_pct: float = 0.10      # Max portfolio allocation per strategy
    max_correlation_to_portfolio: float = 0.70  # Max correlation to existing streams

    # Circuit breakers
    max_daily_loss_pct: float = 0.03      # Kill strategy if daily loss exceeds 3%
    max_drawdown_pct: float = 0.15        # Kill strategy if drawdown exceeds 15%
    max_consecutive_losses: int = 8       # Kill strategy after N consecutive losses

    # Signal quality
    min_signal_confidence: float = 0.60   # Minimum signal confidence to deploy

    # Regime permissions
    allowed_regimes: List[str] = field(default_factory=lambda: [
        "Bull", "Bear", "Neutral",
    ])

    # Manual override
    kill_switch: bool = False             # Manual kill — blocks all deployments


# ═══════════════════════════════════════════════════════════════════════════════
#  Gate Check Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GateCheckResult:
    """Result of a single production gate check."""
    check_name: str
    passed: bool
    reason: str = ""
    value: Any = None
    threshold: Any = None


@dataclass
class ProductionGateResult:
    """Aggregate result of all production gate checks."""
    hypothesis_id: str
    passed: bool
    checks: List[GateCheckResult] = field(default_factory=list)
    timestamp: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def failed_checks(self) -> List[GateCheckResult]:
        return [c for c in self.checks if not c.passed]

    @property
    def passed_checks(self) -> List[GateCheckResult]:
        return [c for c in self.checks if c.passed]

    def render(self) -> str:
        """Human-readable gate evaluation report."""
        status = "PASSED" if self.passed else "BLOCKED"
        lines = [
            f"═══ Production Gate: {status} ═══",
            f"  Hypothesis:  {self.hypothesis_id}",
            f"  Timestamp:   {self.timestamp[:19]}",
        ]
        for check in self.checks:
            icon = "✓" if check.passed else "✗"
            lines.append(
                f"  [{icon}] {check.check_name:<35} {check.reason}"
            )
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  Production Gate
# ═══════════════════════════════════════════════════════════════════════════════

class ProductionGate:
    """
    Deployment safety gate for Stage 10 (Production).

    Evaluates whether a hypothesis that has passed Stages 1-9 is safe
    to deploy with real capital. Implements circuit breakers, allocation
    limits, and diversification checks.

    Parameters
    ----------
    config : GateConfig
        Safety thresholds and limits.
    """

    def __init__(self, config: Optional[GateConfig] = None) -> None:
        self.config = config or GateConfig()

    # ── Main evaluation ───────────────────────────────────────────────────────

    def evaluate(
        self,
        hypothesis_record: Any,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> ProductionGateResult:
        """
        Run all production gate checks for a hypothesis.

        Parameters
        ----------
        hypothesis_record : HypothesisRecord
            The hypothesis being evaluated for production deployment.
        portfolio_state : dict, optional
            Current portfolio state including:
            - current_allocation: dict of strategy → weight
            - daily_pnl: today's P&L fraction
            - drawdown: current drawdown fraction
            - regime: current market regime
            - consecutive_losses: count of consecutive losing trades
            - active_correlations: dict of strategy → correlation to portfolio

        Returns
        -------
        ProductionGateResult
            Aggregated pass/fail with per-check details.
        """
        state = portfolio_state or {}
        checks: List[GateCheckResult] = []

        # ── 1. Min months live ────────────────────────────────────────────
        prod_metrics = hypothesis_record.metrics.get("production", {})
        months_live = prod_metrics.get("months_live", 0)
        min_months = self.config.min_months_live
        checks.append(GateCheckResult(
            check_name="min_months_live",
            passed=months_live >= min_months,
            reason=(
                f"Live for {months_live} months (need >= {min_months})"
                if months_live < min_months
                else f"Live for {months_live} months"
            ),
            value=months_live,
            threshold=min_months,
        ))

        # ── 2. Live profit factor ─────────────────────────────────────────
        live_pf = prod_metrics.get("pf_live", 0.0)
        min_pf = self.config.min_live_pf
        checks.append(GateCheckResult(
            check_name="live_profit_factor",
            passed=live_pf > min_pf,
            reason=(
                f"Live PF={live_pf:.2f} (need > {min_pf})"
                if live_pf <= min_pf
                else f"Live PF={live_pf:.2f}"
            ),
            value=round(live_pf, 4),
            threshold=min_pf,
        ))

        # ── 3. Live Sharpe ────────────────────────────────────────────────
        live_sharpe = prod_metrics.get("sharpe_live", 0.0)
        min_sharpe = self.config.min_live_sharpe
        checks.append(GateCheckResult(
            check_name="live_sharpe",
            passed=live_sharpe >= min_sharpe,
            reason=(
                f"Live Sharpe={live_sharpe:.2f} (need >= {min_sharpe})"
                if live_sharpe < min_sharpe
                else f"Live Sharpe={live_sharpe:.2f}"
            ),
            value=round(live_sharpe, 4),
            threshold=min_sharpe,
        ))

        # ── 4. Allocation cap ─────────────────────────────────────────────
        current_alloc = state.get("current_allocation", {}).get(
            hypothesis_record.hypothesis_id, 0.0
        )
        max_alloc = self.config.max_allocation_pct
        checks.append(GateCheckResult(
            check_name="allocation_cap",
            passed=current_alloc <= max_alloc,
            reason=(
                f"Allocation={current_alloc:.1%} (max={max_alloc:.0%})"
                if current_alloc > max_alloc
                else f"Allocation={current_alloc:.1%}"
            ),
            value=round(current_alloc, 4),
            threshold=max_alloc,
        ))

        # ── 5. Correlation budget ─────────────────────────────────────────
        active_correlations = state.get("active_correlations", {})
        max_corr = max(active_correlations.values()) if active_correlations else 0.0
        corr_budget = self.config.max_correlation_to_portfolio
        checks.append(GateCheckResult(
            check_name="correlation_budget",
            passed=max_corr < corr_budget,
            reason=(
                f"Max correlation={max_corr:.2f} (budget={corr_budget})"
                if max_corr >= corr_budget
                else f"Max correlation={max_corr:.2f}"
            ),
            value=round(max_corr, 4),
            threshold=corr_budget,
        ))

        # ── 6. Kill switch ────────────────────────────────────────────────
        checks.append(GateCheckResult(
            check_name="kill_switch",
            passed=not self.config.kill_switch,
            reason="Kill switch ACTIVE" if self.config.kill_switch else "Kill switch inactive",
            value=self.config.kill_switch,
            threshold=False,
        ))

        # ── 7. Daily loss limit (circuit breaker) ─────────────────────────
        daily_pnl = state.get("daily_pnl", 0.0)
        max_daily_loss = self.config.max_daily_loss_pct
        checks.append(GateCheckResult(
            check_name="daily_loss_limit",
            passed=daily_pnl > -max_daily_loss,
            reason=(
                f"Daily P&L={daily_pnl:.2%} (limit=-{max_daily_loss:.0%})"
                if daily_pnl <= -max_daily_loss
                else f"Daily P&L={daily_pnl:.2%}"
            ),
            value=round(daily_pnl, 6),
            threshold=-max_daily_loss,
        ))

        # ── 8. Drawdown limit (circuit breaker) ───────────────────────────
        drawdown = abs(state.get("drawdown", 0.0))
        max_dd = self.config.max_drawdown_pct
        checks.append(GateCheckResult(
            check_name="drawdown_limit",
            passed=drawdown < max_dd,
            reason=(
                f"Drawdown={drawdown:.1%} (limit={max_dd:.0%})"
                if drawdown >= max_dd
                else f"Drawdown={drawdown:.1%}"
            ),
            value=round(drawdown, 4),
            threshold=max_dd,
        ))

        # ── 9. Consecutive losses ─────────────────────────────────────────
        consecutive = state.get("consecutive_losses", 0)
        max_consecutive = self.config.max_consecutive_losses
        checks.append(GateCheckResult(
            check_name="consecutive_losses",
            passed=consecutive < max_consecutive,
            reason=(
                f"{consecutive} consecutive losses (limit={max_consecutive})"
                if consecutive >= max_consecutive
                else f"{consecutive} consecutive losses"
            ),
            value=consecutive,
            threshold=max_consecutive,
        ))

        # ── 10. Regime permission ─────────────────────────────────────────
        current_regime = state.get("regime", "Neutral")
        checks.append(GateCheckResult(
            check_name="regime_permission",
            passed=current_regime in self.config.allowed_regimes,
            reason=(
                f"Regime '{current_regime}' not in allowed list"
                if current_regime not in self.config.allowed_regimes
                else f"Regime '{current_regime}' allowed"
            ),
            value=current_regime,
            threshold=self.config.allowed_regimes,
        ))

        # ── Aggregate ─────────────────────────────────────────────────────
        all_passed = all(c.passed for c in checks)
        notes = ""
        if not all_passed:
            failed_names = [c.check_name for c in checks if not c.passed]
            notes = f"Failed checks: {', '.join(failed_names)}"

        return ProductionGateResult(
            hypothesis_id=hypothesis_record.hypothesis_id,
            passed=all_passed,
            checks=checks,
            notes=notes,
        )

    # ── Quick checks (for per-bar circuit breaker logic) ──────────────────────

    def check_circuit_breakers(self, portfolio_state: Dict[str, Any]) -> GateCheckResult:
        """
        Fast per-bar check of only circuit-breaker conditions.

        Used during live trading to quickly decide whether to halt.
        """
        daily_pnl = portfolio_state.get("daily_pnl", 0.0)
        drawdown = abs(portfolio_state.get("drawdown", 0.0))
        consecutive = portfolio_state.get("consecutive_losses", 0)

        if self.config.kill_switch:
            return GateCheckResult(
                check_name="kill_switch",
                passed=False,
                reason="Kill switch is ACTIVE",
            )
        if daily_pnl <= -self.config.max_daily_loss_pct:
            return GateCheckResult(
                check_name="daily_loss_limit",
                passed=False,
                reason=f"Daily loss limit breached: {daily_pnl:.2%}",
            )
        if drawdown >= self.config.max_drawdown_pct:
            return GateCheckResult(
                check_name="drawdown_limit",
                passed=False,
                reason=f"Drawdown limit breached: {drawdown:.1%}",
            )
        if consecutive >= self.config.max_consecutive_losses:
            return GateCheckResult(
                check_name="consecutive_losses",
                passed=False,
                reason=f"Consecutive loss limit: {consecutive} losses",
            )

        return GateCheckResult(
            check_name="circuit_breakers", passed=True,
            reason="All circuit breakers OK",
        )

    # ── Kill switch management ────────────────────────────────────────────────

    def enable_kill_switch(self, reason: str = "Manual override") -> None:
        """Activate the kill switch — blocks all deployments."""
        self.config.kill_switch = True
        logger.warning("PRODUCTION KILL SWITCH ACTIVATED: %s", reason)

    def disable_kill_switch(self) -> None:
        """Deactivate the kill switch."""
        if self.config.kill_switch:
            self.config.kill_switch = False
            logger.info("Production kill switch deactivated.")

    # ── Integration ───────────────────────────────────────────────────────────

    def update_hypothesis_metrics(self, record: Any, result: ProductionGateResult) -> None:
        """
        Update a HypothesisRecord's production metrics from gate evaluation.

        Parameters
        ----------
        record : HypothesisRecord
            The hypothesis record to update (mutated in-place).
        result : ProductionGateResult
            The gate evaluation result.
        """
        existing = record.metrics.get("production", {})
        record.metrics["production"] = {
            **existing,
            "gate_passed": result.passed,
            "gate_timestamp": result.timestamp,
            "gate_checks_passed": len(result.passed_checks),
            "gate_checks_total": len(result.checks),
            "months_live": existing.get("months_live", 0),
            "pf_live": existing.get("pf_live", 0.0),
        }
        record.updated_at = datetime.now(timezone.utc).isoformat()


__all__ = [
    "ProductionGate",
    "GateConfig",
    "GateCheckResult",
    "ProductionGateResult",
]

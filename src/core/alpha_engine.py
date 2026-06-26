# src/core/alpha_engine.py
"""
Alpha Engine — multi-strategy portfolio orchestrator (Roadmap v2).

The AlphaEngine combines multiple independent alpha streams into a single
portfolio, implementing the long-term objective from the Research Roadmap:

    "Build an AlphaEngine composed of multiple independent alpha streams:
     Positioning Alpha, Cross-Section Alpha, Momentum Alpha, Mean-Reversion
     Alpha, Liquidation Alpha, Volatility Alpha, Relative Value Alpha.

     Each stream contributes a small but robust edge.

     The portfolio—not any individual strategy—is expected to generate
     durable long-term alpha."

Design
------
- Each alpha stream is a named strategy with a signal source and metadata.
- Sizing uses Fractional Kelly (default 0.25, configurable per stream).
- Risk parity allocates equal risk contribution across streams.
- Correlation budgeting limits concentration in similar strategies.
- Volatility targeting scales total portfolio to a target vol (default 12%).
- The engine integrates with StrategyRepository for active strategy management.

Usage
-----
    from src.core.alpha_engine import AlphaEngine, AlphaStream, EngineConfig

    engine = AlphaEngine(EngineConfig())
    engine.register_stream(AlphaStream(
        name="Positioning",
        family="PositioningAlpha",
        evidence_level=EvidenceLevel.L3,
    ))
    weights = engine.allocate(state)
    # weights = {"Positioning": 0.25, "CrossSection": 0.20, ...}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from src.core.evidence_ladder import EvidenceLevel

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EngineConfig:
    """Alpha Engine configuration parameters."""

    # Sizing
    kelly_fraction: float = 0.25          # Fractional Kelly multiplier
    half_kelly: bool = False              # Use Half-Kelly (0.5 × kelly_fraction)
    max_per_strategy: float = 0.25        # Cap at 25% per strategy
    min_per_strategy: float = 0.01        # Minimum allocation to keep a strategy

    # Risk
    target_portfolio_vol: float = 0.12    # 12% annualized
    max_leverage: float = 2.0             # Maximum gross leverage
    risk_parity: bool = True              # Use risk parity weighting
    correlation_budget: float = 0.65      # Max pairwise correlation before penalty

    # Regime adjustment
    regime_scale: Dict[str, float] = field(default_factory=lambda: {
        "Bull": 1.0,
        "Bear": 1.0,
        "Neutral": 1.0,
    })

    # Evidence-based weighting
    evidence_weight_multipliers: Dict[EvidenceLevel, float] = field(default_factory=lambda: {
        EvidenceLevel.L0: 0.0,    # Don't allocate to unvalidated ideas
        EvidenceLevel.L1: 0.0,    # In-sample edge only — not tradeable
        EvidenceLevel.L2: 0.0,    # Survived costs but not walk-forward
        EvidenceLevel.L3: 0.25,   # Walk-forward validated — reduced sizing
        EvidenceLevel.L4: 0.50,   # Cross-asset validated — moderate sizing
        EvidenceLevel.L5: 0.75,   # Paper trading survived — near full sizing
        EvidenceLevel.L6: 1.0,    # Production grade — full allocation
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  Alpha Stream
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AlphaStream:
    """
    One independent alpha stream in the portfolio.

    Each stream represents a family of strategies (e.g., PositioningAlpha)
    that generates signals with a particular edge.
    """
    name: str                                    # Unique stream name
    family: str                                  # Alpha family (e.g., "PositioningAlpha")
    evidence_level: EvidenceLevel = EvidenceLevel.L0

    # Performance estimates (updated from live/backtest)
    expected_return: float = 0.0                 # Annualized expected return
    expected_vol: float = 0.12                   # Annualized expected volatility
    sharpe: float = 0.0                          # Expected Sharpe ratio

    # Signal callback — returns (direction, confidence) for current bar
    signal_fn: Optional[Callable[[], Tuple[int, float]]] = None

    # Correlation to other streams (updated dynamically)
    correlations: Dict[str, float] = field(default_factory=dict)

    # Metadata
    symbols: List[str] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    weight: float = 0.0                          # Current allocation weight

    def kelly_allocation(self, fraction: float = 0.25) -> float:
        """
        Unconstrained Kelly allocation: f* = μ / σ².

        For a stream with Sharpe S and vol σ:
            f* = (S × σ) / σ² = S / σ
        Then fractional: f = fraction × min(f*, max_per_strategy).
        """
        if self.expected_vol <= 0 or self.expected_return <= 0:
            return 0.0
        # Kelly: f* = μ / σ²
        kelly_raw = self.expected_return / (self.expected_vol ** 2)
        kelly_capped = min(kelly_raw, 2.0)  # Cap at 200% for stability
        return fraction * kelly_capped

    @property
    def is_tradeable(self) -> bool:
        """A stream is tradeable at L3+ (survived walk-forward)."""
        return self.evidence_level >= EvidenceLevel.L3 and self.enabled


# ═══════════════════════════════════════════════════════════════════════════════
#  Portfolio State
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PortfolioState:
    """Snapshot of current portfolio conditions used for allocation decisions."""
    current_regime: str = "Neutral"              # Current market regime
    regime_entropy: float = 0.0                  # Regime uncertainty
    current_leverage: float = 0.0                # Current gross leverage
    daily_pnl: float = 0.0                       # Today's P&L (fraction)
    month_pnl: float = 0.0                       # Month P&L (fraction)
    drawdown: float = 0.0                        # Current drawdown from peak
    market_vol: float = 0.12                     # Current market realized vol (annualized)


# ═══════════════════════════════════════════════════════════════════════════════
#  Alpha Engine
# ═══════════════════════════════════════════════════════════════════════════════

class AlphaEngine:
    """
    Portfolio-level orchestrator for multiple alpha streams.

    Responsibilities:
      - Register and manage independent alpha streams
      - Allocate capital via Kelly + risk parity + correlation budgeting
      - Scale by evidence level (L3-L6 only get capital)
      - Volatility targeting at portfolio level
      - Regime-based allocation multipliers

    The engine is the production counterpart to the ResearchPipeline —
    the pipeline discovers and validates hypotheses; the engine deploys
    the validated streams as a portfolio.
    """

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self._streams: Dict[str, AlphaStream] = {}

    # ── Stream management ────────────────────────────────────────────────────

    def register_stream(self, stream: AlphaStream) -> None:
        """Register an alpha stream for portfolio allocation."""
        if stream.name in self._streams:
            logger.warning("Stream '%s' already registered — overwriting.", stream.name)
        self._streams[stream.name] = stream
        logger.info(
            "AlphaStream REGISTERED: %s (family=%s, L%d, Sharpe=%.2f)",
            stream.name, stream.family,
            stream.evidence_level.value, stream.sharpe,
        )

    def remove_stream(self, name: str) -> bool:
        """Remove a stream from the engine."""
        if name in self._streams:
            del self._streams[name]
            logger.info("AlphaStream REMOVED: %s", name)
            return True
        return False

    def get_stream(self, name: str) -> Optional[AlphaStream]:
        return self._streams.get(name)

    def list_streams(self) -> List[AlphaStream]:
        return list(self._streams.values())

    def list_active(self) -> List[AlphaStream]:
        """Return enabled tradeable streams (L3+)."""
        return [s for s in self._streams.values() if s.is_tradeable]

    def list_candidates(self) -> List[AlphaStream]:
        """Return streams at L4+ (cross-asset validated or better)."""
        return [
            s for s in self._streams.values()
            if s.enabled and s.evidence_level >= EvidenceLevel.L4
        ]

    # ── Allocation ───────────────────────────────────────────────────────────

    def allocate(self, state: Optional[PortfolioState] = None) -> Dict[str, float]:
        """
        Compute portfolio weights for all active streams.

        Algorithm:
          1. Filter to tradeable streams (L3+, enabled).
          2. Compute unconstrained Kelly allocation per stream.
          3. Apply evidence-level multiplier (L3=0.25×, L4=0.50×, etc.).
          4. Apply risk parity if enabled (weights ∝ 1/vol).
          5. Enforce correlation budget (penalize correlated streams).
          6. Apply regime-based scaling.
          7. Normalize to sum ≤ max_leverage.
          8. Clip individual weights to [min_per_strategy, max_per_strategy].

        Parameters
        ----------
        state : PortfolioState, optional
            Current portfolio state for regime-aware allocation.

        Returns
        -------
        Dict[str, float]
            Mapping of stream name → allocation weight (fraction of equity).
        """
        state = state or PortfolioState()
        active = self.list_active()
        if not active:
            logger.debug("No active streams — returning empty allocation.")
            return {}

        n = len(active)
        names = [s.name for s in active]

        # ── Step 1: Unconstrained Kelly ──────────────────────────────────────
        kf = self.config.kelly_fraction
        if self.config.half_kelly:
            kf *= 0.5

        kelly_weights = np.array([
            s.kelly_allocation(kf) for s in active
        ])

        # ── Step 2: Evidence-level multiplier ────────────────────────────────
        evidence_mult = np.array([
            self.config.evidence_weight_multipliers.get(s.evidence_level, 0.0)
            for s in active
        ])
        weights = kelly_weights * evidence_mult

        # ── Step 3: Risk parity adjustment ───────────────────────────────────
        if self.config.risk_parity:
            vols = np.array([max(s.expected_vol, 0.01) for s in active])
            risk_parity_weights = 1.0 / vols
            risk_parity_weights /= risk_parity_weights.sum()
            # Blend: 50% Kelly, 50% risk parity
            weights = 0.5 * weights + 0.5 * risk_parity_weights

        # ── Step 4: Correlation penalty ──────────────────────────────────────
        corr_penalty = self._correlation_penalty(active)
        weights *= corr_penalty

        # ── Step 5: Regime scaling ───────────────────────────────────────────
        regime_mult = self.config.regime_scale.get(state.current_regime, 1.0)
        # In high-entropy regimes, reduce sizing
        entropy_penalty = max(0.5, 1.0 - state.regime_entropy)
        weights *= regime_mult * entropy_penalty

        # If we're in drawdown, reduce sizing proportionally
        if state.drawdown > 0.05:
            dd_scale = max(0.25, 1.0 - state.drawdown / 0.15)
            weights *= dd_scale

        # ── Step 6: Normalize to target leverage ─────────────────────────────
        total_weight = float(np.sum(np.abs(weights)))
        if total_weight > 0:
            # Scale to target volatility if we have market vol estimate
            portfolio_vol = self._estimate_portfolio_vol(active, weights)
            if portfolio_vol > 0:
                vol_scale = self.config.target_portfolio_vol / portfolio_vol
                weights *= min(vol_scale, self.config.max_leverage / max(total_weight, 1e-9))

            # Enforce max leverage
            if total_weight > self.config.max_leverage:
                weights *= self.config.max_leverage / total_weight

        # ── Step 7: Clip individual weights ──────────────────────────────────
        weights = np.clip(
            weights,
            self.config.min_per_strategy,
            self.config.max_per_strategy,
        )

        # ── Step 8: Re-normalize after clipping ──────────────────────────────
        total = float(np.sum(np.abs(weights)))
        if total > self.config.max_leverage:
            weights *= self.config.max_leverage / total

        # Build result
        result = {}
        for name, w in zip(names, weights):
            result[name] = round(float(w), 6)
            # Update stream weight
            self._streams[name].weight = result[name]

        logger.debug(
            "AlphaEngine allocation: %d streams, total_weight=%.3f, regime=%s",
            n, sum(result.values()), state.current_regime,
        )
        return result

    def _correlation_penalty(self, streams: List[AlphaStream]) -> np.ndarray:
        """
        Compute per-stream penalty based on average correlation to other streams.

        Streams highly correlated with others get reduced weight to avoid
        concentration in a single bet.
        """
        n = len(streams)
        if n <= 1:
            return np.ones(n)

        penalties = np.ones(n)
        for i, s_i in enumerate(streams):
            avg_corr = 0.0
            count = 0
            for j, s_j in enumerate(streams):
                if i == j:
                    continue
                corr = s_i.correlations.get(s_j.name, 0.0)
                avg_corr += abs(corr)
                count += 1
            if count > 0:
                avg_corr /= count
                # Linear penalty: corr above budget reduces weight
                excess = max(0.0, avg_corr - self.config.correlation_budget)
                penalties[i] = max(0.1, 1.0 - excess * 2.0)

        return penalties

    def _estimate_portfolio_vol(
        self,
        streams: List[AlphaStream],
        weights: np.ndarray,
    ) -> float:
        """Estimate portfolio volatility from stream vols and correlations."""
        n = len(streams)
        if n == 0:
            return 0.0

        vols = np.array([s.expected_vol for s in streams])
        # Build correlation matrix
        corr_matrix = np.eye(n)
        for i, s_i in enumerate(streams):
            for j, s_j in enumerate(streams):
                if i != j:
                    corr_matrix[i, j] = s_i.correlations.get(s_j.name, 0.0)

        # Portfolio variance: w^T Σ w
        cov = np.outer(vols, vols) * corr_matrix
        port_var = weights @ cov @ weights
        return float(np.sqrt(max(port_var, 0.0)))

    # ── Signal aggregation ──────────────────────────────────────────────────

    def aggregate_signals(self) -> Dict[str, Tuple[int, float]]:
        """
        Poll all active streams for current signals.

        Returns
        -------
        Dict[str, Tuple[int, float]]
            Mapping of stream name → (direction, confidence).
            direction: +1 (long), -1 (short), 0 (flat).
            confidence: [0, 1].
        """
        signals: Dict[str, Tuple[int, float]] = {}
        for stream in self.list_active():
            if stream.signal_fn is not None:
                try:
                    direction, confidence = stream.signal_fn()
                    signals[stream.name] = (direction, confidence)
                except Exception as exc:
                    logger.warning(
                        "Signal function failed for stream '%s': %s",
                        stream.name, exc,
                    )
        return signals

    # ── Performance tracking ─────────────────────────────────────────────────

    def update_performance(
        self,
        stream_name: str,
        return_pct: float,
    ) -> None:
        """Update a stream's performance estimate with a new return observation."""
        stream = self._streams.get(stream_name)
        if stream is None:
            return
        # EWMA update of Sharpe estimate
        alpha = 0.05  # ~20-period half-life
        if stream.sharpe == 0.0:
            stream.sharpe = return_pct / max(stream.expected_vol, 0.01)
        else:
            new_sharpe = return_pct / max(stream.expected_vol, 0.01)
            stream.sharpe = alpha * new_sharpe + (1 - alpha) * stream.sharpe

        stream.expected_return = stream.sharpe * stream.expected_vol

    def update_correlations(
        self,
        correlation_matrix: Dict[str, Dict[str, float]],
    ) -> None:
        """Update pairwise stream correlations from an external estimator."""
        for name_i, corrs in correlation_matrix.items():
            stream = self._streams.get(name_i)
            if stream is None:
                continue
            stream.correlations = corrs

    # ── Summary ──────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a structured summary for dashboards."""
        streams_info = []
        total_weight = 0.0
        for s in self._streams.values():
            streams_info.append({
                "name": s.name,
                "family": s.family,
                "evidence_level": f"L{s.evidence_level.value}",
                "sharpe": round(s.sharpe, 3),
                "weight": round(s.weight, 4),
                "enabled": s.enabled,
                "tradeable": s.is_tradeable,
            })
            total_weight += s.weight

        return {
            "total_streams": len(self._streams),
            "active_streams": len(self.list_active()),
            "candidate_streams": len(self.list_candidates()),
            "total_allocation": round(total_weight, 4),
            "target_vol": self.config.target_portfolio_vol,
            "max_leverage": self.config.max_leverage,
            "streams": streams_info,
        }

    def render_summary(self) -> str:
        """Human-readable summary string."""
        s = self.summary()
        lines = [
            "═══ Alpha Engine Summary ═══",
            f"  Total streams:    {s['total_streams']}",
            f"  Active (L3+):     {s['active_streams']}",
            f"  Candidates (L4+): {s['candidate_streams']}",
            f"  Total allocation: {s['total_allocation']:.2%}",
            f"  Target vol:       {s['target_vol']:.0%}",
            f"  Max leverage:     {s['max_leverage']:.1f}x",
            "",
            "  Streams:",
        ]
        for si in s["streams"]:
            status = "✓" if si["tradeable"] else "✗"
            lines.append(
                f"    [{status}] {si['name']:<25} {si['family']:<20} "
                f"{si['evidence_level']}  Sharpe={si['sharpe']:.2f}  "
                f"w={si['weight']:.3f}"
            )
        return "\n".join(lines)


__all__ = [
    "AlphaEngine",
    "AlphaStream",
    "EngineConfig",
    "PortfolioState",
]

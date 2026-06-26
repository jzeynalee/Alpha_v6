# tests/test_alpha_engine.py
"""
Tests for src/core/alpha_engine.py — Alpha Engine portfolio orchestrator.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.core.alpha_engine import (
    AlphaEngine,
    AlphaStream,
    EngineConfig,
    PortfolioState,
)
from src.core.evidence_ladder import EvidenceLevel


class TestAlphaStream:
    def test_create(self):
        stream = AlphaStream(
            name="Positioning",
            family="PositioningAlpha",
            evidence_level=EvidenceLevel.L3,
            expected_return=0.15,
            expected_vol=0.20,
            sharpe=0.75,
        )
        assert stream.name == "Positioning"
        assert stream.family == "PositioningAlpha"
        assert stream.evidence_level == EvidenceLevel.L3
        assert stream.is_tradeable  # L3+

    def test_not_tradeable_below_l3(self):
        stream = AlphaStream(
            name="Early",
            family="Test",
            evidence_level=EvidenceLevel.L1,
        )
        assert not stream.is_tradeable

    def test_kelly_allocation(self):
        stream = AlphaStream(
            name="Test",
            family="Test",
            expected_return=0.20,
            expected_vol=0.25,
        )
        # f* = μ / σ² = 0.20 / 0.0625 = 3.2 → capped at 2.0
        # fractional = 0.25 × 2.0 = 0.5
        alloc = stream.kelly_allocation(fraction=0.25)
        assert alloc == pytest.approx(0.5, rel=0.01)

    def test_kelly_zero_when_no_return(self):
        stream = AlphaStream(
            name="Test",
            family="Test",
            expected_return=0.0,
            expected_vol=0.20,
        )
        assert stream.kelly_allocation() == 0.0


class TestAlphaEngine:
    @pytest.fixture
    def engine(self):
        return AlphaEngine()

    @pytest.fixture
    def streams(self):
        return [
            AlphaStream(
                name="Positioning",
                family="PositioningAlpha",
                evidence_level=EvidenceLevel.L3,
                expected_return=0.20,
                expected_vol=0.25,
                sharpe=0.8,
            ),
            AlphaStream(
                name="CrossSection",
                family="CrossSectionAlpha",
                evidence_level=EvidenceLevel.L4,
                expected_return=0.15,
                expected_vol=0.18,
                sharpe=0.83,
            ),
            AlphaStream(
                name="Expansion",
                family="ExpansionAlpha",
                evidence_level=EvidenceLevel.L3,
                expected_return=0.12,
                expected_vol=0.22,
                sharpe=0.55,
            ),
        ]

    def test_register_and_retrieve(self, engine, streams):
        engine.register_stream(streams[0])
        assert engine.get_stream("Positioning") is streams[0]
        assert engine.get_stream("Nonexistent") is None

    def test_remove_stream(self, engine, streams):
        engine.register_stream(streams[0])
        assert engine.remove_stream("Positioning")
        assert not engine.remove_stream("Nonexistent")

    def test_list_streams(self, engine, streams):
        for s in streams:
            engine.register_stream(s)
        assert len(engine.list_streams()) == 3

    def test_list_active_only_l3_plus(self, engine):
        engine.register_stream(AlphaStream(
            name="L0", family="F", evidence_level=EvidenceLevel.L0,
        ))
        engine.register_stream(AlphaStream(
            name="L1", family="F", evidence_level=EvidenceLevel.L1,
        ))
        engine.register_stream(AlphaStream(
            name="L2", family="F", evidence_level=EvidenceLevel.L2,
        ))
        engine.register_stream(AlphaStream(
            name="L3", family="F", evidence_level=EvidenceLevel.L3,
            expected_return=0.10, expected_vol=0.20,
        ))
        engine.register_stream(AlphaStream(
            name="L4", family="F", evidence_level=EvidenceLevel.L4,
            expected_return=0.15, expected_vol=0.20,
        ))
        active = engine.list_active()
        assert len(active) == 2  # L3 and L4
        names = {s.name for s in active}
        assert names == {"L3", "L4"}

    def test_list_candidates(self, engine):
        engine.register_stream(AlphaStream(
            name="L3", family="F", evidence_level=EvidenceLevel.L3,
        ))
        engine.register_stream(AlphaStream(
            name="L4", family="F", evidence_level=EvidenceLevel.L4,
        ))
        engine.register_stream(AlphaStream(
            name="L5", family="F", evidence_level=EvidenceLevel.L5,
        ))
        candidates = engine.list_candidates()
        assert len(candidates) == 2  # L4 and L5

    def test_allocate_empty(self, engine):
        weights = engine.allocate()
        assert weights == {}

    def test_allocate_no_tradeable(self, engine):
        engine.register_stream(AlphaStream(
            name="Early", family="F", evidence_level=EvidenceLevel.L1,
        ))
        weights = engine.allocate()
        assert weights == {}

    def test_allocate_basic(self, engine, streams):
        for s in streams:
            engine.register_stream(s)
        weights = engine.allocate()

        assert len(weights) == 3
        assert "Positioning" in weights
        assert "CrossSection" in weights
        assert "Expansion" in weights

        # All weights should be positive and within bounds
        for name, w in weights.items():
            assert 0.0 <= w <= engine.config.max_per_strategy, \
                f"{name} weight {w} out of bounds"

    def test_allocate_respects_max_per_strategy(self, engine):
        """No single stream should exceed max_per_strategy."""
        engine.config.max_per_strategy = 0.25
        engine.register_stream(AlphaStream(
            name="MegaReturn",
            family="F",
            evidence_level=EvidenceLevel.L6,  # Full multiplier
            expected_return=1.0,   # Very high return
            expected_vol=0.10,     # Low vol
        ))
        weights = engine.allocate()
        for w in weights.values():
            assert w <= 0.25, f"Weight {w} exceeds max_per_strategy"

    def test_allocate_in_bull_regime(self, engine, streams):
        for s in streams:
            engine.register_stream(s)
        state = PortfolioState(current_regime="Bull")
        weights = engine.allocate(state)
        assert len(weights) == 3

    def test_allocate_in_high_entropy(self, engine, streams):
        """High entropy should reduce allocation sizes."""
        for s in streams:
            engine.register_stream(s)

        state_normal = PortfolioState(regime_entropy=0.0)
        state_high_entropy = PortfolioState(regime_entropy=0.8)

        weights_normal = engine.allocate(state_normal)
        weights_high = engine.allocate(state_high_entropy)

        total_normal = sum(weights_normal.values())
        total_high = sum(weights_high.values())
        # High entropy should produce lower total allocation
        assert total_high <= total_normal

    def test_allocate_in_drawdown(self, engine, streams):
        """Drawdown > 5% should reduce allocation."""
        for s in streams:
            engine.register_stream(s)

        state_normal = PortfolioState(drawdown=0.0)
        state_dd = PortfolioState(drawdown=0.10)

        weights_normal = engine.allocate(state_normal)
        weights_dd = engine.allocate(state_dd)

        total_normal = sum(weights_normal.values())
        total_dd = sum(weights_dd.values())
        assert total_dd <= total_normal

    def test_correlation_penalty(self, engine):
        """Highly correlated streams should get penalty."""
        s1 = AlphaStream(
            name="S1", family="F", evidence_level=EvidenceLevel.L3,
            expected_return=0.15, expected_vol=0.20,
            correlations={"S2": 0.9},  # Highly correlated
        )
        s2 = AlphaStream(
            name="S2", family="F", evidence_level=EvidenceLevel.L3,
            expected_return=0.15, expected_vol=0.20,
            correlations={"S1": 0.9},
        )
        engine.register_stream(s1)
        engine.register_stream(s2)
        # Set correlation budget low to force penalty; raise max_per_strategy to see effect
        engine.config.correlation_budget = 0.5
        engine.config.max_per_strategy = 0.50
        weights = engine.allocate()
        assert len(weights) == 2
        # Both should still have some weight, but S1 shouldn't hit the cap
        assert weights["S1"] < 0.50

    def test_evidence_multiplier(self, engine):
        """L4 should get higher allocation than L3 for equal expected returns."""
        s3 = AlphaStream(
            name="L3_Stream", family="F", evidence_level=EvidenceLevel.L3,
            expected_return=0.15, expected_vol=0.20,
        )
        s4 = AlphaStream(
            name="L4_Stream", family="F", evidence_level=EvidenceLevel.L4,
            expected_return=0.15, expected_vol=0.20,
        )
        engine.register_stream(s3)
        engine.register_stream(s4)
        # Disable risk parity for clean comparison; raise cap to see multiplier effect
        engine.config.risk_parity = False
        engine.config.max_per_strategy = 0.50
        weights = engine.allocate()
        # L4 should get higher weight than L3 (0.50 multiplier vs 0.25)
        assert weights["L4_Stream"] > weights["L3_Stream"]

    def test_half_kelly(self, engine):
        """Half-Kelly should produce smaller raw Kelly allocations."""
        stream = AlphaStream(
            name="Test", family="F", evidence_level=EvidenceLevel.L3,
            expected_return=0.20, expected_vol=0.25,
        )
        # Raw Kelly (without evidence/rebalance clipping):
        # full: f* = 0.20 / 0.0625 = 3.2 → capped 2.0 → fractional 0.25 = 0.50
        # half: 0.50 × 0.50 = 0.25
        kelly_full = stream.kelly_allocation(fraction=0.25)
        kelly_half = stream.kelly_allocation(fraction=0.125)  # Half-Kelly: 0.25 × 0.5
        assert kelly_half < kelly_full
        assert kelly_full == pytest.approx(0.50, rel=0.01)
        assert kelly_half == pytest.approx(0.25, rel=0.01)

    def test_vol_targeting(self, engine):
        """Higher target vol should allow larger allocations."""
        engine.config.target_portfolio_vol = 0.06  # Low target
        engine.register_stream(AlphaStream(
            name="Test", family="F", evidence_level=EvidenceLevel.L3,
            expected_return=0.20, expected_vol=0.25,
        ))
        engine.config.risk_parity = False
        w_low = engine.allocate()

        engine2 = AlphaEngine(EngineConfig(target_portfolio_vol=0.24))  # High target
        engine2.register_stream(AlphaStream(
            name="Test", family="F", evidence_level=EvidenceLevel.L3,
            expected_return=0.20, expected_vol=0.25,
        ))
        engine2.config.risk_parity = False
        w_high = engine2.allocate()

        assert w_high["Test"] >= w_low["Test"]

    def test_aggregate_signals(self, engine):
        """Signal aggregation should call signal functions."""
        def pos_signal():
            return (1, 0.8)

        def neg_signal():
            return (-1, 0.6)

        engine.register_stream(AlphaStream(
            name="Long", family="F", evidence_level=EvidenceLevel.L3,
            signal_fn=pos_signal,
        ))
        engine.register_stream(AlphaStream(
            name="Short", family="F", evidence_level=EvidenceLevel.L3,
            signal_fn=neg_signal,
        ))
        engine.register_stream(AlphaStream(
            name="NoSignal", family="F", evidence_level=EvidenceLevel.L3,
            signal_fn=None,
        ))

        signals = engine.aggregate_signals()
        assert len(signals) == 2  # Only the ones with signal_fn
        assert signals["Long"] == (1, 0.8)
        assert signals["Short"] == (-1, 0.6)

    def test_aggregate_signals_handles_exception(self, engine, caplog):
        """Signal function that raises should not crash the engine."""
        def broken_signal():
            raise RuntimeError("Signal computation failed")

        engine.register_stream(AlphaStream(
            name="Broken", family="F", evidence_level=EvidenceLevel.L3,
            signal_fn=broken_signal,
        ))
        signals = engine.aggregate_signals()
        assert len(signals) == 0  # Broken signal is skipped
        assert "Signal computation failed" in caplog.text

    def test_update_performance(self, engine):
        engine.register_stream(AlphaStream(
            name="Test", family="F", evidence_level=EvidenceLevel.L3,
            expected_vol=0.20, sharpe=0.0,
        ))
        engine.update_performance("Test", 0.02)
        stream = engine.get_stream("Test")
        assert stream.sharpe != 0.0

    def test_update_correlations(self, engine):
        engine.register_stream(AlphaStream(name="S1", family="F"))
        engine.register_stream(AlphaStream(name="S2", family="F"))
        engine.update_correlations({
            "S1": {"S2": 0.5},
            "S2": {"S1": 0.5},
        })
        assert engine.get_stream("S1").correlations["S2"] == 0.5

    def test_summary(self, engine, streams):
        for s in streams:
            engine.register_stream(s)
        engine.allocate()
        s = engine.summary()
        assert s["total_streams"] == 3
        assert s["active_streams"] == 3
        assert len(s["streams"]) == 3

    def test_render_summary(self, engine, streams):
        for s in streams:
            engine.register_stream(s)
        text = engine.render_summary()
        assert "Alpha Engine Summary" in text
        assert "Positioning" in text
        assert "CrossSection" in text


class TestPortfolioState:
    def test_defaults(self):
        state = PortfolioState()
        assert state.current_regime == "Neutral"
        assert state.regime_entropy == 0.0
        assert state.drawdown == 0.0
        assert state.market_vol == 0.12

    def test_custom_state(self):
        state = PortfolioState(
            current_regime="Bull",
            regime_entropy=0.3,
            drawdown=0.08,
            market_vol=0.25,
        )
        assert state.current_regime == "Bull"
        assert state.drawdown == 0.08


class TestEngineConfig:
    def test_defaults(self):
        config = EngineConfig()
        assert config.kelly_fraction == 0.25
        assert config.target_portfolio_vol == 0.12
        assert config.max_leverage == 2.0
        assert config.risk_parity is True
        assert config.evidence_weight_multipliers[EvidenceLevel.L6] == 1.0
        assert config.evidence_weight_multipliers[EvidenceLevel.L0] == 0.0

    def test_regime_scale_defaults(self):
        config = EngineConfig()
        assert config.regime_scale["Bull"] == 1.0
        assert config.regime_scale["Bear"] == 1.0
        assert config.regime_scale["Neutral"] == 1.0

# tests/test_paper_trading.py
"""Tests for Paper Trading Tracker (Stage 9)."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.core.paper_trading import (
    PaperTradingTracker,
    PaperTrade,
    DailySnapshot,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def tracker(temp_dir):
    return PaperTradingTracker(
        hypothesis_id="test_001",
        initial_equity=10_000.0,
        journal_dir=temp_dir,
    )


@pytest.fixture
def tracker_with_trades(tracker):
    """Tracker with 20 recorded trades for performance testing."""
    rng = np.random.default_rng(42)
    for i in range(20):
        # Alternate between winners and losers
        if i % 3 == 0:
            pnl = -rng.uniform(0.005, 0.02)  # loser
        else:
            pnl = rng.uniform(0.005, 0.03)   # winner
        trade = PaperTrade(
            direction=1 if i % 2 == 0 else -1,
            entry_price=50000.0 + i * 100,
            exit_price=50000.0 + i * 100 + pnl * 50000,
            entry_timestamp=f"2026-06-{i+1:02d}T10:00:00",
            exit_timestamp=f"2026-06-{i+1:02d}T14:00:00",
            pnl_pct=pnl if i % 2 == 0 else pnl,  # direction matters for sign
            pnl_absolute=pnl * 10000,
        )
        tracker.record_trade(trade)
    # Add daily snapshots
    for i in range(20):
        tracker.record_daily_snapshot(notes=f"Day {i+1}")
    return tracker


# ═══════════════════════════════════════════════════════════════════════════════
#  PaperTrade Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaperTrade:
    def test_create(self):
        trade = PaperTrade(
            direction=1,
            entry_price=50000.0,
            exit_price=51000.0,
            entry_timestamp="2026-06-26T10:00:00",
            exit_timestamp="2026-06-26T14:00:00",
            pnl_pct=0.02,
        )
        assert trade.direction == 1
        assert trade.is_winner is True
        assert trade.return_pct == 0.02

    def test_losing_trade(self):
        trade = PaperTrade(
            direction=-1,
            entry_price=50000.0,
            exit_price=51000.0,
            entry_timestamp="2026-06-26T10:00:00",
            exit_timestamp="2026-06-26T14:00:00",
            pnl_pct=-0.02,
        )
        assert trade.is_winner is False

    def test_flat_trade(self):
        trade = PaperTrade(
            direction=1,
            entry_price=50000.0,
            exit_price=50000.0,
            entry_timestamp="2026-06-26T10:00:00",
            exit_timestamp="2026-06-26T14:00:00",
            pnl_pct=0.0,
        )
        assert trade.is_winner is False


# ═══════════════════════════════════════════════════════════════════════════════
#  DailySnapshot Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDailySnapshot:
    def test_create(self):
        snap = DailySnapshot(
            date="2026-06-26",
            equity=10200.0,
            daily_pnl_pct=0.02,
            cumulative_return_pct=0.02,
            drawdown_pct=0.0,
        )
        assert snap.equity == 10200.0
        assert snap.daily_pnl_pct == 0.02


# ═══════════════════════════════════════════════════════════════════════════════
#  PaperTradingTracker Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaperTradingTracker:
    def test_create_tracker(self, tracker):
        assert tracker.hypothesis_id == "test_001"
        assert tracker.initial_equity == 10_000.0
        assert len(tracker._trades) == 0
        assert len(tracker._snapshots) == 0

    def test_start(self, tracker):
        tracker.start()
        assert tracker._started_at != ""

    def test_record_trade(self, tracker):
        trade = PaperTrade(
            direction=1,
            entry_price=50000.0,
            exit_price=51000.0,
            entry_timestamp="2026-06-26T10:00:00",
            exit_timestamp="2026-06-26T14:00:00",
            pnl_pct=0.02,
            pnl_absolute=200.0,
        )
        tracker.record_trade(trade)
        assert len(tracker._trades) == 1
        assert tracker._current_equity > 10_000.0
        assert tracker._peak_equity > 10_000.0

    def test_record_multiple_trades(self, tracker):
        for i in range(5):
            trade = PaperTrade(
                direction=1,
                entry_price=50000.0,
                exit_price=50500.0,
                entry_timestamp=f"2026-06-{i+1:02d}T10:00:00",
                exit_timestamp=f"2026-06-{i+1:02d}T14:00:00",
                pnl_pct=0.01,
                pnl_absolute=100.0,
            )
            tracker.record_trade(trade)
        assert len(tracker._trades) == 5
        # Equity should have compounded
        expected = 10000.0 * (1.01 ** 5)
        assert abs(tracker._current_equity - expected) < 1.0

    def test_record_daily_snapshot(self, tracker):
        tracker.start()
        snap = tracker.record_daily_snapshot(notes="First day")
        assert snap.date != ""
        assert snap.equity == 10000.0
        assert snap.daily_pnl_pct == 0.0
        assert len(tracker._snapshots) == 1

    def test_daily_snapshot_after_trades(self, tracker):
        tracker.start()
        # Record a winning trade
        trade = PaperTrade(
            direction=1,
            entry_price=50000.0,
            exit_price=51000.0,
            entry_timestamp="2026-06-26T10:00:00",
            exit_timestamp="2026-06-26T14:00:00",
            pnl_pct=0.02,
            pnl_absolute=200.0,
        )
        tracker.record_trade(trade)
        snap = tracker.record_daily_snapshot(notes="After win")
        assert snap.equity > 10000.0
        assert snap.cumulative_return_pct > 0.0
        assert snap.drawdown_pct == 0.0

    def test_metrics_empty(self, tracker):
        m = tracker.metrics()
        assert m["days_live"] == 0
        assert m["pf_live"] == 0.0
        assert m["n_trades"] == 0

    def test_metrics_with_data(self, tracker_with_trades):
        m = tracker_with_trades.metrics()
        assert m["days_live"] == 20
        assert m["n_trades"] == 20
        assert m["n_snapshots"] == 20
        # Should have positive PF (more winners than losers with 2:1 ratio)
        assert m["pf_live"] > 1.0

    def test_metrics_pf_calculation(self, tracker):
        # 2 winning trades, 1 losing
        tracker.record_trade(PaperTrade(
            direction=1, entry_price=50000, exit_price=51000,
            entry_timestamp="2026-06-26T10:00", exit_timestamp="2026-06-26T14:00",
            pnl_pct=0.02, pnl_absolute=200.0,
        ))
        tracker.record_trade(PaperTrade(
            direction=1, entry_price=51000, exit_price=52000,
            entry_timestamp="2026-06-27T10:00", exit_timestamp="2026-06-27T14:00",
            pnl_pct=0.02, pnl_absolute=200.0,
        ))
        tracker.record_trade(PaperTrade(
            direction=-1, entry_price=52000, exit_price=52500,
            entry_timestamp="2026-06-28T10:00", exit_timestamp="2026-06-28T14:00",
            pnl_pct=-0.01, pnl_absolute=-100.0,
        ))
        m = tracker.metrics()
        assert m["pf_live"] == 4.0  # 400/100
        assert m["win_rate_live"] == pytest.approx(2/3, abs=0.01)

    def test_is_ready_for_promotion_false(self, tracker):
        assert tracker.is_ready_for_promotion(min_days=30) is False

    def test_is_ready_for_promotion_true(self, temp_dir):
        t = PaperTradingTracker("test_promo", journal_dir=temp_dir)
        # Add 31 winning trades + snapshots
        for i in range(31):
            t.record_trade(PaperTrade(
                direction=1, entry_price=50000, exit_price=51000,
                entry_timestamp=f"2026-06-{i+1:02d}T10:00",
                exit_timestamp=f"2026-06-{i+1:02d}T14:00",
                pnl_pct=0.01, pnl_absolute=100.0,
            ))
            t.record_daily_snapshot(notes=f"Day {i+1}")
        m = t.metrics()
        assert m["days_live"] >= 31
        assert m["pf_live"] > 1.0
        assert t.is_ready_for_promotion(min_days=30) is True

    def test_sharpe_calculation(self, tracker_with_trades):
        m = tracker_with_trades.metrics()
        # Should have a valid Sharpe
        assert "sharpe_live" in m
        # Not NaN
        assert m["sharpe_live"] == m["sharpe_live"]

    def test_drawdown_tracking(self, tracker):
        tracker.start()
        # Winning trade
        tracker.record_trade(PaperTrade(
            direction=1, entry_price=50000, exit_price=51000,
            entry_timestamp="2026-06-26T10:00", exit_timestamp="2026-06-26T14:00",
            pnl_pct=0.05, pnl_absolute=500.0,
        ))
        tracker.record_daily_snapshot()
        # Losing trade
        tracker.record_trade(PaperTrade(
            direction=1, entry_price=51000, exit_price=50000,
            entry_timestamp="2026-06-27T10:00", exit_timestamp="2026-06-27T14:00",
            pnl_pct=-0.02, pnl_absolute=-200.0,
        ))
        snap = tracker.record_daily_snapshot()
        assert snap.drawdown_pct < 0.0  # negative drawdown

    def test_equity_curve(self, tracker_with_trades):
        curve = tracker_with_trades.equity_curve()
        assert len(curve) == 20
        assert "date" in curve[0]
        assert "equity" in curve[0]

    def test_daily_returns(self, tracker_with_trades):
        returns = tracker_with_trades.daily_returns()
        assert len(returns) == 20
        assert isinstance(returns, np.ndarray)

    def test_summary(self, tracker_with_trades):
        s = tracker_with_trades.summary()
        assert s["hypothesis_id"] == "test_001"
        assert s["n_trades"] == 20
        assert s["current_equity"] > 0

    def test_render_summary(self, tracker_with_trades):
        text = tracker_with_trades.render_summary()
        assert "test_001" in text
        assert "PF" in text

    def test_persistence(self, temp_dir):
        t1 = PaperTradingTracker("persist_test", journal_dir=temp_dir)
        t1.start()
        t1.record_trade(PaperTrade(
            direction=1, entry_price=50000, exit_price=51000,
            entry_timestamp="2026-06-26T10:00", exit_timestamp="2026-06-26T14:00",
            pnl_pct=0.02, pnl_absolute=200.0,
        ))
        t1.record_daily_snapshot()

        # Load from disk
        t2 = PaperTradingTracker("persist_test", journal_dir=temp_dir)
        assert len(t2._trades) == 1
        assert len(t2._snapshots) == 1
        m = t2.metrics()
        assert m["n_trades"] == 1

    def test_update_hypothesis_metrics(self, tracker_with_trades):
        from src.core.evidence_ladder import HypothesisRecord

        record = HypothesisRecord(
            hypothesis_id="test_001",
            name="Test",
            family="TestFamily",
        )
        tracker_with_trades.update_hypothesis_metrics(record)
        assert "paper_trading" in record.metrics
        pt = record.metrics["paper_trading"]
        assert pt["days_live"] == 20
        assert pt["n_trades"] == 20
        assert pt["pf_live"] > 0

    def test_journal_logging(self, tracker, temp_dir):
        """Verify that trades are written to the JSONL journal."""
        tracker.record_trade(PaperTrade(
            direction=1, entry_price=50000, exit_price=51000,
            entry_timestamp="2026-06-26T10:00", exit_timestamp="2026-06-26T14:00",
            pnl_pct=0.02, pnl_absolute=200.0,
        ))
        journal_path = Path(temp_dir) / "test_001_trades.jsonl"
        assert journal_path.exists()
        with open(journal_path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["direction"] == 1
        assert data["pnl_pct"] == 0.02

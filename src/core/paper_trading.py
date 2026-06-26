# src/core/paper_trading.py
"""
Paper Trading Tracker — Stage 9 monitoring skeleton (Roadmap v2).

Tracks live paper trading performance for hypotheses that have passed
Stages 1-8. Provides the metrics collection and monitoring infrastructure
needed to evaluate whether a hypothesis survives live market conditions.

Design
------
- Each paper-traded strategy logs daily state to JSONL.
- Metrics are computed on-the-fly from the journal.
- A tracker instance monitors one hypothesis; multiple trackers can run
  concurrently for different streams.
- The tracker integrates with EvidenceLadder: when ``min_paper_trading_days``
  is reached with PF > 1.0, the hypothesis can be promoted to L5.

Usage
-----
    from src.core.paper_trading import PaperTradingTracker, PaperTrade

    tracker = PaperTradingTracker(hypothesis_id="pos_001")
    tracker.record_trade(PaperTrade(direction=1, entry_price=50000, ...))
    tracker.record_daily_pnl(timestamp="2026-06-26", pnl_pct=0.015)
    metrics = tracker.metrics()
    # metrics = {"days_live": 31, "pf_live": 1.35, "sharpe_live": 0.82, ...}
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PaperTrade:
    """A single paper trade recorded by the tracker."""
    direction: int               # +1 long, -1 short
    entry_price: float
    exit_price: float
    entry_timestamp: str
    exit_timestamp: str
    pnl_pct: float               # Profit/loss as fraction of notional
    pnl_absolute: float = 0.0
    strategy_id: str = ""
    notes: str = ""

    @property
    def is_winner(self) -> bool:
        return self.pnl_pct > 0

    @property
    def return_pct(self) -> float:
        """Return as signed fraction (e.g., 0.02 = 2% gain)."""
        return self.pnl_pct


@dataclass
class DailySnapshot:
    """End-of-day snapshot for a paper-traded strategy."""
    date: str
    equity: float                # Current simulated equity
    daily_pnl_pct: float         # Day's P&L as fraction
    cumulative_return_pct: float # Cumulative return from start
    drawdown_pct: float          # Drawdown from peak equity
    n_open_positions: int = 0
    n_closed_trades_today: int = 0
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
#  Paper Trading Tracker
# ═══════════════════════════════════════════════════════════════════════════════

class PaperTradingTracker:
    """
    Tracks paper trading performance for one hypothesis.

    Maintains a trade journal and daily equity snapshots. Can compute
    live performance metrics at any time for Stage 9 evaluation.

    Parameters
    ----------
    hypothesis_id : str
        The hypothesis being paper-traded.
    initial_equity : float
        Starting simulated equity.
    journal_dir : str
        Directory for paper trading journal files.
    """

    DEFAULT_JOURNAL_DIR = "data/journal/paper_trading"

    def __init__(
        self,
        hypothesis_id: str,
        initial_equity: float = 10_000.0,
        journal_dir: Optional[str] = None,
    ) -> None:
        self.hypothesis_id = hypothesis_id
        self.initial_equity = initial_equity
        self.journal_dir = Path(journal_dir or self.DEFAULT_JOURNAL_DIR)
        self.journal_dir.mkdir(parents=True, exist_ok=True)

        self._trades: List[PaperTrade] = []
        self._snapshots: List[DailySnapshot] = []
        self._peak_equity: float = initial_equity
        self._current_equity: float = initial_equity
        self._started_at: str = ""

        # Load existing state if available
        self._load_state()

    # ── State persistence ─────────────────────────────────────────────────────

    @property
    def _state_path(self) -> Path:
        return self.journal_dir / f"{self.hypothesis_id}_paper_trading.json"

    @property
    def _journal_path(self) -> Path:
        return self.journal_dir / f"{self.hypothesis_id}_trades.jsonl"

    def _load_state(self) -> None:
        """Load persisted tracker state from disk."""
        if self._state_path.exists():
            try:
                with open(self._state_path) as fh:
                    data = json.load(fh)
                self._peak_equity = data.get("peak_equity", self.initial_equity)
                self._current_equity = data.get("current_equity", self.initial_equity)
                self._started_at = data.get("started_at", "")
                self._snapshots = [
                    DailySnapshot(**s) for s in data.get("snapshots", [])
                ]
                self._trades = [
                    PaperTrade(**t) for t in data.get("trades", [])
                ]
                logger.info(
                    "Loaded paper trading state for %s: %d trades, %d daily snapshots.",
                    self.hypothesis_id, len(self._trades), len(self._snapshots),
                )
            except Exception as exc:
                logger.warning("Failed to load paper trading state: %s", exc)

    def _save_state(self) -> None:
        """Persist current tracker state to disk."""
        data = {
            "hypothesis_id": self.hypothesis_id,
            "initial_equity": self.initial_equity,
            "peak_equity": self._peak_equity,
            "current_equity": self._current_equity,
            "started_at": self._started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "snapshots": [asdict(s) for s in self._snapshots],
            "trades": [asdict(t) for t in self._trades],
        }
        with open(self._state_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def _append_trade_journal(self, trade: PaperTrade) -> None:
        """Append a trade to the JSONL journal."""
        with open(self._journal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(trade), ensure_ascii=False) + "\n")

    # ── Core tracking ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Mark the start of paper trading."""
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._save_state()
        logger.info(
            "Paper trading STARTED for %s at %s",
            self.hypothesis_id, self._started_at,
        )

    def record_trade(self, trade: PaperTrade) -> None:
        """
        Record a completed paper trade.

        Updates equity and peak tracking, appends to journal.
        """
        self._trades.append(trade)
        self._append_trade_journal(trade)
        self._current_equity *= (1.0 + trade.pnl_pct)
        self._peak_equity = max(self._peak_equity, self._current_equity)
        logger.debug(
            "Paper trade recorded for %s: %s %s, PnL=%.4f%%",
            self.hypothesis_id,
            "LONG" if trade.direction > 0 else "SHORT",
            "WIN" if trade.is_winner else "LOSS",
            trade.pnl_pct * 100,
        )

    def record_daily_snapshot(
        self,
        notes: str = "",
        n_open_positions: int = 0,
        n_closed_trades_today: int = 0,
    ) -> DailySnapshot:
        """
        Record an end-of-day snapshot.

        Computes daily P&L, cumulative return, and current drawdown.
        """
        prev_equity = self._current_equity
        if self._snapshots:
            prev_equity = self._snapshots[-1].equity

        daily_pnl = 0.0
        if prev_equity > 0:
            daily_pnl = (self._current_equity - prev_equity) / prev_equity

        cumulative_return = 0.0
        if self.initial_equity > 0:
            cumulative_return = (
                self._current_equity - self.initial_equity
            ) / self.initial_equity

        drawdown = 0.0
        if self._peak_equity > 0:
            drawdown = (self._current_equity - self._peak_equity) / self._peak_equity

        snapshot = DailySnapshot(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            equity=self._current_equity,
            daily_pnl_pct=round(daily_pnl, 6),
            cumulative_return_pct=round(cumulative_return, 6),
            drawdown_pct=round(drawdown, 6),
            n_open_positions=n_open_positions,
            n_closed_trades_today=n_closed_trades_today,
            notes=notes,
        )
        self._snapshots.append(snapshot)
        self._save_state()
        return snapshot

    # ── Metrics computation ───────────────────────────────────────────────────

    def metrics(self) -> Dict[str, Any]:
        """
        Compute live paper trading performance metrics.

        Returns a dict suitable for Stage 9 evaluation:
        {days_live, pf_live, sharpe_live, win_rate_live, total_return_pct,
         max_drawdown_pct, n_trades, n_snapshots}
        """
        n_snapshots = len(self._snapshots)
        days_live = n_snapshots if n_snapshots > 0 else 0

        # Profit factor: gross profit / gross loss
        gross_profit = sum(t.pnl_absolute for t in self._trades if t.pnl_absolute > 0)
        gross_loss = abs(sum(t.pnl_absolute for t in self._trades if t.pnl_absolute < 0))
        pf_live = gross_profit / max(gross_loss, 1e-9)

        # Win rate
        n_winners = sum(1 for t in self._trades if t.is_winner)
        n_total = len(self._trades)
        win_rate = n_winners / max(n_total, 1)

        # Sharpe (from daily snapshots)
        sharpe = 0.0
        if len(self._snapshots) >= 5:
            daily_returns = np.array([
                s.daily_pnl_pct for s in self._snapshots
            ])
            mean_ret = float(np.mean(daily_returns))
            std_ret = float(np.std(daily_returns, ddof=1))
            if std_ret > 0:
                sharpe = (mean_ret / std_ret) * np.sqrt(365)  # Annualized

        # Total return and max drawdown
        total_return = 0.0
        max_dd = 0.0
        if self.initial_equity > 0:
            total_return = (
                self._current_equity - self.initial_equity
            ) / self.initial_equity
        if self._snapshots:
            max_dd = min(s.drawdown_pct for s in self._snapshots)

        return {
            "days_live": days_live,
            "pf_live": round(pf_live, 4),
            "sharpe_live": round(sharpe, 4),
            "win_rate_live": round(win_rate, 4),
            "total_return_pct": round(total_return * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "n_trades": n_total,
            "n_snapshots": n_snapshots,
            "started_at": self._started_at,
        }

    def is_ready_for_promotion(self, min_days: int = 30) -> bool:
        """
        Check if the strategy meets Stage 9 promotion criteria.

        Requires: >= min_days live AND PF > 1.0.
        """
        m = self.metrics()
        return m["days_live"] >= min_days and m["pf_live"] > 1.0

    # ── Dashboard / reporting ─────────────────────────────────────────────────

    def daily_returns(self) -> np.ndarray:
        """Return array of daily P&L percentages for further analysis."""
        return np.array([s.daily_pnl_pct for s in self._snapshots])

    def equity_curve(self) -> List[Dict[str, Any]]:
        """Return the equity curve as a list of {date, equity} dicts."""
        return [
            {"date": s.date, "equity": round(s.equity, 2)}
            for s in self._snapshots
        ]

    def summary(self) -> Dict[str, Any]:
        """Return a structured summary for dashboards."""
        m = self.metrics()
        return {
            "hypothesis_id": self.hypothesis_id,
            **m,
            "n_trades": len(self._trades),
            "current_equity": round(self._current_equity, 2),
            "peak_equity": round(self._peak_equity, 2),
        }

    def render_summary(self) -> str:
        """Human-readable summary string."""
        m = self.metrics()
        lines = [
            "═══ Paper Trading Summary ═══",
            f"  Hypothesis:       {self.hypothesis_id}",
            f"  Days live:        {m['days_live']}",
            f"  Trades:           {m['n_trades']}",
            f"  PF (live):        {m['pf_live']:.3f}",
            f"  Sharpe (live):    {m['sharpe_live']:.3f}",
            f"  Win rate (live):  {m['win_rate_live']:.2%}",
            f"  Total return:     {m['total_return_pct']:.2f}%",
            f"  Max drawdown:     {m['max_drawdown_pct']:.2f}%",
            f"  Current equity:   {self._current_equity:,.2f}",
            f"  Peak equity:      {self._peak_equity:,.2f}",
            f"  Started:          {m['started_at'][:19] if m['started_at'] else 'N/A'}",
        ]
        return "\n".join(lines)

    # ── Integration with Evidence Ladder ──────────────────────────────────────

    def update_hypothesis_metrics(self, record: Any) -> None:
        """
        Update a HypothesisRecord's paper_trading metrics from this tracker.

        Parameters
        ----------
        record : HypothesisRecord
            The hypothesis record to update (mutated in-place).
        """
        m = self.metrics()
        record.metrics["paper_trading"] = {
            "days_live": m["days_live"],
            "pf_live": m["pf_live"],
            "sharpe_live": m["sharpe_live"],
            "win_rate_live": m["win_rate_live"],
            "n_trades": m["n_trades"],
            "started_at": m["started_at"],
        }
        record.updated_at = datetime.now(timezone.utc).isoformat()


__all__ = [
    "PaperTradingTracker",
    "PaperTrade",
    "DailySnapshot",
]

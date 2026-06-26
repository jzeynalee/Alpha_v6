# src/backtest/result.py
"""
BacktestResult — the structured outcome of a backtest run.

Trade-level analytics (win rate, profit factor, Sharpe, expectancy, max
drawdown, MAE/MFE, duration) are NOT re-implemented here: they are computed by
the production TradeJournal, the same code that analyses live trades. This
module adds only what the journal does not have — an equity-curve view and a
few curve-derived metrics (return, equity-curve max drawdown, exposure) — and
bundles everything into one object with convenient summary / export methods.

Reusing the journal keeps backtest metrics and live metrics definitionally
identical: a strategy cannot look good in backtest and bad live merely
because the two used different formulas.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .portfolio import EquityPoint

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """
    Everything produced by one BacktestEngine.run().

    Attributes
    ----------
    symbol         : the instrument backtested.
    initial_cash   : starting equity.
    final_equity   : equity at the last bar.
    equity_curve   : list of EquityPoint samples (one per bar).
    journal_report : TradeJournal.analytics_report() dict — the authoritative
                     trade-level metrics.
    bars_processed : number of bars the engine walked.
    bars_in_market : number of bars during which a position was open.
    config         : the BacktestConfig used, as a dict (for reproducibility).
    """
    symbol:         str
    initial_cash:   float
    final_equity:   float
    equity_curve:   List[EquityPoint]
    journal_report: Dict
    bars_processed: int
    bars_in_market: int
    config:         Dict = field(default_factory=dict)

    # ─── Curve-derived metrics (not available from the journal) ───────────────

    @property
    def total_return_pct(self) -> float:
        """Total return over the run, in percent of initial cash."""
        return (self.final_equity / self.initial_cash - 1.0) * 100.0

    @property
    def equity_max_drawdown_pct(self) -> float:
        """
        Worst peak-to-trough decline of the *equity curve*, in percent.

        This is the mark-to-market drawdown an account would actually have
        experienced — distinct from the journal's trade-PnL drawdown, which
        only updates on closes.
        """
        peak = -math.inf
        worst = 0.0
        for pt in self.equity_curve:
            peak = max(peak, pt.equity)
            if peak > 0:
                dd = (pt.equity - peak) / peak
                worst = min(worst, dd)
        return worst * 100.0

    @property
    def exposure_pct(self) -> float:
        """Fraction of bars spent holding a position, in percent."""
        if self.bars_processed == 0:
            return 0.0
        return self.bars_in_market / self.bars_processed * 100.0

    @property
    def closed_trades(self) -> int:
        return int(self.journal_report.get("closed_trades", 0))

    @property
    def win_rate(self) -> float:
        return float(self.journal_report.get("overall", {}).get("win_rate", 0.0))

    @property
    def profit_factor(self) -> float:
        return float(self.journal_report.get("overall", {}).get("profit_factor", 0.0))

    @property
    def sharpe(self) -> float:
        return float(self.journal_report.get("overall", {}).get("sharpe", 0.0))

    # ─── Views / export ───────────────────────────────────────────────────────

    def equity_curve_df(self) -> pd.DataFrame:
        """The equity curve as a DataFrame (timestamp, equity, cash, position)."""
        return pd.DataFrame(
            [
                {
                    "bar_index": p.bar_index,
                    "timestamp": p.timestamp,
                    "equity":    p.equity,
                    "cash":      p.cash,
                    "position":  p.position,
                }
                for p in self.equity_curve
            ]
        )

    def summary(self) -> Dict:
        """A compact, flat dict of the headline numbers."""
        ov = self.journal_report.get("overall", {})
        return {
            "symbol":                 self.symbol,
            "initial_cash":           round(self.initial_cash, 2),
            "final_equity":           round(self.final_equity, 2),
            "total_return_pct":       round(self.total_return_pct, 4),
            "equity_max_drawdown_pct": round(self.equity_max_drawdown_pct, 4),
            "exposure_pct":           round(self.exposure_pct, 2),
            "bars_processed":         self.bars_processed,
            "closed_trades":          self.closed_trades,
            "win_rate":               round(self.win_rate, 4),
            "profit_factor":          round(float(ov.get("profit_factor", 0.0)), 4),
            "sharpe":                 round(float(ov.get("sharpe", 0.0)), 4),
            "expectancy":             round(float(ov.get("expectancy", 0.0)), 4),
            "trade_max_drawdown":     round(float(ov.get("max_drawdown", 0.0)), 4),
        }

    def render(self) -> str:
        """A human-readable multi-line summary, suitable for logging/printing."""
        s = self.summary()
        lines = [
            "═══════════════════════════════════════════════",
            f" Backtest result — {s['symbol']}",
            "═══════════════════════════════════════════════",
            f"  Initial cash        : {s['initial_cash']:>14,.2f}",
            f"  Final equity        : {s['final_equity']:>14,.2f}",
            f"  Total return        : {s['total_return_pct']:>13.2f}%",
            f"  Equity max drawdown : {s['equity_max_drawdown_pct']:>13.2f}%",
            f"  Exposure            : {s['exposure_pct']:>13.2f}%",
            "  ---------------------------------------------",
            f"  Bars processed      : {s['bars_processed']:>14,}",
            f"  Closed trades       : {s['closed_trades']:>14,}",
            f"  Win rate            : {s['win_rate'] * 100:>13.2f}%",
            f"  Profit factor       : {s['profit_factor']:>14.3f}",
            f"  Sharpe              : {s['sharpe']:>14.3f}",
            f"  Expectancy          : {s['expectancy']:>14.4f}",
            "═══════════════════════════════════════════════",
        ]
        return "\n".join(lines)

    def to_json(self, path: Optional[Path] = None) -> Dict:
        """
        Return the full result as a JSON-serialisable dict; if ``path`` is
        given, also write it there.
        """
        payload = {
            "summary":        self.summary(),
            "config":         self.config,
            "journal_report": self.journal_report,
            "equity_curve":   self.equity_curve_df().to_dict(orient="records"),
        }
        if path is not None:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as fh:
                json.dump(payload, fh, indent=2, default=str)
            logger.info("Backtest result written → %s", path)
        return payload


__all__ = ["BacktestResult"]

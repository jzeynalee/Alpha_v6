# src/backtest/portfolio.py
"""
Simulated portfolio accounting for the backtester.

This is the one piece of the backtester that genuinely *must* be simulated:
there is no exchange, so cash, equity, and the open position have to be
tracked here. Everything else (sizing, SL/TP, exposure limits, PnL metrics)
reuses the production RiskManager and TradeJournal.

Model
-----
Single-symbol, single-position, long/short, cash-settled:

  * equity        = cash + unrealised PnL of the open position
  * a position is opened with `units` at `entry_price`; opening deducts the
    notional and the entry fee from cash
  * closing credits the notional back, applies the exit fee, and realises PnL
  * only one position open at a time (the engine enforces this)

Fees and slippage are applied by the engine when it computes fill prices;
the portfolio just records whatever fill price it is given.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class OpenPosition:
    """The single currently-open position, if any."""
    symbol:      str
    direction:   int          # +1 long, -1 short
    units:       float
    entry_price: float
    entry_fee:   float
    stop_loss:   float
    take_profit: float
    bar_index:   int          # bar at which the position was opened
    trade_id:    str = ""     # TradeJournal id, filled in by the engine
    strategy_id: str = "backtest"
    regime:      str = "Neutral"
    risk_notional: float = 0.0  # notional as the RiskManager sized it

    @property
    def notional(self) -> float:
        return self.units * self.entry_price

    def unrealised_pnl(self, mark_price: float) -> float:
        """Mark-to-market PnL at ``mark_price`` (before exit fees)."""
        return self.direction * (mark_price - self.entry_price) * self.units


@dataclass
class EquityPoint:
    """One sample on the equity curve."""
    bar_index: int
    timestamp: int
    equity:    float
    cash:      float
    position:  int            # -1 / 0 / +1


@dataclass
class Portfolio:
    """
    Mutable simulated portfolio.

    Parameters
    ----------
    initial_cash : starting cash balance (quote currency).
    """
    initial_cash: float
    cash:         float = field(init=False)
    position:     Optional[OpenPosition] = field(default=None, init=False)
    equity_curve: List[EquityPoint] = field(default_factory=list, init=False)
    realised_pnl: float = field(default=0.0, init=False)
    fees_paid:    float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.cash = float(self.initial_cash)

    # ─── State queries ────────────────────────────────────────────────────────

    @property
    def has_position(self) -> bool:
        return self.position is not None

    def equity(self, mark_price: float) -> float:
        """Total equity = cash + unrealised PnL of the open position."""
        if self.position is None:
            return self.cash
        return self.cash + self.position.unrealised_pnl(mark_price)

    # ─── Mutations ────────────────────────────────────────────────────────────

    def open(self, pos: OpenPosition) -> None:
        """
        Open a position. Deducts the entry fee from cash.

        Note on cash model: this is a cash-settled / margin-style simulation —
        opening does NOT lock the full notional out of `cash` (that would
        prevent shorts and over-state drawdown for leveraged sizing). Only the
        fee is a real cash outflow at open; PnL is realised on close. Equity
        therefore moves with the mark price via unrealised_pnl().
        """
        if self.position is not None:
            raise RuntimeError("Portfolio.open called while a position is open")
        self.cash -= pos.entry_fee
        self.fees_paid += pos.entry_fee
        self.position = pos

    def close(self, exit_price: float, exit_fee: float) -> Tuple[float, float]:
        """
        Close the open position at ``exit_price``.

        Returns
        -------
        (realised_pnl, pnl_pct) where pnl_pct is PnL / entry-notional.
        """
        if self.position is None:
            raise RuntimeError("Portfolio.close called with no open position")
        pos = self.position
        gross = pos.unrealised_pnl(exit_price)
        pnl = gross - exit_fee
        self.cash += pnl
        self.realised_pnl += pnl
        self.fees_paid += exit_fee
        pnl_pct = pnl / max(pos.notional, 1e-9)
        self.position = None
        return pnl, pnl_pct

    # ─── Equity curve ─────────────────────────────────────────────────────────

    def mark(self, bar_index: int, timestamp: int, mark_price: float) -> None:
        """Append one sample to the equity curve."""
        self.equity_curve.append(EquityPoint(
            bar_index=bar_index,
            timestamp=int(timestamp),
            equity=self.equity(mark_price),
            cash=self.cash,
            position=(self.position.direction if self.position else 0),
        ))


__all__ = ["Portfolio", "OpenPosition", "EquityPoint"]

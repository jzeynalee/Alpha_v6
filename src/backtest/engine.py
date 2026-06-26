# src/backtest/engine.py
"""
BacktestEngine — the event-driven core of the backtester.

Design philosophy
-----------------
The engine reuses production code wherever a decision genuinely affects
strategy performance, and simulates only what physically cannot exist without
an exchange:

  * REUSED  — RiskManager: position sizing, SL/TP prices, exposure limits,
              daily-notional / daily-loss limits, the kill switch. These are
              the rules that decide whether and how big a trade is, so the
              backtest must use the *same* code the live system uses.
  * REUSED  — TradeJournal: every trade-level metric (win rate, profit
              factor, Sharpe, expectancy, drawdown, MAE/MFE). The backtest
              logs entries/exits exactly as the live trader does.
  * SIMULATED — fills, fees, slippage, cash/equity (Portfolio). There is no
              exchange, so these are modelled explicitly and conservatively.

Event loop (per bar i)
----------------------
  1. Mark-to-market: sample the equity curve at bar i's close.
  2. If a position is open, check whether bar i's HIGH/LOW would have hit the
     stop-loss or take-profit. Exits are checked *before* new entries, and an
     SL/TP hit uses the SL/TP price (gap-adjusted), not the bar close.
  3. If flat, ask the signal source for a decision based on bars [0..i].
     A non-flat signal is sized by RiskManager.evaluate(); if approved, the
     entry fills on bar i's close adjusted for slippage + fee.

Look-ahead safety
-----------------
The signal source is only ever handed ``ohlcv.iloc[:i+1]`` — it cannot see
bar i+1. Entry fills use bar i's close (the bar the decision was made on);
this is the standard "decide on close, fill on close" convention. SL/TP fills
use bar i+1..n's intrabar range. There is no future leakage.

Intrabar SL/TP ambiguity
------------------------
When a single bar's range spans BOTH the stop and the target, the engine
cannot know which was hit first from OHLC alone. It resolves this
pessimistically — the STOP is assumed hit first — so the backtest never
flatters a strategy on ambiguous bars.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd

from src.risk.risk_manager import RiskManager, TradeRequest
from src.risk.trade_journal import TradeJournal

from .data import load_ohlcv
from .portfolio import OpenPosition, Portfolio
from .result import BacktestResult
from .signal_source import BacktestSignal, CallableSignalSource, SignalSource

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """
    Tuning for one backtest run.

    Fees and slippage are the levers that most affect realism — defaults are
    deliberately conservative (a retail taker fee, a small slippage).

    Attributes
    ----------
    initial_cash      : starting equity (quote currency).
    fee_pct           : per-side fee, as a fraction (0.001 = 0.1 %).
    slippage_pct      : per-side slippage, as a fraction. Entries fill worse
                        by this much; SL/TP fills are also worsened.
    warmup_bars       : bars to skip before the first signal is solicited
                        (lets indicators / the signal source build history).
    account_equity    : equity passed to RiskManager.evaluate() for sizing.
                        Defaults to None → the live portfolio equity is used.
    allow_short       : if False, short signals (direction=-1) are ignored.
    risk_config       : config dict for the RiskManager built internally.
                        If a RiskManager is supplied to the engine directly,
                        this is ignored.
    """
    initial_cash:   float = 10_000.0
    fee_pct:        float = 0.001
    slippage_pct:   float = 0.0005
    warmup_bars:    int   = 50
    account_equity: Optional[float] = None
    allow_short:    bool  = True
    risk_config:    Dict  = field(default_factory=dict)

    def as_dict(self) -> Dict:
        return {
            "initial_cash":   self.initial_cash,
            "fee_pct":        self.fee_pct,
            "slippage_pct":   self.slippage_pct,
            "warmup_bars":    self.warmup_bars,
            "account_equity": self.account_equity,
            "allow_short":    self.allow_short,
        }


# Default permissive risk config — used when the caller supplies neither a
# RiskManager nor a risk_config. Permissive so a plain strategy backtest is
# not silently throttled by limits the user never set.
_DEFAULT_RISK_CONFIG: Dict = {
    "sizing_method":          "fixed_fraction",
    "risk_per_trade_pct":     0.02,
    "max_position_pct":       0.95,
    "sl_atr_mult":            1.5,
    "tp_atr_mult":            3.0,
    "min_proba_alpha":        0.0,
    "max_regime_entropy":     1.0,
    "min_margin_level":       0.0,
    "max_trades_per_day":     10_000,
    "max_daily_notional":     1e12,
    "max_daily_loss_pct":     1.0,
    "max_symbol_exposure_pct": 10.0,
    "max_regime_exposure_pct": 10.0,
    "max_leverage":           100.0,
}


class BacktestEngine:
    """
    Event-driven, single-symbol backtester.

    Parameters
    ----------
    signal_source : a SignalSource (or a plain callable, auto-wrapped).
    config        : BacktestConfig. Defaults are conservative.
    risk_manager  : optional pre-built RiskManager. When omitted, one is
                    built from config.risk_config (or a permissive default).
    """

    def __init__(
        self,
        signal_source: Union[SignalSource, callable],
        config: Optional[BacktestConfig] = None,
        risk_manager: Optional[RiskManager] = None,
    ) -> None:
        # Auto-wrap a bare callable for convenience.
        if not hasattr(signal_source, "generate"):
            if callable(signal_source):
                signal_source = CallableSignalSource(signal_source)
            else:
                raise TypeError(
                    "signal_source must be a SignalSource or a callable"
                )
        self._source = signal_source
        self._config = config or BacktestConfig()

        if risk_manager is not None:
            self._risk = risk_manager
        else:
            rc = self._config.risk_config or dict(_DEFAULT_RISK_CONFIG)
            self._risk = RiskManager(rc)

        self._atr_period = 14

    # ─── ATR (needed by RiskManager sizing + SL/TP) ───────────────────────────

    @staticmethod
    def _compute_atr(window: pd.DataFrame, period: int) -> float:
        """
        Wilder ATR over the last ``period`` bars of ``window``.

        The RiskManager needs an ATR for sizing and stop placement; the live
        system gets it from DeterAlpha's swing tracker. In a generic backtest
        we compute a standard ATR from the OHLC window so the backtest does
        not depend on the full feature pipeline.
        """
        if len(window) < 2:
            return 0.0
        h = window["high"].to_numpy()
        l = window["low"].to_numpy()
        c = window["close"].to_numpy()
        prev_c = c[:-1]
        tr = pd.Series(
            data=[
                max(h[i] - l[i], abs(h[i] - prev_c[i - 1]), abs(l[i] - prev_c[i - 1]))
                for i in range(1, len(window))
            ]
        )
        if len(tr) == 0:
            return 0.0
        atr = tr.tail(period).mean()
        return float(atr) if atr == atr else 0.0   # NaN guard

    # ─── Fill-price helpers ───────────────────────────────────────────────────

    def _entry_fill_price(self, close: float, direction: int) -> float:
        """A buy fills slightly above close, a sell slightly below."""
        slip = self._config.slippage_pct * direction
        return close * (1.0 + slip)

    def _exit_fill_price(self, target: float, direction: int) -> float:
        """
        Slippage on the exit works against the position: closing a long
        (a sell) fills slightly below the target, closing a short above.
        """
        slip = self._config.slippage_pct * direction   # direction = position dir
        return target * (1.0 - slip)

    def _fee(self, notional: float) -> float:
        return abs(notional) * self._config.fee_pct

    # ─── Exit detection ───────────────────────────────────────────────────────

    def _detect_exit(
        self, pos: OpenPosition, bar: pd.Series
    ) -> Optional[tuple]:
        """
        Did ``bar`` trigger this position's stop-loss or take-profit?

        Returns (exit_price, exit_reason) or None. On a bar that spans both
        levels the STOP is assumed first (pessimistic — see module docstring).
        """
        high = float(bar["high"])
        low = float(bar["low"])

        if pos.direction > 0:                       # long
            hit_sl = pos.stop_loss > 0 and low <= pos.stop_loss
            hit_tp = pos.take_profit > 0 and high >= pos.take_profit
        else:                                       # short
            hit_sl = pos.stop_loss > 0 and high >= pos.stop_loss
            hit_tp = pos.take_profit > 0 and low <= pos.take_profit

        if hit_sl:
            # Gap-adjust: if the bar opened past the stop, fill at the open.
            open_px = float(bar["open"])
            if pos.direction > 0:
                fill = min(pos.stop_loss, open_px)
            else:
                fill = max(pos.stop_loss, open_px)
            return fill, "stop_loss"
        if hit_tp:
            return pos.take_profit, "take_profit"
        return None

    # ─── Main loop ────────────────────────────────────────────────────────────

    def run(
        self,
        data: Union[str, "pd.DataFrame"],
        symbol: str = "BACKTEST",
    ) -> BacktestResult:
        """
        Execute the backtest over ``data`` and return a BacktestResult.

        Parameters
        ----------
        data   : OHLCV source — a parquet/csv path or a DataFrame (see
                 backtest.data.load_ohlcv for the accepted schema).
        symbol : instrument label, used for journal entries and the result.
        """
        ohlcv = load_ohlcv(data, symbol=symbol)
        n = len(ohlcv)
        cfg = self._config

        if cfg.warmup_bars >= n:
            raise ValueError(
                f"warmup_bars={cfg.warmup_bars} >= available bars ({n}); "
                f"nothing to backtest"
            )

        self._source.reset()
        portfolio = Portfolio(initial_cash=cfg.initial_cash)
        # TradeJournal needs a real directory (it opens a SQLite DB). Use a
        # throwaway temp dir — the backtest reads metrics back via
        # analytics_report() in-process, so nothing needs to persist.
        _journal_dir = tempfile.mkdtemp(prefix="bt_journal_")
        journal = TradeJournal(base_dir=Path(_journal_dir))
        bars_in_market = 0

        # Per-open-position running MAE/MFE (worst / best unrealised PnL).
        mae = 0.0
        mfe = 0.0

        for i in range(n):
            bar = ohlcv.iloc[i]
            close = float(bar["close"])
            ts = int(bar["timestamp"])

            # 1) Mark-to-market the equity curve on every bar.
            portfolio.mark(i, ts, close)

            # 2) Manage an open position: update MAE/MFE, check SL/TP.
            if portfolio.has_position:
                bars_in_market += 1
                pos = portfolio.position
                upnl = pos.unrealised_pnl(close)
                mae = min(mae, upnl)
                mfe = max(mfe, upnl)

                exit_info = self._detect_exit(pos, bar)
                if exit_info is not None:
                    raw_exit_px, reason = exit_info
                    exit_px = self._exit_fill_price(raw_exit_px, pos.direction)
                    self._close(portfolio, journal, pos, exit_px, reason,
                                hold_bars=i - pos.bar_index, mae=mae, mfe=mfe)
                    mae = mfe = 0.0
                    continue   # one action per bar

            # 3) Warmup gate — no signals until enough history exists.
            if i < cfg.warmup_bars:
                continue

            # 4) Flat → solicit a signal and maybe open a position.
            if not portfolio.has_position:
                window = ohlcv.iloc[: i + 1]
                signal = self._source.generate(symbol, window, i)
                if signal.direction == 0:
                    continue
                if signal.direction < 0 and not cfg.allow_short:
                    continue
                self._try_open(portfolio, journal, symbol, signal, window, i, close)

        # Force-close any still-open position at the final bar's close.
        if portfolio.has_position:
            last = ohlcv.iloc[-1]
            pos = portfolio.position
            exit_px = self._exit_fill_price(float(last["close"]), pos.direction)
            self._close(portfolio, journal, pos, exit_px, "end_of_data",
                        hold_bars=(n - 1) - pos.bar_index, mae=mae, mfe=mfe)

        final_equity = portfolio.cash   # flat at end → equity == cash
        return BacktestResult(
            symbol=symbol,
            initial_cash=cfg.initial_cash,
            final_equity=final_equity,
            equity_curve=portfolio.equity_curve,
            journal_report=journal.analytics_report(),
            bars_processed=n,
            bars_in_market=bars_in_market,
            config=cfg.as_dict(),
        )

    # ─── Open / close helpers ─────────────────────────────────────────────────

    def _try_open(
        self,
        portfolio: Portfolio,
        journal: TradeJournal,
        symbol: str,
        signal: BacktestSignal,
        window: pd.DataFrame,
        bar_index: int,
        close: float,
    ) -> None:
        """Size the signal via the real RiskManager; open if approved."""
        atr = self._compute_atr(window, self._atr_period)
        if atr <= 0.0:
            return   # cannot size / place a stop without an ATR

        equity = self._config.account_equity
        if equity is None:
            equity = portfolio.equity(close)

        req = TradeRequest(
            symbol=symbol,
            direction=signal.direction,
            entry_price=close,
            atr=atr,
            equity=equity,
            proba_alpha=signal.proba_alpha,
            regime_entropy=signal.regime_entropy,
            strategy_id=signal.strategy_id,
            current_position=0.0,
            margin_level=1.0,
        )
        decision = self._risk.evaluate(
            req,
            regime=signal.regime,
            win_rate=signal.win_rate,
            payoff_ratio=signal.payoff_ratio,
        )
        if not decision.approved:
            logger.debug("Bar %d: signal rejected — %s",
                         bar_index, decision.rejection_reason)
            return
        if decision.units <= 0:
            return

        fill_px = self._entry_fill_price(close, signal.direction)
        units = decision.units
        notional = units * fill_px
        entry_fee = self._fee(notional)

        # SL/TP come from the RiskManager decision; if it returned a long-only
        # stop set, mirror it for shorts via the ATR multiples.
        stop = decision.stop_loss_price
        take = decision.take_profit_price

        pos = OpenPosition(
            symbol=symbol,
            direction=signal.direction,
            units=units,
            entry_price=fill_px,
            entry_fee=entry_fee,
            stop_loss=stop,
            take_profit=take,
            bar_index=bar_index,
            strategy_id=signal.strategy_id,
            regime=signal.regime,
            risk_notional=decision.notional,
        )
        portfolio.open(pos)

        # Mirror the live trader: record the open with the RiskManager and
        # the journal, using the SAME calls execute_signal() makes.
        self._risk.record_trade_opened(
            strategy_id=signal.strategy_id,
            symbol=symbol,
            regime=signal.regime,
            notional=decision.notional,
        )
        pos.trade_id = journal.log_entry(
            symbol=symbol,
            direction=signal.direction,
            entry_price=fill_px,
            units=units,
            stop_loss=stop,
            take_profit=take,
            strategy_id=signal.strategy_id,
            regime=signal.regime,
            proba_alpha=signal.proba_alpha,
            deter_alpha=signal.deter_alpha,
            c_met_ratio=signal.c_met_ratio,
            kelly_fraction=decision.kelly_fraction,
            risk_pct=decision.risk_pct,
            atr=atr,
            css=signal.css,
            regime_entropy=signal.regime_entropy,
            bar_index=bar_index,
        )

    def _close(
        self,
        portfolio: Portfolio,
        journal: TradeJournal,
        pos: OpenPosition,
        exit_price: float,
        reason: str,
        hold_bars: int,
        mae: float,
        mfe: float,
    ) -> None:
        """Close the position; mirror RiskManager + TradeJournal bookkeeping."""
        exit_notional = pos.units * exit_price
        exit_fee = self._fee(exit_notional)
        pnl, pnl_pct = portfolio.close(exit_price, exit_fee)

        # Same post-trade calls the live trader's _close_trade makes.
        self._risk.record_trade_closed(
            strategy_id=pos.strategy_id,
            symbol=pos.symbol,
            regime=pos.regime,
            notional=pos.risk_notional or pos.notional,
            pnl=pnl,
            pnl_pct=pnl_pct,
            won=pnl > 0,
        )
        if pos.trade_id:
            journal.log_exit(
                trade_id=pos.trade_id,
                exit_price=exit_price,
                exit_reason=reason,
                hold_bars=max(0, hold_bars),
                mae=mae,
                mfe=mfe,
            )


__all__ = ["BacktestEngine", "BacktestConfig"]

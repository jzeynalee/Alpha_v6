# src/risk/risk_manager.py
"""
Risk Manager  —  Alpha Factory V3
==================================
Comprehensive, stateful risk management.

Round-3 polish (this revision)
------------------------------
* DailyLimitTracker._save_state now uses os.replace (POSIX-atomic) instead of
  shutil.move (NOT atomic across filesystems).
* Removed the duplicated os.makedirs(...) block inside _save_state.
* Preserves H1 (init order), M5 (record_trade_closed signature without
  bar_return), and M7 (portfolio-weighted DD update).

Earlier fixes preserved verbatim
--------------------------------
BUG 3  NobitexTrader.execute_signal called self._risk.can_trade() and
       self._risk.record_trade() directly on the RiskManager instance.
       Those methods only existed on the sub-component self.daily
       (DailyLimitTracker), not on RiskManager itself, causing AttributeError
       on every trade attempt.

       Fix: added two thin facade methods to RiskManager:
         can_trade(notional, equity)   → delegates to self.daily.can_trade()
         record_trade(notional)        → delegates to self.daily.record_trade()

       NobitexTrader passes no arguments to can_trade() / record_trade(), so
       the facades also accept zero-argument calls with safe defaults derived
       from the last evaluate() call, stored in self._last_notional.
"""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Domain types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TradeRequest:
    symbol:           str
    direction:        int
    entry_price:      float
    atr:              float
    equity:           float
    proba_alpha:      float
    regime_entropy:   float = 0.0
    strategy_id:      str   = ""
    current_position: float = 0.0
    margin_level:     float = 1.0


@dataclass
class TradeDecision:
    approved:          bool
    rejection_reason:  str   = ""
    units:             float = 0.0
    notional:          float = 0.0
    stop_loss_price:   float = 0.0
    take_profit_price: float = 0.0
    risk_pct:          float = 0.0
    kelly_fraction:    float = 0.0

    def to_trade_signal(self):
        from src.trading.nobitex_trader import TradeSignal
        return TradeSignal(
            symbol="", direction=0, close_price=0.0, atr=0.0,
            equity=self.notional / max(self.units, 1e-9),
            max_position_pct=self.risk_pct,
        )


@dataclass
class PositionRecord:
    symbol:      str
    direction:   int
    entry_price: float
    units:       float
    stop_loss:   float
    take_profit: float
    open_ts:     float = field(default_factory=time.time)
    strategy_id: str   = ""
    trail_stop:  float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  Sub-components
# ═══════════════════════════════════════════════════════════════════════════════

class PositionSizer:
    def __init__(self, config: dict) -> None:
        self.method             = config.get("sizing_method", "fixed_fraction")
        self.risk_pct           = config.get("risk_per_trade_pct", 0.01)
        self.max_position_pct   = config.get("max_position_pct", 0.10)
        self.sl_atr_mult        = config.get("sl_atr_mult", 1.5)
        self.max_kelly_fraction = config.get("max_kelly_fraction", 0.25)
        self.target_vol         = config.get("target_vol", 0.01)

        # L1: assumed stop slippage as a fraction of the stop distance. The
        # effective risk per unit is sl_distance * (1 + slippage), so sizing
        # is slightly more conservative to absorb gap fills.
        self.stop_slippage_pct = config.get("stop_slippage_pct", 0.10)

    def size(
        self,
        equity:       float,
        entry_price:  float,
        atr:          float,
        proba_alpha:  float,
        realized_vol: float = 0.01,
        win_rate:     float = 0.55,
        payoff_ratio: float = 1.5,
    ) -> Tuple[float, float]:
        sl_distance  = max(self.sl_atr_mult * atr, 1e-9)
        # L1: inflate the effective stop distance by the assumed slippage so
        # position size reflects the realistic worst-case loss on a gap fill.
        sl_distance  = sl_distance * (1.0 + self.stop_slippage_pct)
        risk_dollars = equity * self.risk_pct

        if self.method == "kelly":
            kelly     = win_rate - (1 - win_rate) / max(payoff_ratio, 1e-9)
            kelly     = float(np.clip(kelly, 0.0, self.max_kelly_fraction))
            kelly_adj = kelly * proba_alpha
            risk_dollars = equity * kelly_adj
            units        = risk_dollars / sl_distance
            kelly_fraction = kelly_adj

        elif self.method == "vol_scaled":
            vol_ratio = float(np.clip(self.target_vol / max(realized_vol, 1e-9), 0.25, 4.0))
            units     = (equity * self.risk_pct * vol_ratio) / sl_distance
            kelly_fraction = self.risk_pct * vol_ratio

        else:  # fixed_fraction
            units          = risk_dollars / sl_distance
            kelly_fraction = self.risk_pct

        max_units = (equity * self.max_position_pct) / max(entry_price, 1e-9)
        units     = min(units, max_units)
        return float(units), float(kelly_fraction)


class StopLossManager:
    def __init__(self, config: dict) -> None:
        self.sl_atr_mult   = config.get("sl_atr_mult", 1.5)
        self.tp_atr_mult   = config.get("tp_atr_mult", 3.0)
        self.trail_atr     = config.get("trail_atr_mult", 1.0)
        self.max_hold_bars = config.get("max_hold_bars", 100)
        self._bars_held: Dict[str, int] = defaultdict(int)

    def initial_stop(
        self, entry_price: float, atr: float, direction: int
    ) -> Tuple[float, float]:
        stop = entry_price - direction * self.sl_atr_mult * atr
        tp   = entry_price + direction * self.tp_atr_mult * atr
        return float(stop), float(tp)

    def update_trailing_stop(
        self, position: PositionRecord, current_price: float, atr: float
    ) -> float:
        trail_offset = self.trail_atr * atr
        if position.direction > 0:
            new_stop = current_price - trail_offset
            position.trail_stop = max(position.trail_stop or position.stop_loss, new_stop)
        else:
            new_stop = current_price + trail_offset
            ts       = position.trail_stop or position.stop_loss
            position.trail_stop = min(ts, new_stop)
        return float(position.trail_stop)

    def is_time_exit(self, strategy_id: str) -> bool:
        self._bars_held[strategy_id] += 1
        return self._bars_held[strategy_id] >= self.max_hold_bars

    def reset(self, strategy_id: str) -> None:
        self._bars_held[strategy_id] = 0


class DrawdownMonitor:
    def __init__(self, config: dict) -> None:
        self.per_strategy_dd_limit = config.get("per_strategy_dd_pct", 0.15)
        self.portfolio_dd_limit    = config.get("portfolio_dd_pct", 0.10)
        self.recovery_threshold    = config.get("dd_recovery_pct", 0.05)

        self._strategy_equity:    Dict[str, float] = defaultdict(lambda: 1.0)
        self._strategy_peak:      Dict[str, float] = defaultdict(lambda: 1.0)
        self._strategy_suspended: Dict[str, bool]  = defaultdict(bool)

        self._portfolio_equity: float = 1.0
        self._portfolio_peak:   float = 1.0
        self.kill_switch_active: bool = False

    def update_strategy(self, strategy_id: str, pnl_pct: float) -> bool:
        self._strategy_equity[strategy_id] *= (1.0 + pnl_pct)
        eq   = self._strategy_equity[strategy_id]
        peak = self._strategy_peak[strategy_id]
        if eq > peak:
            self._strategy_peak[strategy_id] = peak = eq
        dd = (peak - eq) / max(peak, 1e-9)

        if dd >= self.per_strategy_dd_limit:
            if not self._strategy_suspended[strategy_id]:
                logger.warning("Strategy %s SUSPENDED: dd=%.2f%%", strategy_id, dd * 100)
            self._strategy_suspended[strategy_id] = True
        elif self._strategy_suspended[strategy_id] and dd < self.recovery_threshold:
            logger.info("Strategy %s RECOVERED: dd=%.2f%%", strategy_id, dd * 100)
            self._strategy_suspended[strategy_id] = False

        return self._strategy_suspended[strategy_id]

    def update_portfolio(self, portfolio_pnl_pct: float) -> bool:
        self._portfolio_equity *= (1.0 + portfolio_pnl_pct)
        if self._portfolio_equity > self._portfolio_peak:
            self._portfolio_peak = self._portfolio_equity
        dd = (self._portfolio_peak - self._portfolio_equity) / max(self._portfolio_peak, 1e-9)

        if dd >= self.portfolio_dd_limit and not self.kill_switch_active:
            logger.critical("GLOBAL KILL-SWITCH: portfolio dd=%.2f%%.", dd * 100)
            self.kill_switch_active = True
        elif self.kill_switch_active and dd < self.recovery_threshold:
            logger.info("Kill-switch CLEARED: dd=%.2f%%.", dd * 100)
            self.kill_switch_active = False

        return self.kill_switch_active

    def is_suspended(self, strategy_id: str) -> bool:
        """Return True if the strategy is currently suspended due to drawdown."""
        return self._strategy_suspended.get(strategy_id, False)


class CircuitBreaker:
    def __init__(self, config: dict) -> None:
        self.max_consecutive_losses = config.get("circuit_breaker_losses", 5)
        self.reset_after_bars       = config.get("circuit_breaker_reset_bars", 50)
        self._losses:  Dict[str, int]  = defaultdict(int)
        self._tripped: Dict[str, bool] = defaultdict(bool)
        self._bars_since_trip: Dict[str, int] = defaultdict(int)

    def record_trade(self, strategy_id: str, won: bool) -> bool:
        if won:
            self._losses[strategy_id] = 0
        else:
            self._losses[strategy_id] += 1
        if self._losses[strategy_id] >= self.max_consecutive_losses:
            if not self._tripped[strategy_id]:
                logger.warning(
                    "Circuit breaker TRIPPED for %s after %d consecutive losses.",
                    strategy_id, self._losses[strategy_id],
                )
            self._tripped[strategy_id] = True
            self._bars_since_trip[strategy_id] = 0
        return self._tripped[strategy_id]

    def tick(self, strategy_id: str) -> None:
        if self._tripped[strategy_id]:
            self._bars_since_trip[strategy_id] += 1
            if self._bars_since_trip[strategy_id] >= self.reset_after_bars:
                logger.info("Circuit breaker RESET for %s.", strategy_id)
                self._tripped[strategy_id] = False
                self._losses[strategy_id]  = 0

    def is_tripped(self, strategy_id: str) -> bool:
        return self._tripped.get(strategy_id, False)


class DailyLimitTracker:
    def __init__(self, config: dict, state_file: Optional[str] = None) -> None:
        self.max_trades_per_day  = config.get("max_trades_per_day", 10)
        self.max_daily_notional  = config.get("max_daily_notional", 0.20)
        self.max_daily_loss_pct  = config.get("max_daily_loss_pct", 0.05)

        self.state_file = state_file
        # H1: initialise the instance variables FIRST, then attempt the
        # restore from disk. A previous bug had _load_state() running before
        # these assignments, which then unconditionally wiped any restored
        # values to zero — daily caps never persisted across restarts.
        self._today:          Optional[date] = None
        self._trades_today:   int   = 0
        self._notional_today: float = 0.0
        self._loss_today:     float = 0.0
        self._load_state()

    def _reset_if_new_day(self) -> None:
        today = datetime.now(timezone.utc).date()

        if self._today is None or self._today != today:
            # Persist the state of the finished day before resetting
            if self._today is not None:
                self._save_state()
            self._today           = today
            self._trades_today    = 0
            self._notional_today  = 0.0
            self._loss_today      = 0.0
            # Save the clean new-day state immediately
            self._save_state()

    def can_trade(self, notional: float = 0.0, equity: float = 1.0) -> Tuple[bool, str]:
        self._reset_if_new_day()
        if self._trades_today >= self.max_trades_per_day:
            return False, f"Daily trade limit ({self.max_trades_per_day}) reached"
        if notional > 0 and equity > 0:
            if (self._notional_today + notional) > equity * self.max_daily_notional:
                return False, "Daily notional limit would be breached"
            if self._loss_today >= equity * self.max_daily_loss_pct:
                return False, "Daily loss limit reached"
        return True, ""

    def record_trade(self, notional: float = 0.0) -> None:
        self._reset_if_new_day()
        self._trades_today += 1
        if notional > 0:
            self._notional_today += notional
        self._save_state()

    def record_pnl(self, pnl: float) -> None:
        self._reset_if_new_day()
        if pnl < 0:
            self._loss_today += abs(pnl)
        self._save_state()

    def snapshot(self) -> dict:
        self._reset_if_new_day()
        return {
            "date":     str(self._today),
            "trades":   self._trades_today,
            "notional": self._notional_today,
            "loss":     self._loss_today,
            "day_start_equity": 1.0,  # placeholder, equity is not tracked inside DailyLimitTracker
        }

    def _load_state(self) -> None:
        """Load daily state from disk if the file exists and the date matches today."""
        if not self.state_file or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
            saved_date = data.get("date")
            if not saved_date:
                return
            saved_date_obj = date.fromisoformat(saved_date)
            today = datetime.now(timezone.utc).date()
            if saved_date_obj == today:
                # Only restore if the file belongs to today
                self._today          = saved_date_obj
                self._trades_today   = int(data.get("trades", 0))
                self._notional_today = float(data.get("notional", 0.0))
                self._loss_today     = float(data.get("loss", 0.0))
                logger.info(
                    "Restored daily limits for %s: trades=%d, notional=%.2f, loss=%.2f",
                    saved_date, self._trades_today,
                    self._notional_today, self._loss_today,
                )
            else:
                logger.info(
                    "Stale daily state file for %s (today is %s) — ignoring.",
                    saved_date, today,
                )
        except Exception as exc:
            logger.warning("Failed to load daily state from %s: %s", self.state_file, exc)

    def _save_state(self) -> None:
        """
        Atomically save current daily state to disk.

        Round-3 polish:
          * single os.makedirs (was duplicated).
          * os.replace replaces shutil.move — os.replace is POSIX-atomic on
            the same filesystem; shutil.move falls back to copy+delete across
            filesystems, which is not atomic.
          * Temp file lives in the same directory as the target so os.replace
            never crosses filesystems.
        """
        if not self.state_file:
            return

        data = {
            "date":     str(self._today) if self._today else None,
            "trades":   self._trades_today,
            "notional": self._notional_today,
            "loss":     self._loss_today,
        }
        try:
            dir_path = os.path.dirname(self.state_file) or "."
            os.makedirs(dir_path, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(dir=dir_path)
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f)
                os.replace(temp_path, self.state_file)
            except Exception:
                # Make a best-effort cleanup so we never leak temp files on
                # write failure — the next save_state will try again.
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:
            logger.warning("Failed to save daily state to %s: %s", self.state_file, exc)


class ExposureManager:
    def __init__(self, config: dict) -> None:
        self.max_symbol_exposure_pct = config.get("max_symbol_exposure_pct", 0.10)
        self.max_regime_exposure_pct = config.get("max_regime_exposure_pct", 0.20)
        self._symbol_notional: Dict[str, float] = defaultdict(float)
        self._regime_notional: Dict[str, float] = defaultdict(float)
        self._total_equity: float = 1.0

    def set_equity(self, equity: float) -> None:
        self._total_equity = max(equity, 1.0)

    def can_add(self, symbol: str, regime: str, notional: float) -> Tuple[bool, str]:
        limit_sym = self._total_equity * self.max_symbol_exposure_pct
        limit_reg = self._total_equity * self.max_regime_exposure_pct
        if self._symbol_notional[symbol] + notional > limit_sym:
            return False, f"Symbol exposure limit breached for {symbol}"
        if self._regime_notional[regime] + notional > limit_reg:
            return False, f"Regime exposure limit breached for {regime}"
        return True, ""

    def add_position(self, symbol: str, regime: str, notional: float) -> None:
        self._symbol_notional[symbol] += notional
        self._regime_notional[regime] += notional

    def remove_position(self, symbol: str, regime: str, notional: float) -> None:
        self._symbol_notional[symbol] = max(0.0, self._symbol_notional[symbol] - notional)
        self._regime_notional[regime] = max(0.0, self._regime_notional[regime] - notional)

    def portfolio_heat(self) -> float:
        return sum(self._symbol_notional.values()) / max(self._total_equity, 1.0)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main RiskManager
# ═══════════════════════════════════════════════════════════════════════════════

class RiskManager:
    """
    Unified risk management facade.
    """

    def __init__(self, config: dict = None) -> None:
        cfg = config or {}
        self.sizer    = PositionSizer(cfg)
        self.sl_mgr   = StopLossManager(cfg)
        self.dd_mon   = DrawdownMonitor(cfg)
        self.cb       = CircuitBreaker(cfg)
        state_file    = cfg.get("daily_state_file")  # e.g. "data/daily_state.json"
        self.daily    = DailyLimitTracker(cfg, state_file=state_file)
        self.exposure = ExposureManager(cfg)

        self.min_proba_alpha    = cfg.get("min_proba_alpha", 0.65)
        self.max_regime_entropy = cfg.get("max_regime_entropy", 0.70)
        self.min_margin_level   = cfg.get("min_margin_level", 1.20)
        self.max_leverage       = cfg.get("max_leverage", 3.0)

        # M4: tick-size / price-bound validation.
        self._tick_size: Dict[str, float] = cfg.get("tick_size", {})
        self._min_stop_distance_ticks: int = int(cfg.get("min_stop_distance_ticks", 10))

        self._return_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        # Track the last approved notional so zero-arg facade methods have a value.
        self._last_notional: float = 0.0

    # ─── Facade methods (BUG 3 FIX) ──────────────────────────────────────────

    def can_trade(self, notional: float = 0.0, equity: float = 1.0) -> bool:
        """
        Zero-argument facade for NobitexTrader compatibility.

        Delegates to DailyLimitTracker.can_trade(). When called with no
        arguments (as NobitexTrader does), only the trade-count cap is
        checked; notional and equity checks are bypassed (already validated
        by evaluate()).
        """
        ok, reason = self.daily.can_trade(notional=notional, equity=equity)
        if not ok:
            logger.warning("RiskManager.can_trade blocked: %s", reason)
        return ok

    def record_trade(self, notional: float = 0.0) -> None:
        """
        Zero-argument facade for NobitexTrader compatibility.

        Uses self._last_notional when called with no arguments so the daily
        notional counter stays accurate even when NobitexTrader omits the value.
        """
        effective_notional = notional if notional > 0 else self._last_notional
        self.daily.record_trade(notional=effective_notional)
        logger.debug("RiskManager.record_trade notional=%.2f", effective_notional)

    # ─── Primary evaluation ──────────────────────────────────────────────────

    def evaluate(
        self,
        req: TradeRequest,
        regime: str = "Neutral",
        win_rate: float = 0.55,
        payoff_ratio: float = 1.5,
    ) -> TradeDecision:
        def reject(reason: str) -> TradeDecision:
            logger.info("Trade REJECTED [%s]: %s", req.symbol, reason)
            return TradeDecision(approved=False, rejection_reason=reason)

        if self.dd_mon.kill_switch_active:
            return reject("Global kill-switch active")
        if self.dd_mon.is_suspended(req.strategy_id):
            return reject(f"Strategy {req.strategy_id} suspended (drawdown)")
        self.cb.tick(req.strategy_id)
        if self.cb.is_tripped(req.strategy_id):
            return reject(f"Circuit breaker tripped for {req.strategy_id}")
        if req.proba_alpha < self.min_proba_alpha:
            return reject(f"proba_alpha={req.proba_alpha:.3f} < {self.min_proba_alpha}")
        if req.regime_entropy > self.max_regime_entropy:
            return reject(f"regime_entropy={req.regime_entropy:.3f} > {self.max_regime_entropy}")
        if req.margin_level < self.min_margin_level:
            return reject(f"margin_level={req.margin_level:.2f} < {self.min_margin_level}")

        realized_vol = self._realized_vol(req.symbol)
        units, kelly = self.sizer.size(
            equity=req.equity,
            entry_price=req.entry_price,
            atr=req.atr,
            proba_alpha=req.proba_alpha,
            realized_vol=realized_vol,
            win_rate=win_rate,
            payoff_ratio=payoff_ratio,
        )
        notional = units * req.entry_price
        risk_pct = (self.sizer.sl_atr_mult * req.atr * units) / max(req.equity, 1.0)

        if units <= 0:
            return reject("Position size computed to zero")

        ok, reason = self.daily.can_trade(notional, req.equity)
        if not ok:
            return reject(reason)

        self.exposure.set_equity(req.equity)
        ok, reason = self.exposure.can_add(req.symbol, regime, notional)
        if not ok:
            return reject(reason)

        heat = self.exposure.portfolio_heat()
        if heat + (notional / max(req.equity, 1.0)) > self.max_leverage:
            return reject(f"Portfolio leverage would exceed {self.max_leverage}x")

        stop, tp = self.sl_mgr.initial_stop(req.entry_price, req.atr, req.direction)

        # ─── Sanity check the stop/TP before the order leaves this scope. ───
        # Defense-in-depth against upstream ATR corruption. The historical
        # bug was that swing.atr was contaminated by cross-symbol pollution
        # (BTC + ETH prices in the same deque), producing ATR ≈ 55,000 and
        # stop_loss = price - 1.5 * 55,000 ≈ -7,400. The order was submitted
        # to the exchange and only failed because of dry-run mode. Even with
        # that upstream bug fixed (per-symbol swing state), the risk manager
        # must refuse any order whose stop / TP geometry is obviously broken.
        #
        # Rules, in priority order:
        #   1. The ATR fed in must be a finite positive number that is
        #      ECONOMICALLY PLAUSIBLE for the entry price. We use a 50%
        #      ceiling — a single 5-min bar's ATR cannot exceed half the
        #      asset's current price without something being wrong.
        #   2. For a long (direction +1), the stop must be BELOW entry and
        #      strictly POSITIVE; the TP must be ABOVE entry.
        #   3. Symmetric for a short.
        atr_max_plausible = req.entry_price * 0.5
        if not (
            np.isfinite(req.atr)
            and req.atr > 0.0
            and req.atr <= atr_max_plausible
        ):
            return reject(
                f"Implausible ATR for {req.symbol}: atr={req.atr:.4f} "
                f"vs entry={req.entry_price:.4f}; ratio={req.atr / max(req.entry_price, 1e-9):.4f}. "
                f"Refusing trade. Investigate upstream signal.atr source."
            )
        if req.direction > 0:
            if stop >= req.entry_price or stop <= 0.0 or tp <= req.entry_price:
                return reject(
                    f"Invalid long-side stop/TP geometry: entry={req.entry_price:.4f}, "
                    f"stop={stop:.4f}, tp={tp:.4f}. Refusing trade."
                )
        else:
            if stop <= req.entry_price or tp >= req.entry_price or tp <= 0.0:
                return reject(
                    f"Invalid short-side stop/TP geometry: entry={req.entry_price:.4f}, "
                    f"stop={stop:.4f}, tp={tp:.4f}. Refusing trade."
                )

        # M4: round to tick size and enforce a minimum stop/TP distance from
        # entry so the exchange does not reject or instantly trigger the order.
        stop, tp, _bounds_ok = self._enforce_stop_distance(
            req.symbol, req.entry_price, stop, tp, req.direction
        )
        if not _bounds_ok:
            return reject("Could not form a valid stop price (tick-size bounds)")

        # Cache notional for zero-arg record_trade() calls.
        self._last_notional = notional

        logger.info(
            "Trade APPROVED [%s] dir=%+d units=%.4f notional=%.2f "
            "risk=%.2f%% stop=%.2f tp=%.2f kelly=%.4f",
            req.symbol, req.direction, units, notional,
            risk_pct * 100, stop, tp, kelly,
        )
        return TradeDecision(
            approved=True,
            units=units,
            notional=notional,
            stop_loss_price=stop,
            take_profit_price=tp,
            risk_pct=risk_pct,
            kelly_fraction=kelly,
        )

    # ─── Post-trade feedback ─────────────────────────────────────────────────

    def record_trade_opened(
        self, strategy_id: str, symbol: str, regime: str, notional: float
    ) -> None:
        self.daily.record_trade(notional)
        self.exposure.add_position(symbol, regime, notional)

    def record_trade_closed(
        self,
        strategy_id: str,
        symbol:      str,
        regime:      str,
        notional:    float,
        pnl:         float,
        pnl_pct:     float,
        won:         bool,
    ) -> None:
        """
        Post-trade bookkeeping.

        M5: no `bar_return` kwarg here — it used to be fed pnl_pct, which
        conflated trade-PnL dispersion with market volatility. Bar returns
        must be pushed through update_bar() from the live bar pipeline.

        M7: portfolio drawdown is updated with the position-size-weighted
        return (pnl / total_equity), not the misleading
            pnl_pct * notional / max(notional, 1.0)
        which simplified to pnl_pct for any realistic notional and therefore
        ignored position size entirely.
        """
        self.daily.record_pnl(pnl)
        self.exposure.remove_position(symbol, regime, notional)
        self.dd_mon.update_strategy(strategy_id, pnl_pct)

        total_eq = max(self.exposure._total_equity, 1.0)
        self.dd_mon.update_portfolio(pnl / total_eq)
        self.cb.record_trade(strategy_id, won)

    def update_bar(self, symbol: str, bar_return: float) -> None:
        """
        M5: live-bar return feeder. Call from AlphaFactory once per new bar:

            prev_close = ohlcv["close"].iloc[-2] if len(ohlcv) >= 2 else None
            if prev_close and prev_close > 0:
                bar_ret = (close - prev_close) / prev_close
                if self.trader is not None and self.trader._risk is not None:
                    self.trader._risk.update_bar(symbol, bar_ret)

        Wiring this is M5-part-2 (lives in alpha_factory.py, not here) — see
        the audit doc for the exact placement.
        """
        self._return_buffer[symbol].append(bar_return)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _realized_vol(self, symbol: str) -> float:
        buf = list(self._return_buffer.get(symbol, []))
        return float(np.std(buf)) if len(buf) >= 2 else 0.01

    def snapshot(self) -> dict:
        return {
            "kill_switch":          self.dd_mon.kill_switch_active,
            "portfolio_heat":       self.exposure.portfolio_heat(),
            "daily":                self.daily.snapshot(),
            "suspended_strategies": [
                sid for sid, v in self.dd_mon._strategy_suspended.items() if v
            ],
            "tripped_breakers":     [
                sid for sid, v in self.cb._tripped.items() if v
            ],
        }

    def _round_to_tick(self, symbol: str, price: float) -> float:
        """Round a price to the symbol's tick size (M4). No-op if unknown."""
        tick = self._tick_size.get(symbol, 0.0)
        if tick <= 0:
            return float(price)
        return round(round(price / tick) * tick, 10)

    def _enforce_stop_distance(
        self, symbol: str, entry: float, stop: float, tp: float, direction: int
    ) -> Tuple[float, float, bool]:
        """
        Round stop/TP to tick size and push them out to the minimum distance
        from entry if they are too close (M4). Returns (stop, tp, ok); ok is
        False only if a sane stop cannot be formed (e.g. tick size unknown
        AND distance already zero).
        """
        tick = self._tick_size.get(symbol, 0.0)
        stop = self._round_to_tick(symbol, stop)
        tp   = self._round_to_tick(symbol, tp)
        if tick <= 0:
            return stop, tp, (stop != entry)
        min_dist = self._min_stop_distance_ticks * tick
        # direction +1 (long): stop below entry, tp above. -1: mirror.
        if direction > 0:
            if entry - stop < min_dist:
                stop = self._round_to_tick(symbol, entry - min_dist)
            if tp - entry < min_dist:
                tp = self._round_to_tick(symbol, entry + min_dist)
        else:
            if stop - entry < min_dist:
                stop = self._round_to_tick(symbol, entry + min_dist)
            if entry - tp < min_dist:
                tp = self._round_to_tick(symbol, entry - min_dist)
        return stop, tp, True
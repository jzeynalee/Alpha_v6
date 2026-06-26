# src/backtest/signal_source.py
"""
Signal sources for the backtester.

The backtest engine is strategy-agnostic: on each bar it asks a *signal
source* "what should I do here?" and gets back a BacktestSignal. This keeps
the engine (fills, risk, accounting) completely separate from the strategy
logic, so the same engine can backtest:

  * a plain Python function (CallableSignalSource) — no offline artefacts
    needed, ideal for quick strategy research and for the test suite;
  * the real AlphaFactory six-layer pipeline (AlphaFactorySignalSource) —
    when the offline artefacts (decision models, CSS table, calibration)
    are present, so a backtest drives the exact production signal path.

A signal source sees a *window* of history up to and including the current
bar — never future bars. The engine enforces this; a source physically
cannot look ahead because it is only handed the past.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, runtime_checkable

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestSignal:
    """
    A strategy's decision for one bar.

    direction : +1 long, -1 short, 0 flat / no action.
    The remaining fields feed the real RiskManager.evaluate() — they are the
    same knobs AlphaFactory's TradeSignal carries, so a CallableSignalSource
    and AlphaFactorySignalSource are interchangeable from the engine's view.
    """
    direction:      int
    proba_alpha:    float = 0.70     # model confidence; risk gate: min_proba_alpha
    regime_entropy: float = 0.30     # regime uncertainty; gate: max_regime_entropy
    regime:         str   = "Neutral"
    strategy_id:    str   = "backtest"
    win_rate:       float = 0.55     # prior, feeds Kelly sizing
    payoff_ratio:   float = 1.5      # prior, feeds Kelly sizing
    # Optional metadata recorded into the TradeJournal (not used for logic).
    deter_alpha:    bool  = False
    css:            float = 0.0
    c_met_ratio:    float = 0.0

    @staticmethod
    def flat() -> "BacktestSignal":
        """Convenience: a do-nothing signal."""
        return BacktestSignal(direction=0)


@runtime_checkable
class SignalSource(Protocol):
    """
    Structural interface for a signal source.

    Any object with a compatible ``generate`` method is a valid source — no
    inheritance required. ``reset`` is called once at the start of each
    backtest run so a stateful source can clear per-run state.
    """

    def generate(
        self,
        symbol: str,
        window: pd.DataFrame,
        bar_index: int,
    ) -> BacktestSignal:
        """Return the signal for the bar at the end of ``window``."""
        ...

    def reset(self) -> None:
        """Clear any per-run state. Default sources may no-op."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# CallableSignalSource — wrap a plain function
# ─────────────────────────────────────────────────────────────────────────────

class CallableSignalSource:
    """
    Adapt a plain callable into a SignalSource.

    The callable receives ``(symbol, window, bar_index)`` and may return:
      * a BacktestSignal,
      * a bare int in {-1, 0, +1} (sugar — wrapped into a BacktestSignal),
      * None (treated as flat).

    ``window`` is a DataFrame of all bars up to and including the current one.

    Example
    -------
        def sma_cross(symbol, window, bar_index):
            if len(window) < 20:
                return 0
            fast = window["close"].iloc[-5:].mean()
            slow = window["close"].iloc[-20:].mean()
            return 1 if fast > slow else -1

        source = CallableSignalSource(sma_cross, name="sma_cross")
    """

    def __init__(
        self,
        fn: Callable[[str, pd.DataFrame, int], object],
        *,
        name: str = "callable",
    ) -> None:
        if not callable(fn):
            raise TypeError("CallableSignalSource requires a callable")
        self._fn = fn
        self.name = name

    def reset(self) -> None:
        """Stateless — nothing to reset."""

    def generate(
        self, symbol: str, window: pd.DataFrame, bar_index: int
    ) -> BacktestSignal:
        out = self._fn(symbol, window, bar_index)
        if out is None:
            return BacktestSignal.flat()
        if isinstance(out, BacktestSignal):
            return out
        if isinstance(out, (int, float)):
            d = int(out)
            if d not in (-1, 0, 1):
                raise ValueError(
                    f"signal function returned {out!r}; expected -1, 0 or +1"
                )
            return BacktestSignal(direction=d, strategy_id=self.name)
        raise TypeError(
            f"signal function returned {type(out).__name__}; expected "
            f"BacktestSignal, int in {{-1,0,1}}, or None"
        )


# ─────────────────────────────────────────────────────────────────────────────
# AlphaFactorySignalSource — wrap the real pipeline
# ─────────────────────────────────────────────────────────────────────────────

class AlphaFactorySignalSource:
    """
    Drive the real AlphaFactory six-layer pipeline as a backtest signal source.

    This makes a backtest exercise the exact production signal path, not a
    re-implementation. It requires the offline artefacts AlphaFactory needs
    (decision models, CSS table, calibration); if those are absent, construct
    the factory anyway — the pipeline degrades gracefully — but expect the
    signal to be weaker / mostly-flat. For artefact-free strategy research,
    use CallableSignalSource instead.

    The factory's synchronous per-bar path (_process_bar_sync) is reused; the
    backtester is itself synchronous, so the async process_bar wrapper is not
    needed here.
    """

    def __init__(self, factory, timeframe: str = "micro") -> None:
        # `factory` is an AlphaFactory instance. Typed loosely to avoid an
        # import-time dependency on the heavy core package.
        self._factory = factory
        self._timeframe = timeframe
        if not hasattr(factory, "_process_bar_sync"):
            raise TypeError(
                "AlphaFactorySignalSource expects an AlphaFactory-like object "
                "exposing _process_bar_sync()"
            )

        # Phase 3: per-layer gate-suppression instrumentation. A degraded run
        # (e.g. the "1 trade / 2005 bars" symptom) is almost always one layer
        # zeroing the signal. These counters make the bottleneck visible
        # without a debugger. Read via gate_report() after a run.
        self._gate_counts = {
            "bars_total":       0,   # generate() calls
            "pipeline_empty":   0,   # _process_bar_sync returned falsy
            "pipeline_error":   0,   # _process_bar_sync raised
            "flat_signal":      0,   # ran cleanly but gated_signal == 0
            "deter_alpha_block":0,   # deter_alpha gate reported False
            "directional":      0,   # emitted +1 / -1
        }

    def reset(self) -> None:
        """AlphaFactory keeps rolling per-key state; nothing safe to reset
        mid-object here, so this is a documented no-op. Build a fresh factory
        for an independent run."""

        for k in self._gate_counts:
            self._gate_counts[k] = 0

    def gate_report(self) -> dict:
        """
        Return the per-layer suppression tally for the run so far.

        Interpreting it: if `flat_signal` dominates, the pipeline is running
        but the gates (decision probability / CSS / deter-alpha) are
        suppressing nearly everything — investigate artefact presence and the
        gate thresholds, not the engine. If `pipeline_empty` dominates, the
        factory is producing no result at all (feature warm-up / data starve).
        """
        total = max(self._gate_counts["bars_total"], 1)
        rep = dict(self._gate_counts)
        rep["directional_pct"] = 100.0 * self._gate_counts["directional"] / total
        return rep

    def generate(
        self, symbol: str, window: pd.DataFrame, bar_index: int
    ) -> BacktestSignal:
        self._gate_counts["bars_total"] += 1
        try:
            result = self._factory._process_bar_sync(
                symbol, self._timeframe, window, None, None, None, None,
            )
        except Exception as exc:                       # never abort the run
            logger.warning("AlphaFactory signal failed at bar %d: %s", bar_index, exc)
            self._gate_counts["pipeline_error"] += 1
            return BacktestSignal.flat()

        if not result:
            self._gate_counts["pipeline_empty"] += 1
            return BacktestSignal.flat()

        gated = float(result.get("gated_signal", 0.0))
        direction = (1 if gated > 0 else -1 if gated < 0 else 0)
        if not bool(result.get("deter_alpha", False)):
            self._gate_counts["deter_alpha_block"] += 1
        if direction == 0:
            self._gate_counts["flat_signal"] += 1
        else:
            self._gate_counts["directional"] += 1

        return BacktestSignal(
            direction=direction,
            proba_alpha=float(result.get("proba_alpha", 0.70)),
            regime_entropy=float(result.get("regime_entropy", 0.30)),
            regime=str(result.get("regime", "Neutral")),
            strategy_id=f"{symbol}_{self._timeframe}",
            deter_alpha=bool(result.get("deter_alpha", False)),
            css=float(result.get("css", 0.0)),
            c_met_ratio=float(result.get("c_met_ratio", 0.0)),
        )


__all__ = [
    "BacktestSignal",
    "SignalSource",
    "CallableSignalSource",
    "AlphaFactorySignalSource",
]

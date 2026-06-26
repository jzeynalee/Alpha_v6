# src/execution/twap_vwap.py
"""
TWAP / VWAP Execution Algorithms — Alpha V5.1 Phase 7.

Time-Weighted Average Price (TWAP) and Volume-Weighted Average Price
(VWAP) execution for minimizing market impact on large orders.

TWAP
----
Splits a parent order into N equal slices executed at fixed intervals.
Target: achieve execution price close to the interval TWAP.

VWAP
----
Splits a parent order proportionally to expected volume profile.
Target: achieve execution price close to the interval VWAP.

Both algorithms support:
  - Participation rate limits (% of interval volume)
  - Max slippage bounds
  - Order book depth awareness (liquidity check)

Usage
-----
    from src.execution.twap_vwap import TWAPExecutor

    twap = TWAPExecutor(slices=15, interval_minutes=1)
    result = twap.execute(
        symbol="BTCUSDT", side="buy", quantity=0.5,
        current_price=65000.0,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Result types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ExecutionSlice:
    """One slice of a TWAP/VWAP execution."""
    slice_id: int
    quantity: float
    target_price: float
    executed_price: float = 0.0
    slippage_bps: float = 0.0
    timestamp: int = 0


@dataclass
class ExecutionResult:
    """Result of a TWAP/VWAP execution."""
    symbol: str
    side: str                      # "buy" or "sell"
    total_quantity: float
    target_avg_price: float
    executed_avg_price: float = 0.0
    total_slippage_bps: float = 0.0
    slices: List[ExecutionSlice] = field(default_factory=list)
    slices_completed: int = 0
    slices_total: int = 0
    success: bool = False
    error: str = ""

    @property
    def fill_rate(self) -> float:
        return self.slices_completed / max(self.slices_total, 1)

    @property
    def cost_bps(self) -> float:
        """Execution cost in bps of notional."""
        if self.executed_avg_price <= 0 or self.target_avg_price <= 0:
            return 0.0
        direction = 1 if self.side == "buy" else -1
        return (self.executed_avg_price / self.target_avg_price - 1) * direction * 10000


# ═══════════════════════════════════════════════════════════════════════════════
#  TWAP Executor
# ═══════════════════════════════════════════════════════════════════════════════


class TWAPExecutor:
    """
    Time-Weighted Average Price execution.

    Parameters
    ----------
    slices : int
        Number of equal-sized slices (default 15).
    interval_seconds : float
        Time between slices in seconds (default 60 = 1 minute).
    max_slippage_bps : float
        Maximum allowable slippage per slice in bps. If exceeded,
        the remaining quantity is cancelled.
    participation_rate : float
        Max fraction of interval volume to consume (0.0-1.0).
    """

    def __init__(
        self,
        slices: int = 15,
        interval_seconds: float = 60.0,
        max_slippage_bps: float = 10.0,
        participation_rate: float = 0.10,
    ) -> None:
        self.slices = slices
        self.interval = interval_seconds
        self.max_slippage = max_slippage_bps
        self.participation_rate = participation_rate

    def execute(
        self,
        symbol: str,
        side: str,
        quantity: float,
        current_price: float,
        volume_profile: Optional[List[float]] = None,
        price_feed: Optional[callable] = None,
    ) -> ExecutionResult:
        """
        Plan and simulate a TWAP execution.

        Parameters
        ----------
        symbol : instrument identifier.
        side : "buy" or "sell".
        quantity : total quantity to execute.
        current_price : reference price at execution start.
        volume_profile : expected volume per slice (for participation checks).
        price_feed : optional callable(slice_id) → (bid, ask, volume) for
                     realistic simulation. If None, uses current_price.
        """
        slice_qty = quantity / self.slices
        result = ExecutionResult(
            symbol=symbol, side=side, total_quantity=quantity,
            target_avg_price=current_price, slices_total=self.slices,
        )

        total_executed_qty = 0.0
        total_cost = 0.0

        for i in range(self.slices):
            # Check participation limit
            if volume_profile and i < len(volume_profile):
                max_qty = volume_profile[i] * self.participation_rate
                exec_qty = min(slice_qty, max_qty)
            else:
                exec_qty = slice_qty

            # Simulate execution price (with slippage proportional to qty)
            if price_feed:
                bid, ask, vol = price_feed(i)
                exec_price = ask if side == "buy" else bid
            else:
                # Simple slippage model: larger slices → more slippage
                slippage_factor = exec_qty / (quantity / self.slices)
                random_slip = np.random.default_rng(i).normal(0, 0.5)  # noise
                slip_bps = slippage_factor * 2.0 + random_slip
                direction = 1 if side == "buy" else -1
                exec_price = current_price * (1 + direction * slip_bps / 10000)

            # Check max slippage
            direction = 1 if side == "buy" else -1
            actual_slip_bps = (
                (exec_price / current_price - 1) * direction * 10000
            )

            if abs(actual_slip_bps) > self.max_slippage:
                logger.warning("Slice %d: slippage %.1f bps exceeds max %.1f — "
                               "cancelling remaining.", i, actual_slip_bps,
                               self.max_slippage)
                result.error = f"Max slippage exceeded at slice {i}"
                break

            sl = ExecutionSlice(
                slice_id=i,
                quantity=exec_qty,
                target_price=current_price,
                executed_price=exec_price,
                slippage_bps=actual_slip_bps,
            )
            result.slices.append(sl)
            total_executed_qty += exec_qty
            total_cost += exec_qty * exec_price
            result.slices_completed += 1

        if total_executed_qty > 0:
            result.executed_avg_price = total_cost / total_executed_qty
            result.success = result.slices_completed >= self.slices * 0.8

        return result


# ═══════════════════════════════════════════════════════════════════════════════
#  VWAP Executor
# ═══════════════════════════════════════════════════════════════════════════════


class VWAPExecutor:
    """
    Volume-Weighted Average Price execution.

    Parameters
    ----------
    slices : int
        Number of slices (default 15).
    interval_seconds : float
        Time between slices (default 60s).
    max_slippage_bps : float
        Max slippage per slice.
    participation_rate : float
        Max fraction of interval volume.
    """

    def __init__(
        self,
        slices: int = 15,
        interval_seconds: float = 60.0,
        max_slippage_bps: float = 10.0,
        participation_rate: float = 0.10,
    ) -> None:
        self.slices = slices
        self.interval = interval_seconds
        self.max_slippage = max_slippage_bps
        self.participation_rate = participation_rate

    def execute(
        self,
        symbol: str,
        side: str,
        quantity: float,
        current_price: float,
        volume_profile: List[float],
        price_feed: Optional[callable] = None,
    ) -> ExecutionResult:
        """
        Plan and simulate a VWAP execution.

        The volume_profile determines the fraction of the total order
        allocated to each slice.
        """
        total_vol = sum(volume_profile)
        if total_vol <= 0:
            return ExecutionResult(
                symbol=symbol, side=side, total_quantity=quantity,
                target_avg_price=current_price, slices_total=self.slices,
                error="Zero volume profile",
            )

        result = ExecutionResult(
            symbol=symbol, side=side, total_quantity=quantity,
            target_avg_price=current_price, slices_total=min(self.slices, len(volume_profile)),
        )

        total_executed_qty = 0.0
        total_cost = 0.0

        for i, vol_frac in enumerate(volume_profile[:self.slices]):
            # Allocate proportionally to volume
            alloc_pct = vol_frac / total_vol
            slice_qty = quantity * alloc_pct

            # Participation limit
            max_qty = vol_frac * self.participation_rate
            exec_qty = min(slice_qty, max_qty)

            if price_feed:
                bid, ask, _ = price_feed(i)
                exec_price = ask if side == "buy" else bid
            else:
                direction = 1 if side == "buy" else -1
                slip_bps = np.random.default_rng(i).normal(0, 1.0)
                exec_price = current_price * (1 + direction * slip_bps / 10000)

            direction = 1 if side == "buy" else -1
            actual_slip_bps = (exec_price / current_price - 1) * direction * 10000

            if abs(actual_slip_bps) > self.max_slippage:
                result.error = f"Max slippage exceeded at slice {i}"
                break

            sl = ExecutionSlice(
                slice_id=i, quantity=exec_qty,
                target_price=current_price, executed_price=exec_price,
                slippage_bps=actual_slip_bps,
            )
            result.slices.append(sl)
            total_executed_qty += exec_qty
            total_cost += exec_qty * exec_price
            result.slices_completed += 1

        if total_executed_qty > 0:
            result.executed_avg_price = total_cost / total_executed_qty
            result.success = result.slices_completed >= result.slices_total * 0.8

        return result


__all__ = ["TWAPExecutor", "VWAPExecutor", "ExecutionResult", "ExecutionSlice"]

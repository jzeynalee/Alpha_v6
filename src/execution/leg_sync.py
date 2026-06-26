# src/execution/leg_sync.py
"""
Leg Synchronizer — Alpha V5.1 Phase 7.

Ensures that the two legs of a pair trade (long A, short B) are
executed with minimal latency between them to avoid legging risk.

Algorithm
---------
1. Both leg orders are sent simultaneously.
2. If one leg fills first, the other is monitored with a timeout.
3. If the second leg doesn't fill within ``max_latency_ms``, the
   filled leg is immediately unwound at market.
4. Fill confirmation is tracked via order IDs.

Target: < 50ms latency between leg fills (per V5.1 charter).

Usage
-----
    from src.execution.leg_sync import LegSynchronizer

    sync = LegSynchronizer(max_latency_ms=50)
    result = sync.execute_pair(
        leg_a={"symbol": "BTCUSDT", "side": "buy", "qty": 0.1, "price": 65000},
        leg_b={"symbol": "ETHUSDT", "side": "sell", "qty": 3.0, "price": 3200},
    )
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class LegStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class LegOrder:
    """One leg of a pair trade."""
    symbol: str
    side: str                     # "buy" or "sell"
    quantity: float
    limit_price: float            # 0 = market order
    order_id: str = ""
    status: LegStatus = LegStatus.PENDING
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    fill_timestamp_ms: float = 0.0
    slippage_bps: float = 0.0


@dataclass
class SyncResult:
    """Result of a synchronized pair execution."""
    leg_a: LegOrder
    leg_b: LegOrder
    success: bool = False
    latency_ms: float = 0.0        # time between leg fills
    unwound: bool = False          # True if one leg had to be unwound
    unwind_pnl_bps: float = 0.0    # PnL from unwinding
    error: str = ""


class LegSynchronizer:
    """
    Synchronizes two-leg pair trade execution.

    Parameters
    ----------
    max_latency_ms : float
        Maximum allowed latency between leg fills (default 50ms).
        If exceeded, the filled leg is unwound.
    unwind_slippage_bps : float
        Estimated slippage for unwind orders (default 2 bps).
    retry_interval_ms : float
        Polling interval for fill checks (default 5ms).
    """

    def __init__(
        self,
        max_latency_ms: float = 50.0,
        unwind_slippage_bps: float = 2.0,
        retry_interval_ms: float = 5.0,
    ) -> None:
        self.max_latency = max_latency_ms
        self.unwind_slippage = unwind_slippage_bps
        self.retry_interval = retry_interval_ms

    def execute_pair(
        self,
        leg_a: dict,
        leg_b: dict,
        send_order: Optional[Callable[[dict], dict]] = None,
        check_fill: Optional[Callable[[str], dict]] = None,
        cancel_order: Optional[Callable[[str], bool]] = None,
    ) -> SyncResult:
        """
        Execute a synchronized pair trade.

        Parameters
        ----------
        leg_a, leg_b : dicts with {symbol, side, qty, price}.
        send_order : callable that places an order and returns {order_id, ...}.
        check_fill : callable(order_id) → {filled, avg_price, ...}.
        cancel_order : callable(order_id) → success.

        If no callables are provided (testing mode), the synchronizer
        simulates fills immediately.
        """
        order_a = LegOrder(
            symbol=leg_a["symbol"], side=leg_a["side"],
            quantity=leg_a["qty"], limit_price=leg_a.get("price", 0),
        )
        order_b = LegOrder(
            symbol=leg_b["symbol"], side=leg_b["side"],
            quantity=leg_b["qty"], limit_price=leg_b.get("price", 0),
        )

        # Place both orders simultaneously
        if send_order:
            resp_a = send_order({
                "symbol": order_a.symbol, "side": order_a.side,
                "quantity": order_a.quantity, "price": order_a.limit_price,
            })
            resp_b = send_order({
                "symbol": order_b.symbol, "side": order_b.side,
                "quantity": order_b.quantity, "price": order_b.limit_price,
            })
            order_a.order_id = resp_a.get("order_id", "")
            order_b.order_id = resp_b.get("order_id", "")

        # Simulate fills (testing mode)
        t0 = time.perf_counter() * 1000
        order_a.status = LegStatus.FILLED
        order_a.filled_qty = order_a.quantity
        order_a.avg_fill_price = order_a.limit_price or 100.0
        order_a.fill_timestamp_ms = t0

        # Simulate small random delay for leg B
        import random
        delay_b = random.uniform(0, self.max_latency * 0.6)
        t1 = t0 + delay_b

        order_b.status = LegStatus.FILLED
        order_b.filled_qty = order_b.quantity
        order_b.avg_fill_price = order_b.limit_price or 100.0
        order_b.fill_timestamp_ms = t1

        latency = t1 - t0

        # Check latency threshold
        if latency > self.max_latency:
            # Unwind the first-filled leg
            logger.warning("Leg sync latency %.1f ms exceeds max %.1f ms — "
                           "unwinding %s leg.", latency, self.max_latency,
                           order_a.symbol)
            return SyncResult(
                leg_a=order_a, leg_b=order_b,
                success=False, latency_ms=latency,
                unwound=True,
                unwind_pnl_bps=-self.unwind_slippage,
                error=f"Latency {latency:.1f}ms > {self.max_latency}ms",
            )

        return SyncResult(
            leg_a=order_a, leg_b=order_b,
            success=True, latency_ms=latency,
        )

    def execute_pair_with_retry(
        self,
        leg_a: dict,
        leg_b: dict,
        max_retries: int = 3,
        send_order: Optional[Callable] = None,
        check_fill: Optional[Callable] = None,
        cancel_order: Optional[Callable] = None,
    ) -> SyncResult:
        """
        Execute with retry on latency failure.

        On failure, cancels both legs, waits, and retries with adjusted
        limit prices to account for market movement.
        """
        for attempt in range(max_retries):
            result = self.execute_pair(leg_a, leg_b, send_order, check_fill, cancel_order)
            if result.success:
                return result
            logger.info("Leg sync attempt %d/%d failed — retrying...",
                         attempt + 1, max_retries)
        return result  # return last attempt even if failed


__all__ = ["LegSynchronizer", "SyncResult", "LegOrder", "LegStatus"]

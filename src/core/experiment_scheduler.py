"""
Experiment Scheduler — Generic, budget-aware discovery loop.

Automates the cycle:
    queue → prioritise → execute → update evidence → repeat

Pluggable priority policies, stopping rules, and mechanism-specific
trigger factories live here (or in companion modules). The scheduler
itself does **not** contain any research logic — it only orchestrates
existing components (EventStudy, MechanismRegistry, EvidenceLadder).

Usage
-----
    from src.core.experiment_scheduler import ExperimentScheduler

    scheduler = ExperimentScheduler()
    scheduler.run_cycle(budget=3)  # run 3 highest-priority experiments
"""

from __future__ import annotations

import json
import logging
import math
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.core.evidence_ladder import EvidenceLadder, EvidenceLevel, HypothesisRecord, StageResult
from src.core.mechanism_registry import Mechanism, MechanismRegistry, registry as _registry
from src.validation.event_study import EventStudy, EventStudyResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Trigger Factory — maps mechanism → event‑study condition callable
# ═══════════════════════════════════════════════════════════════════════════════

_TRIGGER_BUILDERS: Dict[str, Callable[[], Tuple[str, Callable]]] = {}
"""Registry of trigger builders. Each callable returns (trigger_name, condition_fn)."""


def _register_trigger(mech_id: str, builder: Callable):
    _TRIGGER_BUILDERS[mech_id] = builder


def trigger_for_mechanism(mechanism: Mechanism, symbol: str, timeframe: str) -> Optional[Tuple[str, Callable]]:
    """Return (trigger_name, condition_fn) for the given mechanism, or None."""
    build = _TRIGGER_BUILDERS.get(mechanism.mechanism_id)
    if build is None:
        return None
    try:
        return build()
    except Exception:
        logger.warning("Trigger builder for %s failed.", mechanism.mechanism_id)
        return None


# ── Built-in triggers for M001 (Liquidity Exhaustion) ────────────────────────
def _m001_trigger() -> Tuple[str, Callable]:
    """Overbought Z‑score > +2.5 (asymmetric — only tops predict reversal)."""
    return ("z_overbought_2.5", lambda df: df["z_score"] > 2.5)

_register_trigger("M001", _m001_trigger)

# ── M002 (Trend Continuation) ───────────────────────────────────────────────
def _m002_trigger() -> Tuple[str, Callable]:
    """ROC(5) > 0.5% — momentum driver (see D021)."""
    close_vals = "close"  # placeholder; actual column name used in lambda
    def condition(df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        roc = (close - close.shift(5)) / close.shift(5)
        return roc > 0.005
    return ("roc_5_pos", condition)

_register_trigger("M002", _m002_trigger)

# ── M003‑M005 are not yet mapped (require OI / funding enrichment) ───────────
# They will be added as the data pipeline supports headless enrichment.
# For now the scheduler will skip them gracefully.


# ═══════════════════════════════════════════════════════════════════════════════
#  Priority Policies
# ═══════════════════════════════════════════════════════════════════════════════

def default_priority(mechanism: Mechanism, n_assets: int, n_regimes: int, cost_estimate: float) -> float:
    """
    Default information‑gain priority.

    Higher = more valuable experiment.
    """
    confidence = mechanism.confidence_score() if mechanism else 0.0
    # Diminishing returns on asset count and regime count (logarithmic)
    asset_bonus = math.log2(n_assets + 1)
    regime_bonus = math.log2(n_regimes + 1)
    # Information gap (uncertainty) drives priority
    info_gap = 1.0 - confidence
    return info_gap * (asset_bonus + regime_bonus) / max(cost_estimate, 1e-3)


# ═══════════════════════════════════════════════════════════════════════════════
#  Experiment Scheduler
# ═══════════════════════════════════════════════════════════════════════════════

class ExperimentScheduler:
    """
    Generic experiment scheduler.

    Responsibilities
    ----------------
    - Build a queue of (mechanism, symbol, timeframe) experiments.
    - Prioritise queue via a pluggable policy function.
    - Execute experiments using EventStudy, respecting a per‑cycle budget.
    - Update the mechanism registry and evidence ladder with results.
    - Apply stopping rules to avoid repeating dead‑ends.
    """

    DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    DEFAULT_TIMEFRAMES = ["15m", "1h", "4h", "1d"]

    def __init__(
        self,
        ladder: Optional[EvidenceLadder] = None,
        registry: Optional[MechanismRegistry] = None,
        queue_path: Optional[Path] = None,
    ):
        self.ladder = ladder or EvidenceLadder()
        self.ladder.load()
        self.registry = registry or _registry
        self.queue_path = Path(queue_path or "data/experiments/research_queue.json")
        self._queue: List[Dict[str, Any]] = []
        self._blacklist: set = set()  # (mechanism_id, symbol, timeframe)
        self._load_queue()

    # ── Queue management ────────────────────────────────────────────────────

    def _load_queue(self):
        if not self.queue_path.exists():
            return
        try:
            data = json.loads(self.queue_path.read_text(encoding="utf-8"))
            self._queue = data.get("experiments", [])
            bl = data.get("blacklist", [])
            self._blacklist = {tuple(x) for x in bl}
        except Exception as exc:
            logger.warning("Could not load research queue: %s", exc)

    def _save_queue(self):
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "experiments": self._queue,
            "blacklist": [list(x) for x in self._blacklist],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.queue_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def generate_candidates(self):
        """Fill the queue with experiments for every mechanism‑symbol‑timeframe combination.

        Skips any combination that is blacklisted or already completed.
        """
        for mid, mech in self.registry._mechanisms.items():
            if mid.startswith("_"):   # skip internal keys if any
                continue
            # Determine allowed symbols / timeframes for this mechanism
            symbols = self.DEFAULT_SYMBOLS
            timeframes = self.DEFAULT_TIMEFRAMES
            # (Future enhancement: read per‑mechanism constraints from mechanism metadata)

            for sym in symbols:
                for tf in timeframes:
                    # Skip blacklisted
                    if (mid, sym, tf) in self._blacklist:
                        continue
                    # Skip if already in queue with a final status
                    existing = next(
                        (e for e in self._queue
                         if e["mechanism_id"] == mid and e["symbol"] == sym and e["timeframe"] == tf),
                        None,
                    )
                    if existing and existing.get("status") in ("completed", "rejected"):
                        continue

                    # Compute cost estimate (simplified – 50k bars per experiment)
                    cost_estimate = 1.0  # unit cost; can be refined later
                    priority = default_priority(
                        mech,
                        n_assets=len(symbols),
                        n_regimes=3,  # trend, vol, volume
                        cost_estimate=cost_estimate,
                    )
                    entry = {
                        "mechanism_id": mid,
                        "symbol": sym,
                        "timeframe": tf,
                        "status": "pending",
                        "priority": round(priority, 6),
                        "last_run": None,
                        "result_summary": None,
                    }
                    # Update existing or append
                    if existing:
                        existing.update(entry)
                    else:
                        self._queue.append(entry)

        self._save_queue()

    # ── Prioritisation ──────────────────────────────────────────────────────

    def schedule(
        self,
        priority_fn: Optional[Callable[[Dict[str, Any]], float]] = None,
        max_experiments: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Sort the pending queue by priority (descending) and return up to *max_experiments*
        of the highest‑priority experiments that are still pending and not blacklisted.

        *priority_fn* may modify the priority score per entry.
        """
        pending = [
            e for e in self._queue
            if e.get("status") == "pending" and (e["mechanism_id"], e["symbol"], e["timeframe"]) not in self._blacklist
        ]
        if priority_fn is not None:
            for e in pending:
                e["priority"] = round(priority_fn(e), 6)

        pending.sort(key=lambda x: x["priority"], reverse=True)
        return pending[:max_experiments]

    # ── Execution ───────────────────────────────────────────────────────────

    def run_cycle(
        self,
        budget: int = 3,
        priority_fn: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run one full scheduling‑execution cycle.

        Returns list of result summaries.
        """
        if not self._queue:
            self.generate_candidates()

        batch = self.schedule(priority_fn=priority_fn, max_experiments=budget)
        results = []
        for exp in batch:
            res = self._run_experiment(exp)
            results.append(res)
            self._save_queue()
            self.registry.save()
            self.ladder.save()
        return results

    def _run_experiment(self, exp: Dict[str, Any]) -> Dict[str, Any]:
        mid = exp["mechanism_id"]
        symbol = exp["symbol"]
        timeframe = exp["timeframe"]

        logger.info("Running experiment: %s on %s/%s", mid, symbol, timeframe)
        exp["last_run"] = datetime.now(timezone.utc).isoformat()

        mech = self.registry.get(mid)
        if mech is None:
            exp["status"] = "skipped"
            exp["result_summary"] = "Unknown mechanism"
            return exp

        # Obtain trigger
        trigger_info = trigger_for_mechanism(mech, symbol, timeframe)
        if trigger_info is None:
            exp["status"] = "skipped"
            exp["result_summary"] = "No trigger mapping available"
            return exp
        trig_name, condition_fn = trigger_info

        try:
            study = EventStudy(symbol, timeframe, max_bars=50000)
            study.add_trigger(trig_name, condition_fn)
            df = study.load_data()
            df = study.compute_features(df)
            results = study.run(df=df)
        except Exception as exc:
            logger.error("Experiment failed: %s", exc)
            exp["status"] = "error"
            exp["result_summary"] = str(exc)[:200]
            return exp

        if not results:
            exp["status"] = "skipped"
            exp["result_summary"] = "No events generated"
            return exp

        best = study.best_result() or results[0]
        # Build summary
        summary = {
            "trigger": trig_name,
            "n_events": best.n_events,
            "significant_horizons": best.significant_horizons,
            "best_horizon": min(best.significant_horizons, key=lambda h: best.t_pvalue.get(h, 1)) if best.significant_horizons else None,
            "best_p": min(best.t_pvalue.values()) if best.t_pvalue else 1.0,
            "best_mean_bp": (best.mean_return.get(
                min(best.significant_horizons, key=lambda h: best.t_pvalue.get(h, 1))
            ) * 10000) if best.significant_horizons else 0.0,
        }

        # ── Stopping rules ──────────────────────────────────────────────────
        # Reject if: (a) no significant horizon, or (b) best p > 0.2 AND effect < 5 bp
        reject = False
        if not best.significant_horizons:
            if summary["best_p"] > 0.2 and abs(summary["best_mean_bp"]) < 5.0 and best.n_events > 10:
                reject = True
        if reject:
            self._blacklist.add((mid, symbol, timeframe))
            exp["status"] = "rejected"
            exp["result_summary"] = summary
            logger.info("Experiment %s/%s/%s rejected (stopping rule)", mid, symbol, timeframe)
        else:
            exp["status"] = "completed"
            exp["result_summary"] = summary

        # ── Update mechanism (effect summary) ───────────────────────────────
        if best.significant_horizons:
            best_h = min(best.significant_horizons, key=lambda h: best.t_pvalue.get(h, 1))
            # Store per‑asset effect
            if symbol not in mech.effect_summary:
                mech.effect_summary[symbol] = {}
            mech.effect_summary[symbol].update({
                "horizon": best_h,
                "mean_bp": round(summary["best_mean_bp"], 2),
                "p_value": summary["best_p"],
            })

        # Update ladder: create/update a hypothesis record for the mechanism experiment
        hypo_id = f"{mid}_{symbol}_{timeframe}"
        record = self.ladder.get(hypo_id)
        if record is None:
            record = HypothesisRecord(
                hypothesis_id=hypo_id,
                name=f"{mech.name} on {symbol}/{timeframe}",
                family="MechanismValidation",
                description=f"Automated event study for {mid}",
                economic_rationale=mech.economic_rationale,
                evidence_level=EvidenceLevel.L0,
                symbols=[symbol],
                timeframes=[timeframe],
                tags=["auto", "event_study", mid, symbol, timeframe],
            )
            self.ladder.register(record)

        stage_result = StageResult(
            stage=2,  # In-sample discovery (approximation)
            name="EventStudy",
            passed=bool(best.significant_horizons),
            notes=f"Best p={summary['best_p']:.4f}, mean={summary['best_mean_bp']:.1f} bp",
        )
        if best.significant_horizons:
            record.promote(EvidenceLevel.L1, stage_result)
        else:
            record.demote("Event study no significant horizon", 2)

        return exp

# ── Quick entry point ────────────────────────────────────────────────────────
def main():
    scheduler = ExperimentScheduler()
    scheduler.generate_candidates()
    print(f"Queue size: {len(scheduler._queue)}")
    results = scheduler.run_cycle(budget=2)
    for r in results:
        print(f"{r['mechanism_id']} {r['symbol']}/{r['timeframe']} -> {r['status']}: {r.get('result_summary')}")

if __name__ == "__main__":
    main()

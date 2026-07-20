"""
Experiment Scheduler — Generic, budget-aware discovery loop with Bayesian
belief tracking, exploration/exploitation, autonomous replication, and
automated promotion once posterior evidence exceeds a threshold.

Automates the cycle:
    queue → prioritise → execute → update evidence → replicate → auto‑advance → repeat

Pluggable priority policies, stopping rules, and mechanism-specific
trigger factories live here (or in companion modules). The scheduler
itself does **not** contain any research logic — it only orchestrates
existing components (EventStudy, MechanismRegistry, EvidenceLadder).

Version 9 adds:
- Dormant state replaces permanent blacklisting: failed experiments
  are deferred for a configurable period and automatically become
  re‑eligible afterwards.
- Research‑debt tracking: experiments that require more data,
  a different exchange, or an alternative trigger are recorded
  so that they can be revisited later.
- Promotion is evidence‑based: a mechanism auto‑advances only when its
  pooled posterior probability that the true effect exceeds the
  economic threshold surpasses a configurable level, rather than
  when a predetermined number of assets are replicated.

Usage
-----
    from src.core.experiment_scheduler import ExperimentScheduler

    scheduler = ExperimentScheduler()
    scheduler.run_cycle(budget=3)
    # Advance a mechanism that has gathered cross‑asset replications:
    scheduler.run_advancement_checks("M002")
"""

from __future__ import annotations

import json
import logging
import math
import random
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.core.evidence_ladder import (
    EvidenceLadder, EvidenceLevel, HypothesisRecord, StageResult
)
from src.core.mechanism_registry import (
    Mechanism, MechanismRegistry, registry as _registry
)
from src.core.dataset_registry import registry as _data_registry
from src.validation.event_study import EventStudy, EventStudyResult
from src.backtest.signal_source import CallableSignalSource, BacktestSignal
from scripts.evaluate_strategies import run_walk_forward   # existing walk‑forward function

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Trigger Factory — maps mechanism → event‑study condition callable
# ═══════════════════════════════════════════════════════════════════════════════

_TRIGGER_BUILDERS: Dict[str, Callable[[], Tuple[str, Callable]]] = {}
"""Registry of trigger builders. Each callable returns (trigger_name, condition_fn)."""


def _register_trigger(mech_id: str, builder: Callable):
    _TRIGGER_BUILDERS[mech_id] = builder


def trigger_for_mechanism(
    mechanism: Mechanism, symbol: str, timeframe: str
) -> Optional[Tuple[str, Callable]]:
    """Return (trigger_name, condition_fn) for the given mechanism, or None."""
    build = _TRIGGER_BUILDERS.get(mechanism.mechanism_id)
    if build is None:
        return None
    try:
        return build()
    except Exception:
        logger.warning("Trigger builder for %s failed.", mechanism.mechanism_id)
        return None


# ── Built-in triggers ────────────────────────────────────────────────────────
def _m001_trigger() -> Tuple[str, Callable]:
    return ("z_overbought_2.5", lambda df: df["z_score"] > 2.5)

_register_trigger("M001", _m001_trigger)

def _m002_trigger() -> Tuple[str, Callable]:
    def condition(df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        roc = (close - close.shift(5)) / close.shift(5)
        return roc > 0.005
    return ("roc_5_pos", condition)

_register_trigger("M002", _m002_trigger)


# ── Multi‑trigger variants ──────────────────────────────────────────────────
# Key: mechanism_id → list of (trigger_name, condition_fn)
# These will be added as separate queue entries.
_MECHANISM_TRIGGER_VARIANTS: Dict[str, List[Tuple[str, Callable]]] = {
    "M003": [
        (
            "oi_div_bearish",
            lambda df: (df["close"] > df["sma20"])
            & (df["sum_open_interest"] < df["sum_open_interest"].rolling(20).mean()),
        ),
        (
            "oi_div_bullish",
            lambda df: (df["close"] < df["sma20"])
            & (df["sum_open_interest"] > df["sum_open_interest"].rolling(20).mean()),
        ),
    ],
    "M004": [
        (
            "funding_over_2p0",
            lambda df: (
                (df["funding_rate"].rolling(100).std() > 0)
                & ((df["funding_rate"] - df["funding_rate"].rolling(100).mean())
                   / df["funding_rate"].rolling(100).std() > 2.0)
            ),
        ),
        (
            "funding_under_neg2p0",
            lambda df: (
                (df["funding_rate"].rolling(100).std() > 0)
                & ((df["funding_rate"] - df["funding_rate"].rolling(100).mean())
                   / df["funding_rate"].rolling(100).std() < -2.0)
            ),
        ),
    ],
    "M005": [
        (
            "vol_comp_low",
            lambda df: df["atr_percentile"] < 0.33,
        ),
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Bayesian Belief State
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BeliefState:
    """
    Per‑combination (mechanism, symbol, timeframe) Bayesian belief about the
    effect size (μ).  We assume μ ~ N(prior_mean, prior_var) and a Normal
    likelihood with known variance (sample variance).  The posterior is also
    Normal; this class stores the parameters needed to compute it.
    """
    prior_mean: float = 0.0          # prior mean (basis points)
    prior_var: float = 400.0         # prior variance (20 bp std)
    n: int = 0                       # number of observations
    sample_mean: float = 0.0         # sample mean (bp)
    sample_var: float = 0.0          # sample variance (bp**2)
    last_updated: str = ""

    @property
    def posterior_mean(self) -> float:
        if self.n == 0:
            return self.prior_mean
        prior_prec = 1.0 / max(self.prior_var, 1e-9)
        sample_prec = self.n / max(self.sample_var, 1e-9)
        return (prior_prec * self.prior_mean + sample_prec * self.sample_mean) / (prior_prec + sample_prec)

    @property
    def posterior_var(self) -> float:
        if self.n == 0:
            return self.prior_var
        prior_prec = 1.0 / max(self.prior_var, 1e-9)
        sample_prec = self.n / max(self.sample_var, 1e-9)
        return 1.0 / (prior_prec + sample_prec)

    def prob_effect_gt(self, threshold: float = 5.0) -> float:
        """Posterior probability that the true effect size (in bp) > threshold."""
        mu = self.posterior_mean
        sigma = math.sqrt(max(self.posterior_var, 1e-9))
        from math import erf
        def norm_sf(z):
            return 0.5 - 0.5 * erf(z / math.sqrt(2.0))
        if sigma == 0:
            return 1.0 if mu > threshold else 0.0
        z = (mu - threshold) / sigma
        return norm_sf(-z)

    def update(self, mean_bp: float, var_bp: float, n: int):
        """Update belief with a new experiment's results."""
        if n <= 0:
            return
        self.sample_mean = mean_bp
        self.sample_var = max(var_bp, 1e-6)
        self.n = n
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "prior_mean": self.prior_mean,
            "prior_var": self.prior_var,
            "n": self.n,
            "sample_mean": self.sample_mean,
            "sample_var": self.sample_var,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


# ═══════════════════════════════════════════════════════════════════════════════
#  Priority Policies
# ═══════════════════════════════════════════════════════════════════════════════

def default_priority(
    mechanism: Mechanism,
    n_assets: int,
    n_regimes: int,
    cost_estimate: float,
    belief_prob: Optional[float] = None,
) -> float:
    """
    Default information‑gain priority.

    If *belief_prob* is provided (posterior probability that effect > 5 bp),
    the information gap is 1 - belief_prob.  Otherwise the gap is based on the
    mechanism's global confidence score.
    """
    if belief_prob is not None:
        info_gap = 1.0 - belief_prob
    else:
        confidence = mechanism.confidence_score() if mechanism else 0.0
        info_gap = 1.0 - confidence

    asset_bonus = math.log2(n_assets + 1)
    regime_bonus = math.log2(n_regimes + 1)
    return info_gap * (asset_bonus + regime_bonus) / max(cost_estimate, 1e-3)


# ═══════════════════════════════════════════════════════════════════════════════
#  Experiment Scheduler
# ═══════════════════════════════════════════════════════════════════════════════

class ExperimentScheduler:
    """
    Generic experiment scheduler with Bayesian belief tracking,
    autonomous replication, and evidence‑based promotion.

    Responsibilities
    ----------------
    - Build a queue of (mechanism, symbol, timeframe) experiments.
    - Prioritise queue via a pluggable policy function.
    - Execute experiments using EventStudy, respecting a per‑cycle budget.
    - Update the mechanism registry and evidence ladder with results.
    - Apply stopping rules: failures become DORMANT for a configurable period.
      Dormant experiments may be re‑tested later, rather than being permanently
      excluded.
    - Maintain a per‑combination belief state for Bayesian evidence accumulation.
    - Automatically schedule replication experiments for significant results.
    - When a mechanism’s pooled posterior probability that the true effect
      exceeds the economic threshold surpasses a configurable level, the
      scheduler triggers the advancement pipeline (null‑model + walk‑forward).
    - Register validated mechanisms as AlphaStreams for the AlphaEngine.
    - Track research debt: experiments that require more data, a different
      exchange, or an alternative trigger.

    """

    DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    DEFAULT_TIMEFRAMES = ["15m", "1h", "4h", "1d"]
    EXPLORATION_RATE = 0.2
    MIN_EFFECT_THRESHOLD_BP = 5.0         # economic threshold
    SIGNIFICANCE_THRESHOLD = 0.05         # p‑value gate
    REPLICATION_TIMEFRAMES = ["1h", "4h", "1d"]

    # Promotion is evidence‑based, not count‑based.
    ADVANCE_PROB_THRESHOLD = 0.9          # posterior P(μ > economic threshold)

    # Parameters for advancement checks
    DEFAULT_NULL_MODEL_ASSETS = ["ETHUSDT", "SOLUSDT", "BNBUSDT"]
    DEFAULT_NULL_MODEL_TF = "4h"
    DEFAULT_WF_WINDOWS = 6

    # Dormant experiments are ignored for DORMANT_PERIOD_DAYS, then re‑eligible.
    DORMANT_PERIOD_DAYS = 180

    # Mechanisms that require data enrichment (OI / funding)
    ENRICH_REQUIRED_MECHANISMS = {"M003", "M004"}

    # Mapping from mechanism ID to an AlphaEngine family name
    MECHANISM_FAMILY_MAP = {
        "M001": "MeanReversionAlpha",
        "M002": "MomentumAlpha",
        "M003": "PositioningAlpha",
        "M004": "PositioningAlpha",
        "M005": "ExpansionAlpha",
    }

    def __init__(
        self,
        ladder: Optional[EvidenceLadder] = None,
        registry: Optional[MechanismRegistry] = None,
        dataset_registry: Optional[Any] = None,
        queue_path: Optional[Path] = None,
        belief_path: Optional[Path] = None,
        debt_path: Optional[Path] = None,
    ):
        self.ladder = ladder or EvidenceLadder()
        self.ladder.load()
        self.registry = registry or _registry
        self.dataset_registry = dataset_registry or _data_registry
        self.queue_path = Path(queue_path or "data/experiments/research_queue.json")
        self.belief_path = Path(belief_path or "data/experiments/belief_state.json")
        self.debt_path = Path(debt_path or "data/experiments/research_debt.json")
        self._queue: List[Dict[str, Any]] = []
        # dormant experiments: key → dormant_until (Unix timestamp)
        self._dormant: Dict[Tuple[str, str, str, str], float] = {}
        self._beliefs: Dict[Tuple[str, str, str], BeliefState] = {}
        self._research_debt: List[Dict[str, Any]] = []
        self._load_queue()
        self._load_beliefs()
        self._load_debt()

    # ── Queue management ────────────────────────────────────────────────────

    def _load_queue(self):
        if not self.queue_path.exists():
            return
        try:
            data = json.loads(self.queue_path.read_text(encoding="utf-8"))
            self._queue = data.get("experiments", [])
            dorm = data.get("dormant", [])
            self._dormant = {
                (x[0], x[1], x[2], x[3]): x[4]
                for x in dorm if len(x) >= 5
            }
        except Exception as exc:
            logger.warning("Could not load research queue: %s", exc)

    def _save_queue(self):
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "experiments": self._queue,
            "dormant": [
                list(key) + [dormant_until]
                for key, dormant_until in self._dormant.items()
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.queue_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    @staticmethod
    def _exp_key(exp: Dict[str, Any]) -> Tuple[str, str, str, str]:
        return (
            exp["mechanism_id"],
            exp["symbol"],
            exp["timeframe"],
            exp.get("trigger_name", ""),
        )

    def _is_dormant(self, exp: Dict[str, Any]) -> bool:
        key = self._exp_key(exp)
        if key in self._dormant:
            return _time.time() < self._dormant[key]
        return False

    def _make_dormant(self, exp: Dict[str, Any], reason: str = ""):
        key = self._exp_key(exp)
        dormant_until = _time.time() + self.DORMANT_PERIOD_DAYS * 86400
        self._dormant[key] = dormant_until
        logger.info(
            "Experiment %s|%s|%s [%s] made dormant until %s: %s",
            key[0], key[1], key[2], key[3],
            datetime.utcfromtimestamp(dormant_until).isoformat(),
            reason,
        )

    def _reset_dormant(self, exp: Dict[str, Any]):
        key = self._exp_key(exp)
        self._dormant.pop(key, None)

    def generate_candidates(self):
        """Fill the queue with experiments for every mechanism‑symbol‑timeframe combination."""
        # Built‑in mechanisms (M001, M002, M004, M005)
        for mid, mech in self.registry._mechanisms.items():
            if mid.startswith("_") or mid in _MECHANISM_TRIGGER_VARIANTS:
                continue
            symbols = self.DEFAULT_SYMBOLS
            timeframes = self.DEFAULT_TIMEFRAMES

            for sym in symbols:
                for tf in timeframes:
                    exp = {
                        "mechanism_id": mid,
                        "symbol": sym,
                        "timeframe": tf,
                        "trigger_name": "",
                    }
                    if self._is_dormant(exp):
                        # re‑enrol if dormant period has expired
                        self._reset_dormant(exp)
                    existing = next(
                        (e for e in self._queue
                         if e["mechanism_id"] == mid and e["symbol"] == sym and e["timeframe"] == tf
                         and e.get("trigger_name", "") == ""),
                        None,
                    )
                    if existing and existing.get("status") in ("completed", "rejected"):
                        continue

                    cost_estimate = 1.0
                    belief = self._beliefs.get((mid, sym, tf))
                    prob = belief.prob_effect_gt(self.MIN_EFFECT_THRESHOLD_BP) if belief else None
                    priority = default_priority(
                        mech,
                        n_assets=len(symbols),
                        n_regimes=3,
                        cost_estimate=cost_estimate,
                        belief_prob=prob,
                    )
                    entry = {
                        "mechanism_id": mid,
                        "symbol": sym,
                        "timeframe": tf,
                        "trigger_name": "",
                        "status": "pending",
                        "priority": round(priority, 6),
                        "last_run": None,
                        "result_summary": None,
                    }
                    if existing:
                        existing.update(entry)
                    else:
                        self._queue.append(entry)

        # Multi‑trigger variants (M003, M004, M005)
        for mid, variants in _MECHANISM_TRIGGER_VARIANTS.items():
            symbols = self.DEFAULT_SYMBOLS
            timeframes = self.DEFAULT_TIMEFRAMES
            for sym in symbols:
                for tf in timeframes:
                    for tname, _cond in variants:
                        exp = {
                            "mechanism_id": mid,
                            "symbol": sym,
                            "timeframe": tf,
                            "trigger_name": tname,
                        }
                        if self._is_dormant(exp):
                            self._reset_dormant(exp)
                        existing = next(
                            (e for e in self._queue
                             if e["mechanism_id"] == mid and e["symbol"] == sym
                             and e["timeframe"] == tf and e.get("trigger_name", "") == tname),
                            None,
                        )
                        if existing and existing.get("status") in ("completed", "rejected"):
                            continue

                        mech = self.registry.get(mid)
                        cost_estimate = 1.0
                        belief = self._beliefs.get((mid, sym, tf))
                        prob = belief.prob_effect_gt(self.MIN_EFFECT_THRESHOLD_BP) if belief else None
                        priority = default_priority(
                            mech,
                            n_assets=len(symbols),
                            n_regimes=3,
                            cost_estimate=cost_estimate,
                            belief_prob=prob,
                        )
                        entry = {
                            "mechanism_id": mid,
                            "symbol": sym,
                            "timeframe": tf,
                            "trigger_name": tname,
                            "status": "pending",
                            "priority": round(priority, 6),
                            "last_run": None,
                            "result_summary": None,
                        }
                        if existing:
                            existing.update(entry)
                        else:
                            self._queue.append(entry)

        self._save_queue()

    # ── Belief state persistence ────────────────────────────────────────────

    def _load_beliefs(self):
        if not self.belief_path.exists():
            return
        try:
            data = json.loads(self.belief_path.read_text(encoding="utf-8"))
            for key_str, val in data.get("beliefs", {}).items():
                mid, sym, tf = key_str.split("|")
                self._beliefs[(mid, sym, tf)] = BeliefState.from_dict(val)
        except Exception as exc:
            logger.warning("Could not load belief state: %s", exc)

    def _save_beliefs(self):
        self.belief_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "beliefs": {
                f"{mid}|{sym}|{tf}": belief.to_dict()
                for (mid, sym, tf), belief in self._beliefs.items()
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.belief_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _update_belief(self, mid: str, sym: str, tf: str, mean_bp: float, var_bp: float, n: int):
        key = (mid, sym, tf)
        belief = self._beliefs.get(key, BeliefState())
        belief.update(mean_bp, var_bp, n)
        self._beliefs[key] = belief
        logger.info(
            "Belief updated: %s|%s|%s -> mean=%.1f bp, var=%.1f, n=%d, P(>5bp)=%.3f",
            mid, sym, tf, mean_bp, var_bp, n, belief.prob_effect_gt(self.MIN_EFFECT_THRESHOLD_BP),
        )

    # ── Research‑debt tracking ─────────────────────────────────────────────

    def _load_debt(self):
        if not self.debt_path.exists():
            return
        try:
            self._research_debt = json.loads(self.debt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not load research debt: %s", exc)

    def _save_debt(self):
        self.debt_path.parent.mkdir(parents=True, exist_ok=True)
        self.debt_path.write_text(json.dumps(self._research_debt, indent=2, default=str), encoding="utf-8")

    def _add_research_debt(self, exp: Dict[str, Any], reason: str):
        entry = {
            "mechanism_id": exp["mechanism_id"],
            "symbol": exp["symbol"],
            "timeframe": exp["timeframe"],
            "trigger_name": exp.get("trigger_name", ""),
            "reason": reason,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._research_debt.append(entry)
        self._save_debt()
        logger.info("Research debt recorded: %s|%s|%s [%s] – %s",
                    exp["mechanism_id"], exp["symbol"], exp["timeframe"],
                    exp.get("trigger_name", ""), reason)

    # ── Data enrichment (OI / funding) ─────────────────────────────────────

    def _enrich_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Add Open Interest and/or funding columns for mechanisms that require them."""
        try:
            from src.features.positioning_enricher import enrich_ohlcv, clear_cache
            clear_cache()
            df = enrich_ohlcv(df, symbol)
            logger.info("Data enrichment succeeded for %s (%d rows)", symbol, len(df))
            return df
        except Exception as exc:
            logger.warning("Data enrichment failed for %s: %s", symbol, exc)
            return df  # proceed without enrichment; triggers will likely fail gracefully

    # ── Prioritisation ──────────────────────────────────────────────────────

    def schedule(
        self,
        priority_fn: Optional[Callable[[Dict[str, Any]], float]] = None,
        max_experiments: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return up to *max_experiments* pending experiments, highest‑priority first."""
        pending = [
            e for e in self._queue
            if e.get("status") == "pending"
            and not self._is_dormant(e)
        ]
        if priority_fn is not None:
            for e in pending:
                e["priority"] = round(priority_fn(e), 6)

        pending.sort(key=lambda x: x["priority"], reverse=True)

        # Exploration: with some probability, insert a random pending experiment
        if pending and random.random() < self.EXPLORATION_RATE:
            idx = random.randrange(len(pending))
            exp = pending.pop(idx)
            pending.insert(0, exp)

        return pending[:max_experiments]

    # ── Execution ───────────────────────────────────────────────────────────

    def run_cycle(
        self,
        budget: int = 3,
        priority_fn: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """Run one full scheduling‑execution cycle, then auto‑advance ready mechanisms."""
        if not self._queue:
            self.generate_candidates()

        batch = self.schedule(priority_fn=priority_fn, max_experiments=budget)
        results = []
        for exp in batch:
            res = self._run_experiment(exp)
            results.append(res)
            self._save_queue()
            self._save_beliefs()
            self.registry.save()
            self.ladder.save()

        # After processing the batch, attempt to advance any mechanism whose
        # pooled posterior evidence exceeds the promotion threshold.
        self._auto_advance_mechanisms()

        return results

    def _run_experiment(self, exp: Dict[str, Any]) -> Dict[str, Any]:
        mid = exp["mechanism_id"]
        symbol = exp["symbol"]
        timeframe = exp["timeframe"]
        trigger_name = exp.get("trigger_name", "")

        logger.info("Running experiment: %s on %s/%s (%s)", mid, symbol, timeframe, trigger_name or "default")
        exp["last_run"] = datetime.now(timezone.utc).isoformat()

        mech = self.registry.get(mid)
        if mech is None:
            exp["status"] = "skipped"
            exp["result_summary"] = "Unknown mechanism"
            return exp

        # Resolve trigger callable
        if trigger_name:
            variants = _MECHANISM_TRIGGER_VARIANTS.get(mid, [])
            cond_fn = None
            for tname, fn in variants:
                if tname == trigger_name:
                    cond_fn = fn
                    break
            if cond_fn is None:
                exp["status"] = "skipped"
                exp["result_summary"] = f"No trigger variant '{trigger_name}' for {mid}"
                return exp
            trig_name_display = trigger_name
        else:
            trigger_info = trigger_for_mechanism(mech, symbol, timeframe)
            if trigger_info is None:
                exp["status"] = "skipped"
                exp["result_summary"] = "No trigger mapping available"
                return exp
            trig_name_display, cond_fn = trigger_info

        # Prepare data
        try:
            study = EventStudy(symbol, timeframe, max_bars=50000)
            df = study.load_data()
            df = study.compute_features(df)

            # Enrich with OI / funding if needed
            if mid in self.ENRICH_REQUIRED_MECHANISMS:
                df = self._enrich_data(df, symbol)
                df = study.compute_features(df)  # re‑compute after enrichment

            study.add_trigger(trig_name_display, cond_fn)
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
        # Determine best horizon for summary and belief update
        if best.significant_horizons:
            best_h = min(best.significant_horizons, key=lambda h: best.t_pvalue.get(h, 1))
        else:
            # fallback to horizon with lowest p-value
            best_h = min(best.t_pvalue.keys(), key=lambda h: best.t_pvalue[h]) if best.t_pvalue else 5

        mean_return = best.mean_return.get(best_h, 0.0)
        ci_low = best.bootstrap_ci_lower.get(best_h, mean_return)
        ci_high = best.bootstrap_ci_upper.get(best_h, mean_return)
        std_return = best.std_return.get(best_h, 0.0)
        n_events = best.n_events
        p_val = best.t_pvalue.get(best_h, 1.0)

        mean_bp = mean_return * 10000.0
        ci_low_bp = ci_low * 10000.0
        ci_high_bp = ci_high * 10000.0
        std_bp = std_return * 10000.0

        # Use raw returns for variance estimation if available
        eff_var_bp = (std_bp ** 2) if std_bp > 0 else 1.0
        if best_h in best.raw_returns:
            raw = best.raw_returns[best_h]
            if len(raw) > 0:
                eff_var_bp = float(np.var(raw) * 1e8)  # log-return variance → bp²

        summary = {
            "trigger": trig_name_display,
            "n_events": n_events,
            "significant_horizons": best.significant_horizons,
            "best_horizon": best_h if best.significant_horizons else None,
            "best_p": p_val,
            "best_mean_bp": round(mean_bp, 2),
            "best_ci_low_bp": round(ci_low_bp, 2),
            "best_ci_high_bp": round(ci_high_bp, 2),
            "best_std_bp": round(std_bp, 2),
        }

        # ── Stopping rules ──────────────────────────────────────────────────
        reject = False
        if not best.significant_horizons:
            if p_val > 0.2 and abs(mean_bp) < 5.0 and n_events > 10:
                reject = True
        if reject:
            # Mark as dormant rather than permanently blacklisted
            self._make_dormant(exp, reason="No significant predictive power")
            exp["status"] = "dormant"
            exp["result_summary"] = summary
            logger.info("Experiment %s/%s/%s [%s] parked as dormant", mid, symbol, timeframe, trigger_name)
        else:
            exp["status"] = "completed"
            exp["result_summary"] = summary

        # ── Update mechanism effect summary ─────────────────────────────────
        effect_key = f"{symbol}_{timeframe}_{trigger_name}".rstrip("_")
        if effect_key not in mech.effect_summary:
            mech.effect_summary[effect_key] = {}
        mech.effect_summary[effect_key].update({
            "symbol": symbol,
            "timeframe": timeframe,
            "trigger": trig_name_display,
            "horizon": best_h,
            "mean_bp": round(mean_bp, 2),
            "ci_low_bp": round(ci_low_bp, 2),
            "ci_high_bp": round(ci_high_bp, 2),
            "std_bp": round(std_bp, 2),
            "n_events": n_events,
            "p_value": p_val,
        })

        # ── Update belief state ─────────────────────────────────────────────
        self._update_belief(mid, symbol, timeframe, mean_bp, eff_var_bp, n_events)

        # ── Update evidence ladder ──────────────────────────────────────────
        hypo_id = f"{mid}_{symbol}_{timeframe}_{trigger_name}".rstrip("_")
        record = self.ladder.get(hypo_id)
        if record is None:
            record = HypothesisRecord(
                hypothesis_id=hypo_id,
                name=f"{mech.name} on {symbol}/{timeframe} ({trig_name_display})",
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
            stage=2,
            name="EventStudy",
            passed=bool(best.significant_horizons),
            notes=f"Best p={p_val:.4f}, mean={mean_bp:.1f} bp, CI=[{ci_low_bp:.1f}, {ci_high_bp:.1f}]",
        )
        if best.significant_horizons:
            record.promote(EvidenceLevel.L1, stage_result)
        else:
            record.demote("Event study no significant horizon", 2)

        # ── Autonomous replication ──────────────────────────────────────────
        # For multi‑trigger variants, only schedule replications for the same variant
        if best.significant_horizons:
            self._schedule_replications(exp, p_val, mean_bp)

        # ── Research‑debt assessment ────────────────────────────────────────
        if best.significant_horizons:
            if (ci_high_bp - ci_low_bp) > 100:
                self._add_research_debt(exp, "large_confidence_interval")
        else:
            if abs(mean_bp) > 10 and n_events > 10:
                self._add_research_debt(exp, "large_effect_not_significant")

        # ── Update mechanism cross‑asset counts ─────────────────────────────
        self._update_mechanism_counts(mech)

        return exp

    # ── Replication scheduling ──────────────────────────────────────────────

    def _schedule_replications(self, original: Dict[str, Any], p_val: float, mean_bp: float):
        """If the original experiment was significant, enqueue replications on other assets
        at the same timeframe and, optionally, at other timeframes."""
        if p_val >= self.SIGNIFICANCE_THRESHOLD:
            return
        mid = original["mechanism_id"]
        sym = original["symbol"]
        tf = original["timeframe"]
        trigger_name = original.get("trigger_name", "")
        if mean_bp < self.MIN_EFFECT_THRESHOLD_BP:
            return

        logger.info(
            "Significant result found for %s|%s|%s [%s] — scheduling replications.",
            mid, sym, tf, trigger_name,
        )

        # 1. Same timeframe, other symbols
        for other_sym in self.DEFAULT_SYMBOLS:
            if other_sym == sym:
                continue
            self._ensure_experiment(mid, other_sym, tf, parent_id=f"{mid}_{sym}_{tf}", trigger_name=trigger_name)

        # 2. Other timeframes for the same symbol (optional — to map D019 scaling)
        for other_tf in self.REPLICATION_TIMEFRAMES:
            if other_tf == tf:
                continue
            self._ensure_experiment(mid, sym, other_tf, parent_id=f"{mid}_{sym}_{tf}", trigger_name=trigger_name)

        self._save_queue()

    def _ensure_experiment(self, mechanism_id: str, symbol: str, timeframe: str, parent_id: str,
                           trigger_name: str = ""):
        """Add a pending experiment for the given combination unless already present or dormant."""
        key = (mechanism_id, symbol, timeframe, trigger_name)
        if key in self._dormant:
            # reschedule even if dormant? The replication request bypasses dormancy.
            self._reset_dormant({"mechanism_id": mechanism_id, "symbol": symbol,
                                 "timeframe": timeframe, "trigger_name": trigger_name})
        existing = next(
            (e for e in self._queue
             if e["mechanism_id"] == mechanism_id
             and e["symbol"] == symbol
             and e["timeframe"] == timeframe
             and e.get("trigger_name", "") == trigger_name),
            None,
        )
        if existing and existing.get("status") in ("completed", "rejected", "dormant", "pending"):
            return

        mech = self.registry.get(mechanism_id)
        cost_estimate = 1.0
        belief = self._beliefs.get((mechanism_id, symbol, timeframe))
        prob = belief.prob_effect_gt(self.MIN_EFFECT_THRESHOLD_BP) if belief else None
        priority = default_priority(
            mech,
            n_assets=len(self.DEFAULT_SYMBOLS),
            n_regimes=3,
            cost_estimate=cost_estimate,
            belief_prob=prob,
        )
        entry = {
            "mechanism_id": mechanism_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "trigger_name": trigger_name,
            "status": "pending",
            "priority": round(priority, 6),
            "last_run": None,
            "result_summary": None,
            "replication_of": parent_id,
        }
        self._queue.append(entry)
        logger.info(
            "Replication enqueued: %s|%s|%s [%s] (parent %s)",
            mechanism_id, symbol, timeframe, trigger_name, parent_id,
        )

    # ── Mechanism cross‑asset count tracking ────────────────────────────────

    def _update_mechanism_counts(self, mech: Mechanism):
        """
        Scan the mechanism’s effect_summary and update n_assets_replicated,
        n_assets_tested based on significant results.
        """
        replicated = set()
        tested = set()
        for key, val in mech.effect_summary.items():
            sym = val.get("symbol", key.split("_")[0])
            tested.add(sym)
            p = val.get("p_value", 1.0)
            mean_bp = val.get("mean_bp", 0.0)
            if p < self.SIGNIFICANCE_THRESHOLD and mean_bp > self.MIN_EFFECT_THRESHOLD_BP:
                replicated.add(sym)
        mech.n_assets_replicated = len(replicated)
        mech.n_assets_tested = len(tested)
        logger.info("Mechanism %s cross‑asset counts updated: replicated=%d, tested=%d",
                    mech.mechanism_id, mech.n_assets_replicated, mech.n_assets_tested)

    # ═══════════════════════════════════════════════════════════════════════════
    #  Evidence‑based advancement
    # ═══════════════════════════════════════════════════════════════════════════

    def _mechanism_posterior_prob(self, mechanism_id: str, threshold: float = 5.0) -> float:
        """
        Pooled posterior probability that the mechanism’s true effect exceeds *threshold*.

        Combines all per‑combination effect‑summary entries (using their
        sample mean, variance, and event counts) with the standard Normal prior.
        """
        mech = self.registry.get(mechanism_id)
        if mech is None or not mech.effect_summary:
            return 0.0

        prior_prec = 1.0 / 400.0   # same prior as BeliefState
        total_prec = prior_prec
        weighted_sum = 0.0

        for key, val in mech.effect_summary.items():
            mean_bp = val.get("mean_bp", 0.0)
            std_bp = val.get("std_bp", 10.0)
            n = val.get("n_events", 0)
            if n == 0:
                continue
            var = max(std_bp ** 2, 1e-6)
            prec = n / var
            total_prec += prec
            weighted_sum += prec * mean_bp

        posterior_mean = weighted_sum / total_prec
        posterior_sd = math.sqrt(1.0 / total_prec)

        from math import erf
        def norm_sf(z):
            return 0.5 - 0.5 * erf(z / math.sqrt(2.0))
        z = (posterior_mean - threshold) / max(posterior_sd, 1e-9)
        return norm_sf(-z)

    def _auto_advance_mechanisms(self):
        """Check every mechanism’s pooled posterior probability and run advancement
        checks if it exceeds the promotion threshold."""
        for mid, mech in self.registry._mechanisms.items():
            if mid.startswith("_"):
                continue
            prob = self._mechanism_posterior_prob(mid, self.MIN_EFFECT_THRESHOLD_BP)
            logger.info(
                "Mechanism %s pooled P(μ>%dbp)=%.4f (threshold %.2f)",
                mid, self.MIN_EFFECT_THRESHOLD_BP, prob, self.ADVANCE_PROB_THRESHOLD,
            )
            if prob < self.ADVANCE_PROB_THRESHOLD:
                continue
            # Skip if null‑model gate already passed and walk‑forward was already run
            if mech.null_model_beaten and mech.n_wf_windows_total > 0:
                continue
            logger.info("Evidence threshold met for %s (pooled prob=%.4f). Running advancement checks.",
                        mid, prob)
            self.run_advancement_checks(mid)

    # ═══════════════════════════════════════════════════════════════════════════
    #  Advancement Checks — null‑model gate + walk‑forward → L3 promotion
    # ═══════════════════════════════════════════════════════════════════════════

    def run_advancement_checks(self, mechanism_id: str, symbols: Optional[List[str]] = None,
                               timeframe: Optional[str] = None, n_wf_windows: int = 6):
        """
        Run null‑model gate and walk‑forward validation for *mechanism_id*.
        If both checks pass, promote the mechanism to L3 in the evidence ladder
        and update the mechanism registry confidence components.
        """
        mech = self.registry.get(mechanism_id)
        if mech is None:
            logger.error("Advancement: unknown mechanism %s", mechanism_id)
            return

        symbols = symbols or self.DEFAULT_NULL_MODEL_ASSETS
        timeframe = timeframe or self.DEFAULT_NULL_MODEL_TF

        # --- null‑model gate ---
        logger.info("Advancement: null‑model gate for %s on %s / %s", mechanism_id, symbols, timeframe)
        beaten_assets = 0
        for sym in symbols:
            if self._check_null_model(mech, sym, timeframe):
                beaten_assets += 1
        null_passed = beaten_assets >= max(2, len(symbols) // 2)  # majority
        logger.info("Advancement: null‑model beaten on %d/%d assets", beaten_assets, len(symbols))

        # --- walk‑forward validation ---
        logger.info("Advancement: walk‑forward validation for %s on %s / %s", mechanism_id, symbols, timeframe)
        total_passed = 0
        total_windows = 0
        for sym in symbols:
            passed, total = self._run_walk_forward_check(mech, sym, timeframe, n_wf_windows)
            total_passed += passed
            total_windows += total
        wf_passed = total_passed >= 2  # at least 2 positive folds across all assets

        # --- update mechanism registry ---
        mech.null_model_beaten = null_passed
        mech.n_wf_windows_passed = total_passed
        mech.n_wf_windows_total = total_windows
        if null_passed and wf_passed:
            mech.acceptance_level = 4  # Walk‑Forward Validated
            logger.info("Advancement: %s promoted to acceptance level 4", mechanism_id)
        else:
            logger.warning("Advancement: %s did not meet L3 thresholds", mechanism_id)
        self.registry.save()

        # --- promote evidence‑ladder hypothesis for the mechanism itself ---
        record = self.ladder.get(mechanism_id)
        if record:
            target_level = EvidenceLevel.L3 if (null_passed and wf_passed) else record.evidence_level
            if target_level > record.evidence_level:
                stage_result = StageResult(
                    stage=3,
                    name="AdvancementChecks",
                    passed=True,
                    notes=f"Null‑model={null_passed}, WF positive folds={total_passed}/{total_windows}",
                )
                record.promote(target_level, stage_result)
                self.ladder.save()
                logger.info("Advancement: %s promoted to L%d in evidence ladder", mechanism_id, target_level.value)
            else:
                logger.info("Advancement: %s already at or above L%d", mechanism_id, record.evidence_level.value)
        else:
            logger.warning("Advancement: no ladder record for %s", mechanism_id)

        # --- auto‑register as AlphaStream if L3 reached ---
        if null_passed and wf_passed:
            self._maybe_register_alpha_stream(mechanism_id)

    # ── null‑model comparison per asset ─────────────────────────────────────

    def _check_null_model(self, mech: Mechanism, symbol: str, timeframe: str) -> bool:
        """Return True if the mechanism produces a better (and significant) forward return
        than a naive `close > SMA20` trigger at the mechanism’s best horizon."""
        trigger_info = trigger_for_mechanism(mech, symbol, timeframe)
        if trigger_info is None:
            logger.warning("Null‑model: no trigger for %s|%s|%s", mech.mechanism_id, symbol, timeframe)
            return False
        trig_name, cond_fn = trigger_info

        # run event study for mechanism trigger
        try:
            study = EventStudy(symbol, timeframe, max_bars=50000)
            study.add_trigger(trig_name, cond_fn)
            df = study.load_data()
            df = study.compute_features(df)
            # also add naive trigger
            study.add_trigger("naive_close_gt_sma20",
                              lambda d: d["close"] > d["sma20"])
            results = study.run(df=df)
        except Exception as exc:
            logger.error("Null‑model study failed for %s|%s|%s: %s",
                         mech.mechanism_id, symbol, timeframe, exc)
            return False

        # extract best horizon result for mechanism
        mech_res = next((r for r in results if r.trigger_name == trig_name), None)
        naive_res = next((r for r in results if r.trigger_name == "naive_close_gt_sma20"), None)
        if mech_res is None or naive_res is None:
            return False

        # find best horizon for mechanism based on lowest p‑value among significant ones
        best_mech_h = None
        best_mech_p = 1.0
        for h in mech_res.horizons:
            p = mech_res.t_pvalue.get(h, 1.0)
            if p < best_mech_p and h in mech_res.significant_horizons:
                best_mech_p = p
                best_mech_h = h
        if best_mech_h is None:
            # fallback to lowest p-value
            best_mech_h = min(mech_res.t_pvalue.keys(), key=lambda k: mech_res.t_pvalue[k])
        mech_mean_bp = mech_res.mean_return.get(best_mech_h, 0.0) * 10000.0

        # same for naive
        best_naive_h = min(naive_res.t_pvalue.keys(), key=lambda k: naive_res.t_pvalue[k]) if naive_res.t_pvalue else best_mech_h
        naive_mean_bp = naive_res.mean_return.get(best_naive_h, 0.0) * 10000.0

        # check: mechanism mean > naive mean **and** mechanism p < 0.05
        mech_sig = best_mech_p < 0.05
        better = mech_mean_bp > naive_mean_bp
        logger.info("Null‑model %s|%s|%s: mech=%.1f bp (p=%.4f) naive=%.1f bp → %s",
                    mech.mechanism_id, symbol, timeframe, mech_mean_bp, best_mech_p, naive_mean_bp,
                    "PASS" if (mech_sig and better) else "FAIL")
        return mech_sig and better

    # ── walk‑forward validation per asset ───────────────────────────────────

    def _run_walk_forward_check(self, mech: Mechanism, symbol: str, timeframe: str,
                                n_windows: int) -> Tuple[int, int]:
        """
        Run a walk‑forward backtest using the mechanism’s trigger as a simple
        long‑only signal. Returns (n_positive_folds, total_folds).
        """
        trigger_info = trigger_for_mechanism(mech, symbol, timeframe)
        if trigger_info is None:
            return 0, 0
        _, cond_fn = trigger_info

        # Build a signal function that goes long when the condition is true
        def signal_fn(symbol: str, window: pd.DataFrame, bar_index: int) -> BacktestSignal:
            # Re-compute features as the trigger (e.g. z_score) might rely on a full history
            window = EventStudy(symbol, timeframe, max_bars=50000).compute_features(window)
            mask = cond_fn(window)
            if not mask.empty and mask.iloc[-1]:
                return BacktestSignal(direction=1, proba_alpha=0.65, strategy_id=mech.mechanism_id)
            return BacktestSignal.flat()

        try:
            ohlcv = self.dataset_registry.get_ohlcv("binance", symbol, timeframe)
            if ohlcv is None:
                raise ValueError(f"No OHLCV data for {symbol}/{timeframe}")
            if "timestamp" not in ohlcv.columns:
                ohlcv = ohlcv.reset_index()
        except Exception as exc:
            logger.error("WF data load failed for %s/%s: %s", symbol, timeframe, exc)
            return 0, 0

        try:
            wf_result = run_walk_forward(ohlcv, signal_fn, n_windows=n_windows)
        except Exception as exc:
            logger.error("WF execution failed for %s/%s: %s", symbol, timeframe, exc)
            return 0, 0

        # run_walk_forward returns dict with:
        #   n_windows, ir_positive_prob, ir_per_fold, ...
        n_folds = wf_result.get("n_windows", n_windows)
        ir_per_fold = wf_result.get("ir_per_fold", [])
        positive_folds = sum(1 for v in ir_per_fold if v > 0)
        logger.info("WF %s/%s/%s: %d/%d positive folds",
                    mech.mechanism_id, symbol, timeframe, positive_folds, n_folds)
        return positive_folds, n_folds


    # ── AlphaEngine registration ────────────────────────────────────────────

    def _maybe_register_alpha_stream(self, mechanism_id: str) -> None:
        """
        If *mechanism_id* is not already recorded in
        ``data/experiments/alpha_streams.json``, create an AlphaStream entry
        from the mechanism’s current data and write it to that file.  The entry
        can later be loaded by the AlphaEngine.
        """
        from src.core.alpha_engine import AlphaEngine, AlphaStream

        alpha_path = Path("data/experiments/alpha_streams.json")
        registry_dict: Dict[str, dict] = {}
        if alpha_path.exists():
            try:
                registry_dict = json.loads(alpha_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        if mechanism_id in registry_dict:
            return

        mech = self.registry.get(mechanism_id)
        record = self.ladder.get(mechanism_id)
        if mech is None:
            return

        family = self.MECHANISM_FAMILY_MAP.get(mechanism_id, "Unknown")
        level = record.evidence_level if record else EvidenceLevel.L0

        # approximate expected return / vol from effect summaries
        return_sum = 0.15   # placeholder annual return
        vol_sum = 0.20      # placeholder annual vol
        # try to estimate from best effect
        best_score = -1.0
        for v in mech.effect_summary.values():
            mean_bp = v.get("mean_bp", 0)
            p_val = v.get("p_value", 1)
            score = abs(mean_bp) * (1 - p_val)
            if score > best_score:
                best_score = score
                if abs(mean_bp) > 0:
                    # crude: assume 10 trades per month ~ 120 per year
                    annualized = (mean_bp * 1e-4 * 120)
                    return_sum = max(annualized, 0.01)

        symbols = list({v["symbol"] for v in mech.effect_summary.values() if "symbol" in v})
        timeframes = list({v["timeframe"] for v in mech.effect_summary.values() if "timeframe" in v})

        stream_data = {
            "mechanism_id": mechanism_id,
            "name": mech.name,
            "family": family,
            "evidence_level": level.value,
            "expected_return": round(return_sum, 4),
            "expected_vol": vol_sum,
            "sharpe": round(return_sum / vol_sum if vol_sum else 0.0, 3),
            "symbols": symbols,
            "timeframes": timeframes,
        }
        # In a real deployment we would instantiate an AlphaStream and register
        # it in a live engine, but for headless operation we simply persist
        # the definition.
        try:
            alpha_path.parent.mkdir(parents=True, exist_ok=True)
            alpha_path.write_text(
                json.dumps(registry_dict | {mechanism_id: stream_data}, indent=2, default=str),
                encoding="utf-8"
            )
            logger.info("AlphaStream %s persisted to %s", mechanism_id, alpha_path)
        except Exception as exc:
            logger.error("Failed to write alpha stream: %s", exc)


# ── Quick entry point ───────────────────────────────────────────────────────
def main():
    scheduler = ExperimentScheduler()
    scheduler.generate_candidates()
    print(f"Queue size: {len(scheduler._queue)}")
    results = scheduler.run_cycle(budget=2)
    for r in results:
        print(
            f"{r['mechanism_id']} {r['symbol']}/{r['timeframe']} -> "
            f"{r['status']}: {r.get('result_summary')}"
        )


if __name__ == "__main__":
    main()

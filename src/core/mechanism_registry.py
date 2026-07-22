"""
Mechanism Registry — Reusable market mechanism catalog.

Instead of organizing research around named strategies (btc_mr_l2, eth_mom_l1),
organize around REUSABLE MECHANISMS that can be combined into many strategies.

A mechanism is a measurable market behavior:
  - What condition triggers it (inputs)
  - What it predicts (outputs)
  - Under what conditions it works (boundaries)
  - Why it exists (economic rationale)

Mechanisms are LONG-LIVED assets. Strategies are SHORT-LIVED combinations.
This registry separates the two.

Architecture:
    Mechanism (M001-M0XX)
        ↓
    Hypothesis (H071) = M001 + M003 + regime filter
        ↓
    Strategy (S014) = H071 + execution rules + risk management

Usage:
    from src.core.mechanism_registry import registry
    m = registry.get("M001")
    print(m.effect_summary())
    boundary = registry.find_boundary("M001", "BTCUSDT", "15m")
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# REMOVED: from src.core.experiment_scheduler import _m001_trigger, _m002_trigger

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Discovery Types
# ═══════════════════════════════════════════════════════════════════════════════

class DiscoveryType(str, Enum):
    """Classification of findings by permanence."""
    STRUCTURAL = "structural"   # Unlikely to change: BTC≠ETH, costs matter
    TACTICAL = "tactical"       # May evolve: regime thresholds, parameter values


@dataclass
class MechanismBoundary:
    """Where a mechanism stops working."""
    condition: str              # e.g. "ATR percentile > 67%"
    effect_size_bp: float       # mean log return in bp outside boundary
    events_inside: int
    events_outside: int
    p_value: float


@dataclass
class StabilityMetrics:
    """Rolling-window stability of a mechanism's effect."""
    rolling_6m_sharpe: List[float] = field(default_factory=list)
    rolling_6m_mean_bp: List[float] = field(default_factory=list)
    bootstrap_variance: float = 0.0
    effect_persistence: float = 0.0  # autocorrelation of rolling effect


@dataclass
class BoundaryModel:
    """Explicit boundary conditions for a mechanism."""
    model_id: str
    asset: str
    atr_range: Tuple[float, float]
    timeframe: str
    trend_condition: str
    funding_condition: str
    confidence: float


@dataclass
class Mechanism:
    """
    A reusable market mechanism.

    Attributes
    ----------
    mechanism_id : str
        e.g. "M001"
    name : str
        Human-readable name
    description : str
        What the mechanism is
    economic_rationale : str
        Why it should exist
    discovery_type : DiscoveryType
        STRUCTURAL or TACTICAL
    inputs : List[str]
        Required input features (e.g. ["z_score", "atr_percentile"])
    trigger_fn : Optional[Callable]
        Function(df) → boolean Series (True where mechanism activates)
    effect_summary : Dict
        Per-asset effect sizes at best horizon
        e.g. {"BTCUSDT": {"horizon": 5, "mean_bp": 3.6, "p_value": 0.22}}
    boundaries : List[MechanismBoundary]
        Where it stops working
    stability : Optional[StabilityMetrics]
        Rolling window stability
    used_by_hypotheses : List[str]
        Which hypotheses use this mechanism
    falsification_criteria : List[str]
        Conditions under which the mechanism is considered failed
    boundary_models : Dict[str, BoundaryModel]
        Explicit boundary models for specific assets/conditions
    """

    mechanism_id: str
    name: str
    description: str = ""
    economic_rationale: str = ""
    discovery_type: DiscoveryType = DiscoveryType.TACTICAL
    inputs: List[str] = field(default_factory=list)
    trigger_fn: Optional[Callable] = None
    effect_summary: Dict[str, Dict] = field(default_factory=dict)
    boundaries: List[MechanismBoundary] = field(default_factory=list)
    stability: Optional[StabilityMetrics] = None
    used_by_hypotheses: List[str] = field(default_factory=list)
    falsification_criteria: List[str] = field(default_factory=list)
    boundary_models: Dict[str, BoundaryModel] = field(default_factory=dict)
    # ── Frozen confidence components ────────────────────────────────────
    n_assets_tested: int = 0          # Assets where mechanism confirmed at target tf
    n_assets_replicated: int = 0      # Assets where mechanism replicates
    n_wf_windows_passed: int = 0      # Walk-forward windows with positive effect
    n_wf_windows_total: int = 4       # Total walk-forward windows attempted
    parameter_plateau: bool = False   # Does threshold sweep show broad plateau?
    null_model_beaten: bool = False   # Does mechanism beat random trigger?
    discovery_period: str = ""        # e.g. "2022-2024"
    confirmation_period: str = ""     # e.g. "2025-2026" (separate from discovery)
    acceptance_level: int = 0         # 0=hypothesis,1=observed,2=replicated,3=cross-market,4=wf-validated,5=production
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def effect_size_rank(self) -> float:
        """Composite score: effect size (bp) × (1 - p_value). Higher = better."""
        if not self.effect_summary:
            return 0.0
        best = max(self.effect_summary.values(),
                   key=lambda v: abs(v.get("mean_bp", 0)) * (1 - v.get("p_value", 1)))
        mean_bp = abs(best.get("mean_bp", 0))
        p_val = best.get("p_value", 1.0)
        return mean_bp * (1.0 - p_val)

    def confidence_score(self) -> float:
        """
        Frozen confidence formula v3 — decoupled components, no arbitrary caps.

        confidence = 0.20*replication + 0.20*temporal + 0.15*effect + 0.15*signif
                   + 0.10*parameter + 0.10*oos + 0.10*robustness
        """
        import math

        # Replication: Combines cross-market and cross-asset evidence
        n_repl = max(self.n_assets_replicated, 0)
        replication = (1 - math.exp(-n_repl / 3.0))

        # Temporal: fraction of WF windows passed
        temporal = self.n_wf_windows_passed / max(self.n_wf_windows_total, 1)

        # Effect size: Soft saturating at 50bp (was hard 20bp cap)
        best_effect = max((abs(d.get('mean_bp', 0)) for d in self.effect_summary.values()), default=0)
        effect_size = 1 - math.exp(-best_effect / 50.0)

        # Significance: 1 - best p-value
        p_values = [d.get('p_value', 1.0) for d in self.effect_summary.values() if d.get('p_value') is not None]
        significance = 1.0 - min(p_values) if p_values else 0.0

        # Parameter: binary — broad plateau confirmed
        parameter = 1.0 if self.parameter_plateau else 0.0

        # Robustness (replaces cross-asset consistency): Consistency across tested assets
        robustness = self.n_assets_replicated / max(self.n_assets_tested, 1) if self.n_assets_tested > 0 else 0.0

        # Out-of-sample: separate confirmation period exists
        oos = 1.0 if self.confirmation_period else 0.0

        return round(
            0.20 * replication +
            0.20 * temporal +
            0.15 * effect_size +
            0.15 * significance +
            0.10 * parameter +
            0.10 * robustness +
            0.10 * oos,
            4
        )

    def meets_protocol(self) -> dict:
        """Acceptance protocol checks — not confidence alone."""
        best_p = min((d.get('p_value', 1.0) for d in self.effect_summary.values()), default=1.0)
        best_effect = max((abs(d.get('mean_bp', 0)) for d in self.effect_summary.values()), default=0)
        return {
            'statistical_significance': best_p < 0.05,
            'economic_significance': best_effect > 12.0,
            'parameter_stability': self.parameter_plateau,
            'temporal_walk_forward': self.n_wf_windows_passed >= 2,
            'cross_asset_replication': self.n_assets_replicated >= 3,
            'null_model_beaten': self.null_model_beaten,
            'causal_explanation': len(self.economic_rationale) > 50,
            'confidence_threshold': self.confidence_score() >= 0.75,
        }

    def acceptance_level_name(self) -> str:
        return {0: 'Hypothesis', 1: 'Observed', 2: 'Replicated',
                3: 'Cross-Market', 4: 'Walk-Forward Validated',
                5: 'Production Ready'}.get(self.acceptance_level, 'Unknown')


# Define triggers locally to avoid circular dependency
def m001_trigger_fn(df: pd.DataFrame) -> pd.Series:
    # Z-score > 2.5 AND ATR percentile > 30% to ensure enough liquidity
    return (df["z_score"] > 2.5) & (df["atr_percentile"] > 0.3)

def m002_trigger_fn(df: pd.DataFrame) -> pd.Series:
    close = df["close"]
    roc = (close - close.shift(5)) / close.shift(5)
    return roc > 0.005

# ═══════════════════════════════════════════════════════════════════════════════
# Pre-defined Mechanisms (M001-M005)
# ═══════════════════════════════════════════════════════════════════════════════

BUILTIN_MECHANISMS: Dict[str, Mechanism] = {
    "M001": Mechanism(
        mechanism_id="M001",
        name="Liquidity Exhaustion",
        description="After a statistically extreme price move driven by temporary "
                    "liquidity imbalance, price has a tendency to revert toward "
                    "its local mean as liquidity providers re-enter.",
        economic_rationale="Market makers withdraw liquidity during rapid moves, "
                          "creating temporary vacuums. When they return, the spread "
                          "compresses and price reverts. This is a microstructure "
                          "phenomenon amplified by leverage in crypto.",
        discovery_type=DiscoveryType.STRUCTURAL,
        inputs=["z_score", "atr_percentile"],
        trigger_fn=m001_trigger_fn,
        effect_summary={
            "BTCUSDT": {"horizon": 5, "mean_bp": 3.6, "p_value": 0.22, "best_regime": "low_vol"},
        },
        falsification_criteria=[
            "ADX > 25 (High trend)",
            "High volatility expansion (ATR > 90th percentile)",
            "News-driven regime (detected via sentiment anomaly)",
            "Low liquidity environment (insufficient depth)"
        ],
        boundary_models={
            "BTC_4h_0.35_0.60": BoundaryModel(
                model_id="M001_BTC_4h_B01",
                asset="BTCUSDT",
                atr_range=(0.35, 0.60),
                timeframe="4h",
                trend_condition="ADX < 25",
                funding_condition="neutral",
                confidence=0.82
            )
        },
    ),

    "M002": Mechanism(
        mechanism_id="M002",
        name="Trend Continuation (Refined)",
        description="Assets in a confirmed momentum trend (ROC > 0.5%) tend to "
                    "continue in that direction over short horizons, with momentum "
                    "decaying after 10-20 bars. Regime filters removed to reduce noise.",
        economic_rationale="Institutional positioning and narrative-driven flows "
                          "create persistent directional pressure. Retail traders "
                          "chase trends, reinforcing the move until exhaustion.",
        discovery_type=DiscoveryType.STRUCTURAL,
        inputs=["roc_5"],
        trigger_fn=lambda df: (df["close"] - df["close"].shift(5)) / df["close"].shift(5) > 0.005,
        effect_summary={
            "ETHUSDT": {"horizon": 10, "mean_bp": 15.0, "p_value": 0.01, "best_regime": "any"},
            "SOLUSDT": {"horizon": 5, "mean_bp": 10.0, "p_value": 0.03, "best_regime": "any"},
        },
        falsification_criteria=[
            "ROC(5) < 0.5% (Weak momentum)",
            "Volume divergence"
        ],
        boundary_models={
            "ETH_4h_ROC_only": BoundaryModel(
                model_id="M002_ETH_4h_B01",
                asset="ETHUSDT",
                atr_range=(0.0, 1.0),
                timeframe="4h",
                trend_condition="ROC > 0.5%",
                funding_condition="any",
                confidence=0.85
            )
        },
    ),

    "M003": Mechanism(
        mechanism_id="M003",
        name="Position Unwind",
        trigger_fn=lambda df: ((df['close'].pct_change(5) > 0.005) & (df['sum_open_interest'].pct_change(5) < -0.005)) | \
                              ((df['close'].pct_change(5) < -0.005) & (df['sum_open_interest'].pct_change(5) > 0.005)),
        effect_summary={
            "BTCUSDT": {"horizon": 20, "mean_bp": 24.5, "p_value": 0.01},
        },
    ),
    "M004": Mechanism(
        mechanism_id="M004",
        name="Funding Rotation",
        trigger_fn=lambda df: (df['funding_rate'] > 0.001) | (df['funding_rate'] < -0.001),
        effect_summary={
            "BTCUSDT": {"horizon": 3, "mean_bp": 63.6, "p_value": 0.005},
        },
    ),
    "M005": Mechanism(
        mechanism_id="M005",
        name="Volatility Compression → Expansion",
        trigger_fn=lambda df: df['atr_percentile'] < 0.2,
        effect_summary={
            "BTCUSDT": {"horizon": 20, "mean_bp": 13.2, "p_value": 0.05},
        },
    ),
    "M006": Mechanism(mechanism_id="M006", name="Positioning Alpha", trigger_fn=lambda df: df['volume'] > df['volume'].rolling(20).mean() * 2.0),
    "M007": Mechanism(mechanism_id="M007", name="Expansion Alpha", trigger_fn=lambda df: df['close'] > df['high'].shift(1).rolling(50).max()),
    "M008": Mechanism(mechanism_id="M008", name="Relative Value Alpha", trigger_fn=lambda df: df['z_score'] < -2.0),
    "M009": Mechanism(mechanism_id="M009", name="Liquidation Alpha", trigger_fn=lambda df: df['volume'] > df['volume'].rolling(50).mean() * 3.0),
    "M010": Mechanism(mechanism_id="M010", name="Microstructure Alpha", trigger_fn=lambda df: df['bid_ask_spread'] > df['bid_ask_spread'].rolling(20).mean() * 1.5),
    "M011": Mechanism(mechanism_id="M011", name="Multi-Timeframe Alpha", trigger_fn=lambda df: df['close'] > df['ema200']),
    "M012": Mechanism(mechanism_id="M012", name="Ensemble Alpha", trigger_fn=lambda df: df['atr_percentile'] > 0.5),
    "M013": Mechanism(mechanism_id="M013", name="Cross-Sectional Alpha", trigger_fn=lambda df: df['close'] > df['close'].shift(20)),
    "M014": Mechanism(mechanism_id="M014", name="Funding Alpha", trigger_fn=lambda df: df['funding_rate'] > 0.001),
    "M015": Mechanism(mechanism_id="M015", name="Volatility Alpha", trigger_fn=lambda df: df['atr_percentile'] < 0.1),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════════

class MechanismRegistry:
    """Central registry of all validated market mechanisms."""

    STORAGE_PATH = Path("data/experiments/mechanism_registry.json")

    def __init__(self):
        self._mechanisms: Dict[str, Mechanism] = {}
        self._load_builtins()

    def _load_builtins(self):
        """Load pre-defined mechanisms. Load saved state from disk if exists."""
        # Start with builtins
        self._mechanisms.update(BUILTIN_MECHANISMS)
        # Overlay any saved state
        if self.STORAGE_PATH.exists():
            try:
                with open(self.STORAGE_PATH) as f:
                    saved = json.load(f)
                for mid, data in saved.items():
                    if mid in self._mechanisms:
                        # Update mutable fields
                        m = self._mechanisms[mid]
                        m.effect_summary = data.get("effect_summary", m.effect_summary)
                        m.boundaries = [
                            MechanismBoundary(**b) for b in data.get("boundaries", [])
                        ] or m.boundaries
                        m.used_by_hypotheses = data.get("used_by_hypotheses", m.used_by_hypotheses)
                        # Load confidence components
                        m.n_assets_tested = data.get("n_assets_tested", m.n_assets_tested)
                        m.n_assets_replicated = data.get("n_assets_replicated", m.n_assets_replicated)
                        m.n_wf_windows_passed = data.get("n_wf_windows_passed", m.n_wf_windows_passed)
                        m.n_wf_windows_total = data.get("n_wf_windows_total", m.n_wf_windows_total)
                        m.parameter_plateau = data.get("parameter_plateau", m.parameter_plateau)
                        m.null_model_beaten = data.get("null_model_beaten", m.null_model_beaten)
                        m.discovery_period = data.get("discovery_period", m.discovery_period)
                        m.confirmation_period = data.get("confirmation_period", "")
                        m.acceptance_level = data.get("acceptance_level", m.acceptance_level)
                        if data.get("stability"):
                            m.stability = StabilityMetrics(**data["stability"])
                logger.info("Mechanism registry loaded from disk (%d mechanisms)", len(saved))
            except Exception as e:
                logger.warning("Failed to load mechanism registry: %s", e)

    def save(self):
        """Persist current state to disk."""
        data = {}
        for mid, m in self._mechanisms.items():
            entry = {
                "mechanism_id": m.mechanism_id,
                "effect_summary": m.effect_summary,
                "boundaries": [asdict(b) for b in m.boundaries],
                "used_by_hypotheses": m.used_by_hypotheses,
            }
            if m.stability:
                entry["stability"] = asdict(m.stability)
            data[mid] = entry
        self.STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.STORAGE_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Mechanism registry saved (%d mechanisms)", len(data))

    def get(self, mechanism_id: str) -> Optional[Mechanism]:
        return self._mechanisms.get(mechanism_id)

    def list_all(self) -> List[Mechanism]:
        return list(self._mechanisms.values())

    def list_by_type(self, dtype: DiscoveryType) -> List[Mechanism]:
        return [m for m in self._mechanisms.values() if m.discovery_type == dtype]

    def register(self, mechanism: Mechanism):
        """Register a new or updated mechanism."""
        mechanism.updated_at = datetime.now(timezone.utc).isoformat()
        self._mechanisms[mechanism.mechanism_id] = mechanism

    def rank_by_effect(self) -> List[Tuple[Mechanism, float]]:
        """Return mechanisms ranked by effect-size score (descending)."""
        ranked = [(m, m.effect_size_rank()) for m in self._mechanisms.values()]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def link_hypothesis(self, mechanism_id: str, hypothesis_id: str):
        """Record that a hypothesis uses this mechanism."""
        m = self._mechanisms.get(mechanism_id)
        if m and hypothesis_id not in m.used_by_hypotheses:
            m.used_by_hypotheses.append(hypothesis_id)

    def find_boundary(
        self,
        mechanism_id: str,
        symbol: str,
        timeframe: str,
        condition_col: str,
        n_splits: int = 5,
    ) -> List[MechanismBoundary]:
        """
        Discover where a mechanism stops working by splitting events on a condition.

        Example:
            boundary = registry.find_boundary("M001", "BTCUSDT", "15m", "atr_percentile")
            # Returns: effect is positive below 40th ATR percentile, negative above
        """
        from src.validation.event_study import EventStudy

        m = self._mechanisms.get(mechanism_id)
        if m is None or m.trigger_fn is None:
            raise ValueError(f"Mechanism {mechanism_id} not found or has no trigger_fn")

        study = EventStudy(symbol, timeframe, max_bars=50000)
        study.add_trigger(mechanism_id, m.trigger_fn)

        # Get events
        df = study.load_data()
        df = study.compute_features(df)
        trigger_mask = m.trigger_fn(df) if m.trigger_fn else pd.Series(False, index=df.index)
        events = study._find_events(trigger_mask)

        if condition_col not in df.columns:
            raise ValueError(f"Column {condition_col} not in features. Available: {list(df.columns)}")

        # Split events by condition quantiles
        condition_vals = df[condition_col].iloc[events].dropna()
        if len(condition_vals) < 20:
            return []

        quantiles = np.linspace(0, 1, n_splits + 1)
        boundaries = []
        best_h = max(m.effect_summary.get(symbol, {}).get("horizon", 5), 1)

        for i in range(n_splits):
            low = condition_vals.quantile(quantiles[i])
            high = condition_vals.quantile(quantiles[i + 1])
            inside = [e for e in events
                      if e < len(df) and low <= df[condition_col].iloc[e] <= high]
            outside = [e for e in events
                       if e < len(df) and (df[condition_col].iloc[e] < low or df[condition_col].iloc[e] > high)]

            if len(inside) < 5:
                continue

            inside_rets = study._compute_forward_returns(inside, best_h)
            _, p_val = study._t_test(inside_rets)
            mean_bp = float(np.mean(inside_rets)) * 10000

            boundaries.append(MechanismBoundary(
                condition=f"{condition_col} in [{low:.2f}, {high:.2f}]",
                effect_size_bp=mean_bp,
                events_inside=len(inside),
                events_outside=len(outside),
                p_value=p_val,
            ))

        # Store on mechanism
        m.boundaries = boundaries
        return boundaries

    def compute_stability(
        self,
        mechanism_id: str,
        symbol: str,
        timeframe: str,
        window_bars: int = 5000,
    ) -> StabilityMetrics:
        """
        Compute rolling-window stability of a mechanism's effect.

        Returns StabilityMetrics with rolling Sharpe, mean bp, and persistence.
        """
        from src.validation.event_study import EventStudy

        m = self._mechanisms.get(mechanism_id)
        if m is None or m.trigger_fn is None:
            raise ValueError(f"Mechanism {mechanism_id} not found or has no trigger_fn")

        df = EventStudy(symbol, timeframe).load_data()
        df = EventStudy(symbol, timeframe).compute_features(df)
        best_h = max(m.effect_summary.get(symbol, {}).get("horizon", 5), 1)

        n_bars = len(df)
        step = window_bars // 2
        rolling_means = []
        rolling_sharpes = []

        for start in range(0, n_bars - window_bars, step):
            window_df = df.iloc[start:start + window_bars]
            trigger_mask = m.trigger_fn(window_df)
            study_temp = EventStudy(symbol, timeframe, max_bars=window_bars)
            events = study_temp._find_events(trigger_mask)
            if len(events) < 5:
                continue
            rets = study_temp._compute_forward_returns(events, best_h)
            mean_bp = float(np.mean(rets)) * 10000
            std_bp = float(np.std(rets, ddof=1)) * 10000
            rolling_means.append(mean_bp)
            rolling_sharpes.append(mean_bp / std_bp if std_bp > 0 else 0.0)

        # Effect persistence: autocorrelation of rolling means
        persistence = 0.0
        if len(rolling_means) > 2:
            arr = np.array(rolling_means)
            persistence = float(np.corrcoef(arr[:-1], arr[1:])[0, 1])
            if np.isnan(persistence):
                persistence = 0.0

        # Bootstrap variance of the effect
        all_rets_full = []
        for start in range(0, n_bars - window_bars, step):
            window_df = df.iloc[start:start + window_bars]
            trigger_mask = m.trigger_fn(window_df)
            study_temp = EventStudy(symbol, timeframe, max_bars=window_bars)
            events = study_temp._find_events(trigger_mask)
            if len(events) >= 5:
                rets = study_temp._compute_forward_returns(events, best_h)
                all_rets_full.append(float(np.mean(rets)))

        boot_var = float(np.var(all_rets_full)) if len(all_rets_full) > 1 else 0.0

        stability = StabilityMetrics(
            rolling_6m_mean_bp=rolling_means,
            rolling_6m_sharpe=rolling_sharpes,
            bootstrap_variance=boot_var,
            effect_persistence=persistence,
        )
        m.stability = stability
        return stability

    def rank_by_confidence(self) -> List[Tuple[Mechanism, float]]:
        """Return mechanisms ranked by composite confidence score."""
        ranked = [(m, m.confidence_score()) for m in self._mechanisms.values()]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def research_cost_optimize(self, n_suggestions: int = 10) -> List[Dict]:
        """
        Prioritize experiments by expected information gain per unit cost.

        Each potential experiment is scored by:
          info_gain = (1.0 - mechanism.confidence) × n_assets × n_regimes
          cost      = n_bars / 1000 + data_loading_penalty
          priority  = info_gain / cost

        Returns ranked list of suggested next experiments.
        """
        from src.core.causal_graph import causal_graph

        suggestions = causal_graph.suggest_hypotheses(max_suggestions=50)
        scored = []

        for s in suggestions:
            mechanism_ids = s["mechanisms"]
            # Aggregate confidence of involved mechanisms
            avg_confidence = 0.0
            for mid in mechanism_ids:
                m = self._mechanisms.get(mid.lstrip("M0").lstrip("M"))
                # Try exact match first, then prefix
                if m:
                    avg_confidence += m.confidence_score()
                else:
                    for full_mid in self._mechanisms:
                        if mid in full_mid:
                            avg_confidence += self._mechanisms[full_mid].confidence_score()
                            break
                    else:
                        avg_confidence += 0.3  # Unknown mechanism
            avg_confidence /= max(len(mechanism_ids), 1)

            # Information gain: how much uncertainty remains
            info_gain = (1.0 - avg_confidence) * len(mechanism_ids)

            # Cost estimate
            n_assets = max(len(mechanism_ids), 2)
            cost = 5000 / 1000 + (0.5 if n_assets > 2 else 0.0)

            priority = info_gain / max(cost, 0.1)
            scored.append({**s, "info_gain": round(info_gain, 3),
                          "est_cost": round(cost, 2),
                          "priority": round(priority, 4)})

        scored.sort(key=lambda x: x["priority"], reverse=True)
        return scored[:n_suggestions]

# Singleton
registry = MechanismRegistry()

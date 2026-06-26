# src/core/knowledge_base.py
"""
Research Knowledge Base — preserve empirical findings (Research Platform v2).

Every confirmed finding, rejected hypothesis, and discovered market property
is stored here so new hypotheses can cite previous evidence instead of
rediscovering it.

The Knowledge Base captures:
  - Observations (empirical findings with confidence levels)
  - Supporting experiments (which experiments proved/disproved this)
  - Rejected explanations (what was tried and failed)
  - Related hypotheses (links to evidence ladder entries)

Design
------
- JSON-persisted to ``data/experiments/knowledge_base.json``.
- Observations are tagged by domain (microstructure, momentum, volatility, etc.).
- Each observation has a confidence level (1-5) and supporting experiment refs.
- ``ResearchKnowledgeBase`` provides query methods: by domain, by confidence,
  by related hypothesis, and citation helpers.

Seed Data
---------
Pre-populated with 7 discoveries from 2025-2026 research:

  1. BTC behaves differently from ETH
  2. SOL behaves differently from BTC
  3. Funding alone is weak
  4. Z-score is stronger than percentage stretch
  5. Walk-forward kills many beautiful backtests
  6. Costs destroy many apparent alphas
  7. MTF context matters
  8. Microstructure differs across assets

Usage
-----
    from src.core.knowledge_base import knowledge_base

    # Query by domain
    findings = knowledge_base.get_by_domain("microstructure")

    # Cite a finding in a hypothesis
    kb.cite("obs_004")  # Returns citation string
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Observation:
    """One empirical finding stored in the knowledge base."""
    observation_id: str                      # Unique ID: "obs_001"
    statement: str                           # The finding itself
    domain: str                              # "microstructure", "momentum", "volatility", etc.
    confidence: int = 1                      # 1 (weak) to 5 (strong)
    supporting_experiments: List[str] = field(default_factory=list)  # experiment IDs
    rejected_explanations: List[str] = field(default_factory=list)   # What was tried & failed
    related_hypotheses: List[str] = field(default_factory=list)      # Evidence ladder IDs
    discovered_at: str = ""                  # ISO timestamp
    updated_at: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.discovered_at:
            self.discovered_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.discovered_at

    @property
    def confidence_label(self) -> str:
        labels = {1: "Weak", 2: "Suggestive", 3: "Moderate", 4: "Strong", 5: "Confirmed"}
        return labels.get(self.confidence, "Unknown")

    def citation(self) -> str:
        """Formatted citation string for use in hypothesis documents."""
        return (
            f"[{self.observation_id}] {self.statement} "
            f"(confidence: {self.confidence_label}, "
            f"experiments: {len(self.supporting_experiments)})"
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeBaseSummary:
    """Dashboard summary of knowledge base contents."""
    total_observations: int
    by_domain: Dict[str, int]
    by_confidence: Dict[str, int]
    high_confidence: int  # confidence >= 4
    total_supporting_experiments: int
    total_related_hypotheses: int


# ═══════════════════════════════════════════════════════════════════════════════
#  Research Knowledge Base
# ═══════════════════════════════════════════════════════════════════════════════

class ResearchKnowledgeBase:
    """
    Persistent store of empirical research findings.

    Parameters
    ----------
    path : str, optional
        Path to the knowledge base JSON file.
    """

    DEFAULT_PATH = "data/experiments/knowledge_base.json"

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or self.DEFAULT_PATH)
        self._observations: Dict[str, Observation] = {}
        self._loaded = False

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def add(self, observation: Observation) -> None:
        """Add an observation to the knowledge base."""
        if observation.observation_id in self._observations:
            logger.warning(
                "Observation %s already exists. Use update().",
                observation.observation_id,
            )
            return
        self._observations[observation.observation_id] = observation
        logger.info(
            "KB: added observation %s [%s, confidence=%d]",
            observation.observation_id, observation.domain, observation.confidence,
        )

    def get(self, observation_id: str) -> Optional[Observation]:
        return self._observations.get(observation_id)

    def update(
        self,
        observation_id: str,
        **kwargs,
    ) -> bool:
        """Update fields of an existing observation."""
        obs = self._observations.get(observation_id)
        if obs is None:
            return False
        for key, value in kwargs.items():
            if hasattr(obs, key):
                setattr(obs, key, value)
        obs.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def cite(self, observation_id: str) -> str:
        """Return a citation string for this observation, or empty string."""
        obs = self._observations.get(observation_id)
        if obs is None:
            return ""
        return obs.citation()

    # ── Query ──────────────────────────────────────────────────────────────────

    def get_by_domain(self, domain: str) -> List[Observation]:
        """Return all observations in a given domain."""
        return [
            o for o in self._observations.values()
            if o.domain.lower() == domain.lower()
        ]

    def get_by_confidence(self, min_confidence: int) -> List[Observation]:
        """Return observations with confidence >= min_confidence."""
        return [
            o for o in self._observations.values()
            if o.confidence >= min_confidence
        ]

    def get_by_hypothesis(self, hypothesis_id: str) -> List[Observation]:
        """Return observations related to a specific hypothesis."""
        return [
            o for o in self._observations.values()
            if hypothesis_id in o.related_hypotheses
        ]

    def get_high_confidence(self) -> List[Observation]:
        """Return observations with confidence >= 4 (Strong or Confirmed)."""
        return self.get_by_confidence(4)

    def list_domains(self) -> List[str]:
        """Return all known domains."""
        return sorted(set(o.domain for o in self._observations.values()))

    def list_all(self) -> List[Observation]:
        return sorted(self._observations.values(), key=lambda o: (-o.confidence, o.observation_id))

    # ── Summary ────────────────────────────────────────────────────────────────

    def summary(self) -> KnowledgeBaseSummary:
        by_domain: Dict[str, int] = {}
        by_confidence: Dict[str, int] = {}
        high_confidence = 0
        total_experiments = 0
        total_hypotheses = 0

        for o in self._observations.values():
            by_domain[o.domain] = by_domain.get(o.domain, 0) + 1
            label = o.confidence_label
            by_confidence[label] = by_confidence.get(label, 0) + 1
            if o.confidence >= 4:
                high_confidence += 1
            total_experiments += len(o.supporting_experiments)
            total_hypotheses += len(o.related_hypotheses)

        return KnowledgeBaseSummary(
            total_observations=len(self._observations),
            by_domain=by_domain,
            by_confidence=by_confidence,
            high_confidence=high_confidence,
            total_supporting_experiments=total_experiments,
            total_related_hypotheses=total_hypotheses,
        )

    def render_summary(self) -> str:
        s = self.summary()
        lines = [
            "═══ Research Knowledge Base ═══",
            f"  Total observations: {s.total_observations}",
            f"  High confidence (≥4): {s.high_confidence}",
            "",
            "  By Domain:",
        ]
        for domain, count in sorted(s.by_domain.items()):
            lines.append(f"    {domain:<25} {count:>3}")
        lines.append("")
        lines.append("  By Confidence:")
        for level in ["Confirmed", "Strong", "Moderate", "Suggestive", "Weak"]:
            count = s.by_confidence.get(level, 0)
            if count > 0:
                lines.append(f"    {level:<15} {count:>3}")
        return "\n".join(lines)

    # ── Persistence ────────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist the knowledge base to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "observations": [o.to_dict() for o in self._observations.values()],
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(
            "Knowledge Base saved: %d observations → %s",
            len(self._observations), self.path,
        )

    def load(self) -> bool:
        """Load the knowledge base from disk."""
        if not self.path.exists():
            logger.info("Knowledge Base: no existing file at %s.", self.path)
            self._loaded = True
            return True
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load knowledge base: %s", exc)
            return False

        observations_data = data.get("observations", [])
        loaded = 0
        for od in observations_data:
            try:
                obs = Observation(**od)
                self._observations[obs.observation_id] = obs
                loaded += 1
            except Exception as exc:
                logger.warning("Skipping corrupt observation: %s", exc)

        self._loaded = True
        logger.info(
            "Knowledge Base loaded: %d observations (version=%s).",
            loaded, data.get("version", "?"),
        )
        return True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def __len__(self) -> int:
        return len(self._observations)


# ═══════════════════════════════════════════════════════════════════════════════
#  Module-level singleton (pre-seeded)
# ═══════════════════════════════════════════════════════════════════════════════

def create_seeded_knowledge_base() -> ResearchKnowledgeBase:
    """Factory that creates a Knowledge Base pre-seeded with known discoveries."""
    kb = ResearchKnowledgeBase()

    discoveries = [
        Observation(
            observation_id="obs_001",
            statement="BTC behaves differently from ETH — strategies that work on one often fail on the other.",
            domain="cross_asset",
            confidence=5,
            supporting_experiments=["experiment_family_a", "btc_vs_eth_comparison"],
            related_hypotheses=["btc_mr_l2", "eth_mom_l1"],
            notes="Confirmed across multiple backtests and walk-forward validations. "
                  "ETH is more momentum-driven; BTC shows stronger mean-reversion at intraday timeframes.",
        ),
        Observation(
            observation_id="obs_002",
            statement="SOL behaves differently from BTC — higher volatility, stronger momentum persistence.",
            domain="cross_asset",
            confidence=4,
            supporting_experiments=["experiment_family_b", "sol_momentum_60m"],
            related_hypotheses=["sol_mom_l1"],
            notes="SOL's high retail participation creates distinct momentum characteristics. "
                  "Strategies must account for higher slippage and volatility.",
        ),
        Observation(
            observation_id="obs_003",
            statement="Funding rate as a standalone signal is weak — must be combined with OI or price action.",
            domain="funding",
            confidence=4,
            supporting_experiments=["experiment_family_c", "funding_standalone_test"],
            rejected_explanations=["Funding divergence alone predicts reversals."],
            related_hypotheses=["pos_003", "pos_004"],
            notes="Funding rate extremes do occur before reversals, but timing is unreliable. "
                  "Combining funding acceleration with OI divergence improves signal quality.",
        ),
        Observation(
            observation_id="obs_004",
            statement="Z-score-based mean-reversion is stronger than percentage-stretch-based mean-reversion.",
            domain="mean_reversion",
            confidence=5,
            supporting_experiments=["failed_mr_thesis", "zscore_vs_pct_stretch"],
            related_hypotheses=["btc_mr_l2", "pos_001"],
            notes="Z-score normalizes by recent volatility, making signals adaptive to regime changes. "
                  "Percentage-based thresholds suffer from regime-dependent performance.",
        ),
        Observation(
            observation_id="obs_005",
            statement="Walk-forward validation kills many beautiful in-sample backtests — PF drops 30-60% typically.",
            domain="validation",
            confidence=5,
            supporting_experiments=["walk_forward_btc_mr", "walk_forward_eth_mom"],
            related_hypotheses=["btc_mr_l2", "eth_mom_l1", "sol_mom_l1"],
            notes="This is the single most important lesson from 2025-2026 research. "
                  "Never trust an in-sample backtest without walk-forward confirmation. "
                  "The pipeline's Stage 3 (walk-forward) is the hardest gate.",
        ),
        Observation(
            observation_id="obs_006",
            statement="Transaction costs destroy many apparent alphas — always backtest with realistic fees + slippage.",
            domain="execution",
            confidence=5,
            supporting_experiments=["cost_sensitivity_analysis"],
            related_hypotheses=["btc_mr_l2", "exec_001"],
            notes="Many strategies with PF 1.5+ gross fall below 1.0 after 10bp fee + 5bp slippage. "
                  "High-turnover strategies are especially vulnerable. "
                  "Maker-order execution can recover ~5bp but introduces fill risk.",
        ),
        Observation(
            observation_id="obs_007",
            statement="Multi-timeframe context matters — higher-timeframe regime significantly impacts lower-timeframe strategy performance.",
            domain="multi_timeframe",
            confidence=4,
            supporting_experiments=["mtf_zscore_experiment", "experiment_mtf_context"],
            related_hypotheses=["mtf_001", "mtf_002"],
            notes="Strategies perform differently in HTF bull vs bear regimes. "
                  "A mean-reversion strategy may work in range-bound HTF but fail in trending HTF. "
                  "HTF context should gate or modulate LTF signal thresholds.",
        ),
        Observation(
            observation_id="obs_008",
            statement="Market microstructure differs meaningfully across assets — bid-ask spreads, order book depth, and fill dynamics vary.",
            domain="microstructure",
            confidence=3,
            supporting_experiments=["microstructure_comparison"],
            related_hypotheses=["micro_001", "micro_002", "micro_003"],
            notes="BTC has the deepest books and tightest spreads. "
                  "Altcoins (ETH, SOL, DOGE) have wider spreads and shallower books. "
                  "LOB imbalance signals that work on BTC may fail on thinner markets.",
        ),
    ]

    for obs in discoveries:
        kb.add(obs)

    kb.save()
    logger.info("Knowledge Base seeded with %d initial observations.", len(discoveries))
    return kb


# Module-level singleton
knowledge_base = ResearchKnowledgeBase()

__all__ = [
    "ResearchKnowledgeBase",
    "Observation",
    "KnowledgeBaseSummary",
    "knowledge_base",
    "create_seeded_knowledge_base",
]

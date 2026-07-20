# src/core/evidence_ladder.py
"""
Evidence Ladder — strict hypothesis classification system (Roadmap v2).

Every alpha hypothesis is classified before significant development effort
according to the evidence ladder defined in the 2026-06-26 Research Roadmap:

  Level  Meaning                         Action
  L0     Economic intuition only         Cheap prototype
  L1     In-sample edge                  Do not celebrate
  L2     Survives transaction costs      Continue research
  L3     Survives walk-forward           High priority
  L4     Survives cross-asset validation Candidate alpha
  L5     Survives live paper trading     Production candidate
  L6     Survives 6–12 months live       Deploy capital

The ladder integrates with the existing SurvivalGate (Layer 5) and
StrategyRepository (Layer 6) to provide a unified tracking system for
every hypothesis from inception through production deployment.

Design
------
- Each hypothesis is stored as a HypothesisRecord with full provenance.
- The ladder is persisted as JSON in ``data/experiments/evidence_ladder.json``.
- Promotion requires explicit gate evidence; demotion is automatic on failure.
- The ladder emits structured events that the Research Pipeline consumes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Evidence Level Enum
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceLevel(IntEnum):
    """Ordered evidence levels — higher = stronger evidence."""
    L0 = 0   # Economic intuition only
    L1 = 1   # In-sample edge
    L2 = 2   # Survives transaction costs
    L3 = 3   # Survives walk-forward
    L4 = 4   # Survives cross-asset validation
    L5 = 5   # Survives live paper trading
    L6 = 6   # Survives 6–12 months live

    @classmethod
    def from_string(cls, s: str) -> "EvidenceLevel":
        """Parse 'L0'..'L6' or integer string."""
        s = s.strip().upper()
        if s.startswith("L"):
            try:
                return cls(int(s[1:]))
            except (ValueError, IndexError):
                pass
        try:
            return cls(int(s))
        except ValueError:
            raise ValueError(f"Invalid evidence level: {s!r}. Expected L0..L6.")

    @property
    def label(self) -> str:
        """Human-readable label for this level."""
        return _LEVEL_LABELS.get(self, f"L{self.value}")

    @property
    def action(self) -> str:
        """Recommended action at this level."""
        return _LEVEL_ACTIONS.get(self, "Unknown")


_LEVEL_LABELS: Dict[EvidenceLevel, str] = {
    EvidenceLevel.L0: "Economic intuition only",
    EvidenceLevel.L1: "In-sample edge",
    EvidenceLevel.L2: "Survives transaction costs",
    EvidenceLevel.L3: "Survives walk-forward",
    EvidenceLevel.L4: "Survives cross-asset validation",
    EvidenceLevel.L5: "Survives live paper trading",
    EvidenceLevel.L6: "Survives 6-12 months live",
}

_LEVEL_ACTIONS: Dict[EvidenceLevel, str] = {
    EvidenceLevel.L0: "Cheap prototype",
    EvidenceLevel.L1: "Do not celebrate",
    EvidenceLevel.L2: "Continue research",
    EvidenceLevel.L3: "High priority",
    EvidenceLevel.L4: "Candidate alpha",
    EvidenceLevel.L5: "Production candidate",
    EvidenceLevel.L6: "Deploy capital",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Research Pipeline Stage Mapping
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PipelineStage:
    """One stage in the 10-stage research pipeline."""
    number: int
    name: str
    description: str
    required_evidence_level: EvidenceLevel
    gate_type: str   # "manual" | "automated" | "semi-automated"


# The 10-stage research pipeline from the Roadmap, mapped to evidence levels.
PIPELINE_STAGES: List[PipelineStage] = [
    PipelineStage(1,  "Economic Explanation",   "Written rationale, falsification condition", EvidenceLevel.L0, "manual"),
    PipelineStage(2,  "In-Sample Discovery",     "Initial signal detection on training data",   EvidenceLevel.L1, "automated"),
    PipelineStage(3,  "Walk-Forward Validation", "Purged walk-forward cross-validation",        EvidenceLevel.L3, "automated"),
    PipelineStage(4,  "Bootstrap",               "Statistical significance via bootstrap",      EvidenceLevel.L3, "automated"),
    PipelineStage(5,  "Outlier Robustness",      "Remove top/bottom 1% returns, re-evaluate",   EvidenceLevel.L3, "automated"),
    PipelineStage(6,  "Transaction Costs",       "Realistic fees + slippage + market impact",   EvidenceLevel.L2, "automated"),
    PipelineStage(7,  "Regime Stability",        "Performance across Bull/Bear/Neutral regimes",EvidenceLevel.L4, "automated"),
    PipelineStage(8,  "Cross-Asset Validation",  "Test on 2+ unrelated assets",                 EvidenceLevel.L4, "automated"),
    PipelineStage(9,  "Paper Trading",           "Live market data, no capital",                EvidenceLevel.L5, "semi-automated"),
    PipelineStage(10, "Production",              "Live capital deployment",                     EvidenceLevel.L6, "semi-automated"),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Hypothesis Record
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StageResult:
    """Outcome of one pipeline stage evaluation."""
    stage: int
    name: str
    passed: bool
    timestamp: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class EvidenceLadderMetadata:
    """Persistent metadata for the ladder."""
    total_trials: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HypothesisRecord:
    """
    Full lifecycle record of one alpha hypothesis.

    Tracks its journey from L0 (economic intuition) through the evidence
    ladder, recording every stage evaluation with full provenance.
    """
    hypothesis_id: str
    name: str
    family: str                      # e.g. "Positioning", "CrossSection", "Expansion"
    description: str = ""
    economic_rationale: str = ""

    # Current position on the ladder
    evidence_level: EvidenceLevel = EvidenceLevel.L0

    # Metadata
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "researcher"
    symbols: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Stage results — ordered list of evaluations
    stage_results: List[StageResult] = field(default_factory=list)

    # Performance snapshot (from most recent successful evaluation)
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Backlog tracking
    failed_at_stage: Optional[int] = None
    failure_reason: str = ""
    retry_count: int = 0
    archived: bool = False

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def promote(self, new_level: EvidenceLevel, stage_result: StageResult) -> None:
        """Promote to a higher evidence level after passing a stage."""
        if new_level <= self.evidence_level:
            logger.warning(
                "Hypothesis %s: attempted promotion L%d → L%d (not higher). Ignored.",
                self.hypothesis_id, self.evidence_level.value, new_level.value,
            )
            return
        old = self.evidence_level
        self.evidence_level = new_level
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.stage_results.append(stage_result)
        self.failed_at_stage = None
        self.failure_reason = ""
        logger.info(
            "Hypothesis %s PROMOTED: L%d → L%d (%s) via stage %d (%s).",
            self.hypothesis_id, old.value, new_level.value,
            new_level.label, stage_result.stage, stage_result.name,
        )

    def demote(self, reason: str, failed_stage: int) -> None:
        """Demote back to L0 on failure — returns to research backlog."""
        old = self.evidence_level
        self.evidence_level = EvidenceLevel.L0
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.failed_at_stage = failed_stage
        self.failure_reason = reason
        self.retry_count += 1
        stage_result = StageResult(
            stage=failed_stage,
            name=f"Stage {failed_stage}",
            passed=False,
            notes=reason,
        )
        self.stage_results.append(stage_result)
        logger.warning(
            "Hypothesis %s DEMOTED: L%d → L0 (failed stage %d: %s). Retry #%d.",
            self.hypothesis_id, old.value, failed_stage, reason, self.retry_count,
        )

    def record_stage(self, result: StageResult) -> None:
        """Record a stage evaluation without changing level."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.stage_results.append(result)

    @property
    def level_label(self) -> str:
        return self.evidence_level.label

    @property
    def level_action(self) -> str:
        return self.evidence_level.action

    @property
    def current_stage(self) -> int:
        """The next pipeline stage this hypothesis should attempt."""
        if self.evidence_level >= EvidenceLevel.L6:
            return 11  # beyond the pipeline
        for stage in PIPELINE_STAGES:
            if stage.required_evidence_level > self.evidence_level:
                return stage.number
        return 1

    # ── Multi-dimensional scoring (Evidence Ladder v2) ─────────────────────

    def evidence_score(self) -> "EvidenceScore":
        """
        Compute a multi-dimensional evidence score.
        ...
        """
        return compute_evidence_score(self)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence_level"] = self.evidence_level.value
        d["evidence_level_label"] = self.level_label
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HypothesisRecord":
        level = EvidenceLevel(d.get("evidence_level", 0))
        stage_results = [
            StageResult(**sr) for sr in d.get("stage_results", [])
        ]
        d_clean = {k: v for k, v in d.items()
                   if k not in ("evidence_level", "stage_results",
                                "evidence_level_label")}
        return cls(
            evidence_level=level,
            stage_results=stage_results,
            **d_clean,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  Multi-Dimensional Evidence Scoring (Evidence Ladder v2)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EvidenceScore:
    """Multi-dimensional evidence score for a hypothesis.

    Each axis is 0.0–1.0. The weighted_total is a composite.
    This replaces the single L0-L6 level for ranking/comparison.
    """
    hypothesis_id: str
    economic_rationale: float = 0.0       # Sound economic basis
    sample_size: float = 0.0              # Enough data used
    cross_validation: float = 0.0         # Walk-forward performed
    regime_stability: float = 0.0         # Works across Bull/Bear/Neutral
    cross_asset: float = 0.0             # Validated on other assets
    transaction_costs: float = 0.0        # Survives realistic fees
    statistical_confidence: float = 0.0   # Bootstrap / p-value
    production_readiness: float = 0.0     # Deployable

    # Weights for each axis in the composite score
    WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        "economic_rationale": 0.10,
        "sample_size": 0.10,
        "cross_validation": 0.20,
        "regime_stability": 0.15,
        "cross_asset": 0.10,
        "transaction_costs": 0.15,
        "statistical_confidence": 0.10,
        "production_readiness": 0.10,
    })

    @property
    def weighted_total(self) -> float:
        """Weighted composite score (0.0–1.0)."""
        total = 0.0
        for axis, weight in self.WEIGHTS.items():
            total += getattr(self, axis, 0.0) * weight
        return round(total, 4)

    @property
    def labels(self) -> Dict[str, str]:
        """Human-readable labels for each axis."""
        return {
            "economic_rationale": "Economic Rationale",
            "sample_size": "Sample Size",
            "cross_validation": "Cross-Validation",
            "regime_stability": "Regime Stability",
            "cross_asset": "Cross-Asset Validation",
            "transaction_costs": "Transaction Cost Robustness",
            "statistical_confidence": "Statistical Confidence",
            "production_readiness": "Production Readiness",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "economic_rationale": self.economic_rationale,
            "sample_size": self.sample_size,
            "cross_validation": self.cross_validation,
            "regime_stability": self.regime_stability,
            "cross_asset": self.cross_asset,
            "transaction_costs": self.transaction_costs,
            "statistical_confidence": self.statistical_confidence,
            "production_readiness": self.production_readiness,
            "weighted_total": self.weighted_total,
        }

    def render(self) -> str:
        """Human-readable multi-axis score display."""
        lines = [
            f"═══ Evidence Score: {self.hypothesis_id} ═══",
            f"  Weighted Total: {self.weighted_total:.3f}",
        ]
        for axis, weight in self.WEIGHTS.items():
            value = getattr(self, axis, 0.0)
            label = self.labels.get(axis, axis)
            bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
            lines.append(
                f"  {label:<28} [{bar}] {value:.2f} × {weight:.2f} = {value * weight:.3f}"
            )
        return "\n".join(lines)


def compute_evidence_score(record: HypothesisRecord) -> EvidenceScore:
    """
    Compute a multi-dimensional evidence score from a HypothesisRecord.

    Derives per-axis scores from the record's stage results and metrics.
    """
    score = EvidenceScore(hypothesis_id=record.hypothesis_id)

    # 1. Economic Rationale (0-1): based on description + rationale quality
    rationale_len = len(record.economic_rationale.strip())
    desc_len = len(record.description.strip())
    score.economic_rationale = min(1.0, (rationale_len / 200 + desc_len / 100) / 2)

    # 2. Sample Size (0-1): based on in-sample metrics
    in_sample = record.metrics.get("in_sample", {})
    trades = in_sample.get("closed_trades", 0)
    score.sample_size = min(1.0, trades / 100)

    # 3. Cross-Validation (0-1): walk-forward metrics
    wf = record.metrics.get("walk_forward", {})
    n_windows = wf.get("n_windows", 0)
    ir_pos = wf.get("ir_positive_prob", 0.0)
    score.cross_validation = min(1.0, (n_windows / 24 + ir_pos) / 2)

    # 4. Regime Stability (0-1): from regime_stability metrics
    regime = record.metrics.get("regime_stability", {})
    n_pos = regime.get("n_regimes_positive", 0)
    score.regime_stability = n_pos / 3.0  # 0, 1, 2, or 3 out of 3

    # 5. Cross-Asset (0-1): from cross_asset metrics
    cross = record.metrics.get("cross_asset", {})
    n_assets_passed = cross.get("n_passed", 0)
    score.cross_asset = min(1.0, n_assets_passed / 3)

    # 6. Transaction Costs (0-1): from transaction_costs metrics
    tc = record.metrics.get("transaction_costs", {})
    pf_net = tc.get("pf_net", 0.0)
    pf_gross = tc.get("pf_gross", pf_net)
    if pf_gross > 0:
        cost_ratio = pf_net / pf_gross
    else:
        cost_ratio = 0.0
    score.transaction_costs = min(1.0, max(0.0, cost_ratio))

    # 7. Statistical Confidence (0-1): bootstrap p-value
    bs = record.metrics.get("bootstrap", {})
    p_value = bs.get("p_value", 1.0)
    score.statistical_confidence = max(0.0, 1.0 - p_value)

    # 8. Production Readiness (0-1): paper trading + production metrics
    pt = record.metrics.get("paper_trading", {})
    prod = record.metrics.get("production", {})
    days_live = pt.get("days_live", 0)
    pf_live = pt.get("pf_live", prod.get("pf_live", 0.0))
    prod_score = min(1.0, days_live / 60) * 0.5  # 60+ days = 0.5
    if pf_live > 1.0:
        prod_score += min(0.5, (pf_live - 1.0) / 2.0)  # PF above 1.0 adds up to 0.5
    score.production_readiness = min(1.0, prod_score)

    return score


# ═══════════════════════════════════════════════════════════════════════════════
#  Evidence Ladder — Registry
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceLadder:
    """
    Central registry of all alpha hypotheses with evidence-level tracking.

    Persisted to ``data/experiments/evidence_ladder.json``. Thread-safe for
    read operations; write operations should be serialised externally.

    Usage
    -----
        ladder = EvidenceLadder()
        ladder.register(HypothesisRecord(
            hypothesis_id="pos_001",
            name="OI Expansion Breakout",
            family="Positioning",
        ))
        # After passing walk-forward:
        ladder.promote("pos_001", EvidenceLevel.L3,
                       StageResult(stage=3, name="Walk-Forward", passed=True))
        ladder.save()
    """

    DEFAULT_PATH = "data/experiments/evidence_ladder.json"

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or self.DEFAULT_PATH)
        self._hypotheses: Dict[str, HypothesisRecord] = {}
        self._metadata = EvidenceLadderMetadata()
        self._loaded = False

    # ── Metadata ─────────────────────────────────────────────────────────────

    def increment_trials(self) -> int:
        """Increment the global experiment trial count."""
        self._metadata.total_trials += 1
        self._metadata.updated_at = datetime.now(timezone.utc).isoformat()
        return self._metadata.total_trials

    def get_total_trials(self) -> int:
        """Return the global experiment trial count."""
        return self._metadata.total_trials

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def register(self, record: HypothesisRecord) -> None:
        """Register a new hypothesis at L0."""
        if record.hypothesis_id in self._hypotheses:
            logger.warning(
                "Hypothesis %s already registered. Use update() to modify.",
                record.hypothesis_id,
            )
            return
        self._hypotheses[record.hypothesis_id] = record
        logger.info(
            "Hypothesis REGISTERED: %s (%s) [%s → L%d].",
            record.hypothesis_id, record.name, record.family, record.evidence_level.value,
        )

    def get(self, hypothesis_id: str) -> Optional[HypothesisRecord]:
        """Retrieve a hypothesis by ID."""
        return self._hypotheses.get(hypothesis_id)

    def promote(
        self,
        hypothesis_id: str,
        new_level: EvidenceLevel,
        stage_result: StageResult,
    ) -> bool:
        """Promote a hypothesis to a higher evidence level."""
        record = self._hypotheses.get(hypothesis_id)
        if record is None:
            logger.error("Cannot promote unknown hypothesis: %s", hypothesis_id)
            return False
        if new_level <= record.evidence_level:
            logger.warning(
                "Promotion L%d → L%d for %s is not an advancement. Skipped.",
                record.evidence_level.value, new_level.value, hypothesis_id,
            )
            return False
        record.promote(new_level, stage_result)
        return True

    def demote(
        self,
        hypothesis_id: str,
        reason: str,
        failed_stage: int,
    ) -> bool:
        """Demote a hypothesis back to L0 on failure."""
        record = self._hypotheses.get(hypothesis_id)
        if record is None:
            logger.error("Cannot demote unknown hypothesis: %s", hypothesis_id)
            return False
        record.demote(reason, failed_stage)
        return True

    def archive(self, hypothesis_id: str) -> bool:
        """Archive a hypothesis (no longer actively researched)."""
        record = self._hypotheses.get(hypothesis_id)
        if record is None:
            return False
        record.archived = True
        record.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("Hypothesis ARCHIVED: %s", hypothesis_id)
        return True

    def list_active(self) -> List[HypothesisRecord]:
        """Return all non-archived hypotheses, sorted by evidence level (desc)."""
        active = [r for r in self._hypotheses.values() if not r.archived]
        active.sort(key=lambda r: (-r.evidence_level.value, r.updated_at), reverse=False)
        return active

    def list_by_level(self, level: EvidenceLevel) -> List[HypothesisRecord]:
        """Return all active hypotheses at a given evidence level."""
        return [
            r for r in self._hypotheses.values()
            if not r.archived and r.evidence_level == level
        ]

    def list_by_family(self, family: str) -> List[HypothesisRecord]:
        """Return all active hypotheses in a given alpha family."""
        return [
            r for r in self._hypotheses.values()
            if not r.archived and r.family.lower() == family.lower()
        ]

    def list_candidates(self) -> List[HypothesisRecord]:
        """Return hypotheses at L4+ (candidate alpha or better)."""
        return [
            r for r in self._hypotheses.values()
            if not r.archived and r.evidence_level >= EvidenceLevel.L4
        ]

    def list_production_candidates(self) -> List[HypothesisRecord]:
        """Return hypotheses at L5+ (ready for or in production)."""
        return [
            r for r in self._hypotheses.values()
            if not r.archived and r.evidence_level >= EvidenceLevel.L5
        ]

    # ── Backlog management ───────────────────────────────────────────────────

    def list_backlog(self) -> List[HypothesisRecord]:
        """Return hypotheses at L0 that have previously failed (retry candidates)."""
        return [
            r for r in self._hypotheses.values()
            if not r.archived
            and r.evidence_level == EvidenceLevel.L0
            and r.retry_count > 0
        ]

    def list_never_tested(self) -> List[HypothesisRecord]:
        """Return hypotheses at L0 that have never been tested."""
        return [
            r for r in self._hypotheses.values()
            if not r.archived
            and r.evidence_level == EvidenceLevel.L0
            and r.retry_count == 0
        ]
    # [Rest of existing CRUD methods...]

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist the full ladder to disk as JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.1",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": self._metadata.to_dict(),
            "hypotheses": [
                r.to_dict() for r in self._hypotheses.values()
            ],
        }
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        logger.info(
            "Evidence Ladder saved: %d hypotheses, %d trials → %s",
            len(self._hypotheses), self._metadata.total_trials, self.path,
        )

    def load(self) -> bool:
        """Load the ladder from disk. Returns True on success."""
        if not self.path.exists():
            logger.info("Evidence Ladder: no existing file at %s — starting fresh.", self.path)
            self._loaded = True
            return True
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load evidence ladder: %s", exc)
            return False
        
        # Load metadata
        meta_data = data.get("metadata", {})
        self._metadata = EvidenceLadderMetadata(**meta_data)
        
        # Load hypotheses
        hypotheses_data = data.get("hypotheses", [])
        loaded = 0
        for hd in hypotheses_data:
            try:
                record = HypothesisRecord.from_dict(hd)
                self._hypotheses[record.hypothesis_id] = record
                loaded += 1
            except Exception as exc:
                logger.warning("Skipping corrupt hypothesis record: %s", exc)
        self._loaded = True
        logger.info(
            "Evidence Ladder loaded: %d hypotheses (%d trials) from %s (version=%s).",
            loaded, self._metadata.total_trials, self.path, data.get("version", "?"),
        )
        return True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def __len__(self) -> int:
        return len(self._hypotheses)

    # ── Summary ──────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a structured summary for dashboards."""
        by_level: Dict[str, int] = {}
        by_family: Dict[str, int] = {}
        total = 0
        candidates = 0
        production = 0
        backlog = 0
        archived = 0

        for r in self._hypotheses.values():
            if r.archived:
                archived += 1
                continue
            total += 1
            level_key = f"L{r.evidence_level.value}"
            by_level[level_key] = by_level.get(level_key, 0) + 1
            fam = r.family or "Unclassified"
            by_family[fam] = by_family.get(fam, 0) + 1
            if r.evidence_level >= EvidenceLevel.L4:
                candidates += 1
            if r.evidence_level >= EvidenceLevel.L5:
                production += 1
            if r.evidence_level == EvidenceLevel.L0 and r.retry_count > 0:
                backlog += 1

        return {
            "total_active": total,
            "total_archived": archived,
            "candidates": candidates,
            "production_candidates": production,
            "backlog": backlog,
            "by_level": by_level,
            "by_family": by_family,
        }

    def render_summary(self) -> str:
        """Human-readable summary string."""
        s = self.summary()
        lines = [
            "═══ Evidence Ladder Summary ═══",
            f"  Active hypotheses:    {s['total_active']}",
            f"  Archived:             {s['total_archived']}",
            f"  Candidate alpha (L4+):{s['candidates']}",
            f"  Production ready (L5+):{s['production_candidates']}",
            f"  Backlog (failed L0):  {s['backlog']}",
            "",
            "  By Level:",
        ]
        for lv in range(7):
            key = f"L{lv}"
            count = s["by_level"].get(key, 0)
            label = _LEVEL_LABELS.get(EvidenceLevel(lv), "Unknown")
            lines.append(f"    {key}  {count:>3}  {label}")
        lines.append("")
        lines.append("  By Family:")
        for fam, count in sorted(s["by_family"].items()):
            lines.append(f"    {fam:<25} {count:>3}")
        return "\n".join(lines)


__all__ = [
    "EvidenceLevel",
    "EvidenceLadder",
    "HypothesisRecord",
    "StageResult",
    "PipelineStage",
    "PIPELINE_STAGES",
    "EvidenceScore",
    "compute_evidence_score",
]

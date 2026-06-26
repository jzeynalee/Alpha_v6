# src/core/research_scoreboard.py
"""
Research Scoreboard — tracks research productivity, not software health.

Metrics: hypotheses proposed, experiments completed, hypotheses rejected,
discoveries confirmed, candidates surviving each pipeline stage.

Reads from evidence ladder, knowledge base, and experiment summaries.
Lightweight: pure computation from existing data, no new persistence.

Usage:
    from src.core.research_scoreboard import ResearchScoreboard
    sb = ResearchScoreboard()
    sb.compute()
    print(sb.render())
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResearchScoreboard:
    """Snapshot of research productivity metrics."""

    # Volume
    total_hypotheses_proposed: int = 0
    experiments_completed: int = 0

    # Learning
    hypotheses_rejected: int = 0          # Failed at any stage, now L0
    discoveries_confirmed: int = 0        # KB observations with confidence >= 4

    # Pipeline progression
    surviving_in_sample: int = 0          # L1+
    surviving_transaction_costs: int = 0  # L2+
    surviving_walk_forward: int = 0       # L3+
    surviving_cross_asset: int = 0        # L4+
    reaching_paper_trading: int = 0       # L5+
    promoted_to_production: int = 0       # L6

    # Efficiency
    rejection_rate: float = 0.0           # rejected / (rejected + surviving)
    progression_rate: float = 0.0         # L3+ / total active

    # Metadata
    archived_count: int = 0
    active_count: int = 0

    def compute(
        self,
        ladder_path: str = "data/experiments/evidence_ladder.json",
        kb_path: str = "data/experiments/knowledge_base.json",
        experiments_dir: str = "data/experiments/summaries",
    ) -> None:
        """Compute all metrics from existing data files."""

        # ── Evidence Ladder ────────────────────────────────────────────
        try:
            with open(ladder_path) as f:
                ladder = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            ladder = {"hypotheses": []}

        hypotheses = ladder.get("hypotheses", [])
        self.total_hypotheses_proposed = len(hypotheses)

        self.active_count = sum(1 for h in hypotheses if not h.get("archived", False))
        self.archived_count = sum(1 for h in hypotheses if h.get("archived", False))

        for h in hypotheses:
            level = h.get("evidence_level", 0)
            if level >= 1:
                self.surviving_in_sample += 1
            if level >= 2:
                self.surviving_transaction_costs += 1
            if level >= 3:
                self.surviving_walk_forward += 1
            if level >= 4:
                self.surviving_cross_asset += 1
            if level >= 5:
                self.reaching_paper_trading += 1
            if level >= 6:
                self.promoted_to_production += 1

            if level == 0 and h.get("retry_count", 0) > 0 and not h.get("archived", False):
                self.hypotheses_rejected += 1

        # ── Knowledge Base ─────────────────────────────────────────────
        try:
            with open(kb_path) as f:
                kb = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            kb = {"observations": []}

        self.discoveries_confirmed = sum(
            1 for o in kb.get("observations", [])
            if o.get("confidence", 0) >= 4
        )

        # ── Experiment Summaries ───────────────────────────────────────
        summaries_dir = Path(experiments_dir)
        if summaries_dir.exists():
            self.experiments_completed = len(list(summaries_dir.glob("*.json")))

        # ── Derived metrics ────────────────────────────────────────────
        total_evaluated = self.hypotheses_rejected + sum([
            self.surviving_in_sample,
            self.surviving_transaction_costs,
            self.surviving_walk_forward,
            self.surviving_cross_asset,
            self.reaching_paper_trading,
            self.promoted_to_production,
        ])
        denom = max(total_evaluated, 1)
        self.rejection_rate = self.hypotheses_rejected / denom

        active_denom = max(self.active_count, 1)
        self.progression_rate = self.surviving_walk_forward / active_denom

    def to_dict(self) -> Dict[str, Any]:
        return {
            "volume": {
                "total_hypotheses_proposed": self.total_hypotheses_proposed,
                "active": self.active_count,
                "archived": self.archived_count,
                "experiments_completed": self.experiments_completed,
            },
            "learning": {
                "hypotheses_rejected": self.hypotheses_rejected,
                "discoveries_confirmed": self.discoveries_confirmed,
                "rejection_rate": round(self.rejection_rate, 3),
            },
            "pipeline": {
                "surviving_in_sample_L1": self.surviving_in_sample,
                "surviving_transaction_costs_L2": self.surviving_transaction_costs,
                "surviving_walk_forward_L3": self.surviving_walk_forward,
                "surviving_cross_asset_L4": self.surviving_cross_asset,
                "reaching_paper_trading_L5": self.reaching_paper_trading,
                "promoted_to_production_L6": self.promoted_to_production,
                "progression_rate_L3_plus": round(self.progression_rate, 3),
            },
        }

    def render(self) -> str:
        """Human-readable scoreboard display."""
        d = self.to_dict()
        v = d["volume"]
        l = d["learning"]
        p = d["pipeline"]

        def bar(value: int, max_val: int, width: int = 20) -> str:
            fill = int(min(value / max(max_val, 1), 1.0) * width)
            return "█" * fill + "░" * (width - fill)

        max_proposed = max(v["total_hypotheses_proposed"], 1)

        lines = [
            "╔══════════════════════════════════════════════════════╗",
            "║         RESEARCH SCOREBOARD                          ║",
            "╠══════════════════════════════════════════════════════╣",
            "",
            "  ── Volume ──",
            f"  Hypotheses proposed:     {v['total_hypotheses_proposed']:>5}",
            f"  Active:                  {v['active']:>5}",
            f"  Archived:                {v['archived']:>5}",
            f"  Experiments completed:   {v['experiments_completed']:>5}",
            "",
            "  ── Learning ──",
            f"  Hypotheses rejected:     {l['hypotheses_rejected']:>5}",
            f"  Discoveries confirmed:   {l['discoveries_confirmed']:>5}  (confidence ≥ 4)",
            f"  Rejection rate:          {l['rejection_rate']:.1%}",
            "",
            "  ── Pipeline Progression ──",
            f"  L0  Intuition            {v['active']:>5}  {bar(v['active'], max_proposed)}",
            f"  L1  In-sample            {p['surviving_in_sample_L1']:>5}",
            f"  L2  Transaction costs    {p['surviving_transaction_costs_L2']:>5}",
            f"  L3  Walk-forward         {p['surviving_walk_forward_L3']:>5}  ← hardest gate",
            f"  L4  Cross-asset          {p['surviving_cross_asset_L4']:>5}",
            f"  L5  Paper trading        {p['reaching_paper_trading_L5']:>5}",
            f"  L6  Production           {p['promoted_to_production_L6']:>5}",
            f"  Progression rate (L3+):   {p['progression_rate_L3_plus']:.1%}",
            "",
            "╚══════════════════════════════════════════════════════╝",
        ]

        # Interpretation
        if l["rejection_rate"] > 0.8:
            lines.append("  📊 High rejection rate — pipeline is filtering effectively.")
        if p["promoted_to_production_L6"] == 0:
            lines.append("  🎯 No strategies at production yet. Focus: push ONE through.")
        if l["discoveries_confirmed"] >= 5:
            lines.append("  🧠 Strong knowledge accumulation. Discoveries are compounding.")

        return "\n".join(lines)

    def render_compact(self) -> str:
        """Single-line compact display."""
        return (
            f"Scoreboard: {self.total_hypotheses_proposed} proposed | "
            f"{self.experiments_completed} experiments | "
            f"{self.hypotheses_rejected} rejected | "
            f"{self.discoveries_confirmed} discoveries | "
            f"L3={self.surviving_walk_forward} L4={self.surviving_cross_asset} "
            f"L5={self.reaching_paper_trading} L6={self.promoted_to_production}"
        )


__all__ = ["ResearchScoreboard"]

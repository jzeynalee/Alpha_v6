# src/core/knowledge_graph.py
"""
Knowledge Graph — captures relationships between research entities.

Links discoveries, hypotheses, experiments, and evidence into a queryable graph.
Lightweight: JSON-backed, embeddable, no external dependencies.

Nodes: Discovery, Hypothesis, Experiment, Observation
Edges: supports, contradicts, depends_on, validated_by, invalidated_by, derived_from

Usage:
    from src.core.knowledge_graph import KnowledgeGraph, knowledge_graph
    kg = knowledge_graph()
    kg.add_edge("D003", "supports", "btc_mr_l2")
    related = kg.query("D003")  # everything connected to D003
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Edge:
    """A directed relationship between two research entities."""
    source: str       # e.g. "D003", "btc_mr_l2", "exp_042"
    relation: str     # supports | contradicts | depends_on | validated_by | invalidated_by | derived_from
    target: str       # e.g. "btc_mr_l2", "D005", "zscore_method"
    notes: str = ""


class KnowledgeGraph:
    """
    Queryable graph of research relationships.

    Persisted to data/experiments/knowledge_graph.json.

    Relations:
      - supports: discovery/hypothesis supports another
      - contradicts: discovery/hypothesis contradicts another
      - depends_on: hypothesis depends on a discovery/method
      - validated_by: hypothesis was validated by an experiment
      - invalidated_by: hypothesis was invalidated by an experiment
      - derived_from: hypothesis derived from a discovery
    """

    DEFAULT_PATH = "data/experiments/knowledge_graph.json"

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path or self.DEFAULT_PATH)
        self._edges: List[Edge] = []
        self._loaded = False

    # ── CRUD ──────────────────────────────────────────────────────────────

    def add_edge(self, source: str, relation: str, target: str, notes: str = "") -> None:
        """Add a relationship between two entities."""
        edge = Edge(source=source, relation=relation, target=target, notes=notes)
        self._edges.append(edge)

    def remove_edge(self, source: str, relation: str, target: str) -> bool:
        for i, e in enumerate(self._edges):
            if e.source == source and e.relation == relation and e.target == target:
                del self._edges[i]
                return True
        return False

    # ── Query ─────────────────────────────────────────────────────────────

    def query(self, entity_id: str) -> List[Edge]:
        """Return all edges connected to an entity (either direction)."""
        return [
            e for e in self._edges
            if e.source == entity_id or e.target == entity_id
        ]

    def query_outgoing(self, entity_id: str) -> List[Edge]:
        """Edges where entity is the source."""
        return [e for e in self._edges if e.source == entity_id]

    def query_incoming(self, entity_id: str) -> List[Edge]:
        """Edges where entity is the target."""
        return [e for e in self._edges if e.target == entity_id]

    def query_by_relation(self, relation: str) -> List[Edge]:
        """All edges of a given relation type."""
        return [e for e in self._edges if e.relation == relation]

    def get_supporting(self, entity_id: str) -> List[str]:
        """List of entities that support this one."""
        return [
            e.source for e in self._edges
            if e.target == entity_id and e.relation == "supports"
        ]

    def get_contradicting(self, entity_id: str) -> List[str]:
        """List of entities that contradict this one."""
        return [
            e.source for e in self._edges
            if e.target == entity_id and e.relation == "contradicts"
        ]

    def get_validated_by(self, entity_id: str) -> List[str]:
        """Experiments that validated this hypothesis/discovery."""
        return [
            e.target for e in self._edges
            if e.source == entity_id and e.relation == "validated_by"
        ]

    def get_invalidated_by(self, entity_id: str) -> List[str]:
        """Experiments that invalidated this hypothesis/discovery."""
        return [
            e.target for e in self._edges
            if e.source == entity_id and e.relation == "invalidated_by"
        ]

    def find_path(self, source: str, target: str, max_depth: int = 4) -> Optional[List[Edge]]:
        """Find a path between two entities (BFS, limited depth)."""
        if source == target:
            return []

        visited: Set[str] = {source}
        queue: List[Tuple[str, List[Edge]]] = [(source, [])]

        while queue:
            current, path = queue.pop(0)
            if len(path) >= max_depth:
                continue

            for edge in self._edges:
                neighbor = None
                if edge.source == current and edge.target not in visited:
                    neighbor = edge.target
                elif edge.target == current and edge.source not in visited:
                    neighbor = edge.source
                    edge = Edge(source=neighbor, relation=("back_" + edge.relation), target=current)

                if neighbor:
                    new_path = path + [edge]
                    if neighbor == target:
                        return new_path
                    visited.add(neighbor)
                    queue.append((neighbor, new_path))

        return None

    def query_question(self, question: str) -> List[Edge]:
        """
        Answer structured questions via relation matching.

        Supported patterns:
          - "failed hypotheses involving X" → invalidated_by edges filtered by X
          - "discoveries depending on X" → depends_on edges filtered by X
          - "strategies invalid because D00X" → invalidated_by on D00X
        """
        results: List[Edge] = []

        if "failed" in question.lower() or "invalid" in question.lower():
            for part in question.split():
                results.extend([
                    e for e in self._edges
                    if e.relation == "invalidated_by" and part.upper() in e.source.upper()
                ])

        if "depend" in question.lower():
            for part in question.split():
                results.extend([
                    e for e in self._edges
                    if e.relation == "depends_on" and part.upper() in e.target.upper()
                ])

        if "invalid because" in question.lower():
            # Find discovery ID
            import re
            disc_ids = re.findall(r'D\d+', question)
            for did in disc_ids:
                results.extend([
                    e for e in self._edges
                    if e.relation == "invalidated_by" and e.source == did
                ])

        return results

    def summary(self) -> Dict[str, Any]:
        """Summary statistics."""
        nodes: Set[str] = set()
        by_relation: Dict[str, int] = {}
        for e in self._edges:
            nodes.add(e.source)
            nodes.add(e.target)
            by_relation[e.relation] = by_relation.get(e.relation, 0) + 1

        return {
            "total_edges": len(self._edges),
            "total_nodes": len(nodes),
            "by_relation": by_relation,
        }

    def render_summary(self) -> str:
        s = self.summary()
        lines = [
            "═══ Knowledge Graph ═══",
            f"  Nodes: {s['total_nodes']}",
            f"  Edges: {s['total_edges']}",
            "  Relations:",
        ]
        for rel, count in sorted(s["by_relation"].items()):
            lines.append(f"    {rel:<20} {count:>3}")
        return "\n".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "edges": [{"source": e.source, "relation": e.relation, "target": e.target, "notes": e.notes} for e in self._edges],
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> bool:
        if not self.path.exists():
            self._loaded = True
            return True
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        for ed in data.get("edges", []):
            self._edges.append(Edge(**ed))
        self._loaded = True
        return True

    @property
    def is_loaded(self) -> bool:
        return self._loaded


def create_seeded_graph() -> KnowledgeGraph:
    """Factory: pre-seeded knowledge graph from current discoveries."""
    kg = KnowledgeGraph()

    # ── D003: Z-score > % stretch ────────────────────────────────────────
    kg.add_edge("D003", "supports", "btc_mr_l2", "Z-score is the recommended signal construction for MR")
    kg.add_edge("btc_mr_l2", "depends_on", "D003")
    kg.add_edge("D003", "invalidated_by", "failed_mr_thesis", "Walk-forward PF=0.9 without z-score filtering")
    kg.add_edge("D003", "validated_by", "zscore_vs_pct_stretch", "Z-score PF=1.35 vs pct PF=1.08")

    # ── D004: Funding alone is weak ──────────────────────────────────────
    kg.add_edge("D004", "contradicts", "pos_003", "Funding acceleration alone insufficient")
    kg.add_edge("D004", "supports", "pos_001", "Must combine funding with OI")
    kg.add_edge("D004", "supports", "pos_004", "Funding divergence needs OI context")
    kg.add_edge("pos_003", "depends_on", "D004")

    # ── D005: Walk-forward kills 30-60% PF ───────────────────────────────
    kg.add_edge("D005", "invalidated_by", "walk_forward_btc_mr", "BTC MR: in-sample PF=2.1 → WF PF=1.05")
    kg.add_edge("btc_mr_l2", "depends_on", "D005")
    kg.add_edge("eth_mom_l1", "depends_on", "D005", "Needs walk-forward before any deployment")
    kg.add_edge("sol_mom_l1", "depends_on", "D005")

    # ── D006: Costs destroy apparent alphas ──────────────────────────────
    kg.add_edge("D006", "invalidated_by", "cost_sensitivity_analysis")
    kg.add_edge("exec_001", "depends_on", "D006", "Adaptive exit must beat cost baseline")
    kg.add_edge("exec_002", "depends_on", "D006")

    # ── D001/D002: Cross-asset differences ───────────────────────────────
    kg.add_edge("D001", "contradicts", "eth_mom_l1", "BTC-tuned momentum does not transfer to ETH")
    kg.add_edge("D001", "contradicts", "sol_mom_l1", "BTC-tuned momentum does not transfer to SOL")
    kg.add_edge("btc_mr_l2", "depends_on", "D001")
    kg.add_edge("eth_mom_l1", "depends_on", "D002")
    kg.add_edge("sol_mom_l1", "depends_on", "D002")

    # ── D007: MTF context ────────────────────────────────────────────────
    kg.add_edge("D007", "supports", "mtf_001", "HTF vol context modulates LTF signals")
    kg.add_edge("D007", "supports", "mtf_002", "HTF trend age filters LTF entries")
    kg.add_edge("mtf_001", "derived_from", "D007")
    kg.add_edge("mtf_002", "derived_from", "D007")

    # ── D008: Microstructure differs ─────────────────────────────────────
    kg.add_edge("D008", "contradicts", "micro_001", "LOB imbalance not universal across assets")
    kg.add_edge("micro_001", "depends_on", "D008")
    kg.add_edge("micro_002", "depends_on", "D008")

    # ── D009: BTC MR failed walk-forward ─────────────────────────────────
    kg.add_edge("D009", "invalidated_by", "failed_mr_thesis")
    kg.add_edge("D009", "invalidated_by", "failed_mr_thesis_retry")
    kg.add_edge("btc_mr_l2", "depends_on", "D009", "Re-discovery required with MTF filtering")

    # ── Cross-program links ──────────────────────────────────────────────
    kg.add_edge("exp_001", "depends_on", "D005", "Expansion strategies need walk-forward")
    kg.add_edge("exp_002", "depends_on", "D005")
    kg.add_edge("cs_001", "depends_on", "D001", "Cross-sectional must account for asset differences")
    kg.add_edge("liq_001", "depends_on", "D006", "Liquidation strategies sensitive to costs")
    kg.add_edge("port_001", "depends_on", "D005", "Kelly sizing needs walk-forward validation")

    kg.save()
    logger.info("Knowledge Graph seeded with %d edges.", len(kg._edges))
    return kg


# Module-level singleton
knowledge_graph = KnowledgeGraph()

__all__ = [
    "KnowledgeGraph",
    "Edge",
    "knowledge_graph",
    "create_seeded_graph",
]

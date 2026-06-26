# src/llm/project_memory.py
"""
Project Memory — LLM-friendly state snapshot (Alpha_v6).

Generates a compact, structured summary of the entire project state
that any LLM can consume in a single context window.

Usage:
    python -m src.llm.project_memory
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_ladder_summary(ladder_path: str = "data/experiments/evidence_ladder.json") -> dict:
    """Load evidence ladder summary."""
    try:
        with open(ladder_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"error": "Ladder not found"}
    
    hypotheses = data.get("hypotheses", [])
    by_level = {}
    by_family = {}
    for h in hypotheses:
        lvl = f"L{h.get('evidence_level', 0)}"
        by_level[lvl] = by_level.get(lvl, 0) + 1
        fam = h.get("family", "Unknown")
        by_family[fam] = by_family.get(fam, 0) + 1
    
    return {
        "total": len(hypotheses),
        "active": sum(1 for h in hypotheses if not h.get("archived", False)),
        "archived": sum(1 for h in hypotheses if h.get("archived", False)),
        "by_level": by_level,
        "by_family": by_family,
    }


def _load_kb_summary(kb_path: str = "data/experiments/knowledge_base.json") -> dict:
    """Load knowledge base summary."""
    try:
        with open(kb_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"error": "Knowledge base not found"}
    
    observations = data.get("observations", [])
    by_domain = {}
    by_confidence = {}
    for o in observations:
        domain = o.get("domain", "unknown")
        by_domain[domain] = by_domain.get(domain, 0) + 1
        conf = o.get("confidence", 0)
        label = {5: "Confirmed", 4: "Strong", 3: "Moderate", 2: "Suggestive", 1: "Weak"}.get(conf, "Unknown")
        by_confidence[label] = by_confidence.get(label, 0) + 1
    
    return {
        "total": len(observations),
        "by_domain": by_domain,
        "by_confidence": by_confidence,
    }


def _count_source_files() -> dict:
    """Count source files by directory."""
    src = Path("src")
    if not src.exists():
        return {}
    counts = {}
    for d in sorted(src.iterdir()):
        if d.is_dir() and d.name != "__pycache__":
            py_files = list(d.rglob("*.py"))
            py_files = [f for f in py_files if "__pycache__" not in str(f)]
            if py_files:
                counts[d.name] = len(py_files)
    return counts


def generate_memory() -> Dict[str, Any]:
    """Generate a complete project memory snapshot."""
    return {
        "project": "Alpha_v6",
        "type": "Alpha Research Platform",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_ladder": _load_ladder_summary(),
        "knowledge_base": _load_kb_summary(),
        "source_files": _count_source_files(),
        "entry_files": [
            "PROJECT_STATE.md",
            "NEXT_ACTION.md",
            "ARCHITECTURE.md",
        ],
        "research_programs": [
            "A: Open Interest + Funding",
            "B: Cross-Sectional Momentum",
            "C: Volatility Expansion",
            "D: Liquidations",
            "E: Market Microstructure",
            "F: Multi-Timeframe Context",
            "G: Relative Value",
            "H: Machine Learning",
            "I: Portfolio Construction",
            "J: Execution Research",
        ],
        "key_modules": [
            "src/core/dataset_registry.py",
            "src/core/evidence_ladder.py",
            "src/core/research_pipeline.py",
            "src/core/experiment_manager.py",
            "src/core/knowledge_base.py",
            "src/core/alpha_engine.py",
            "src/core/paper_trading.py",
            "src/core/production_gate.py",
        ],
    }


def main() -> None:
    memory = generate_memory()
    print(json.dumps(memory, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

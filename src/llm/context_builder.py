# src/llm/context_builder.py
"""
Context Builder — builds a minimal context payload for LLM consumption.

Generates a ~2KB JSON containing everything an LLM needs to understand
the current research state without reading 300 files.
"""

from __future__ import annotations

import json
from pathlib import Path


def build_context() -> str:
    """Build a compact LLM context string from entry files."""
    parts = []
    
    for filename in ["PROJECT_STATE.md", "NEXT_ACTION.md", "ARCHITECTURE.md"]:
        path = Path(filename)
        if path.exists():
            parts.append(f"=== {filename} ===\n{path.read_text(encoding='utf-8')[:3000]}")
    
    return "\n\n".join(parts)


def build_minimal_context() -> dict:
    """Build a dict with just the essential facts for an LLM session."""
    return {
        "project": "Alpha_v6",
        "type": "Alpha Research Platform for cryptocurrency markets",
        "data_available": {
            "exchanges": ["binance", "lbank", "nobitex"],
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT", "TONUSDT"],
            "timeframes": ["5m", "15m", "1h", "4h", "1d"],
        },
        "data_access": "from src.core.dataset_registry import registry; registry.get_ohlcv('binance', 'BTCUSDT', '15m')",
        "run_experiment": "from src.core.experiment_manager import ExperimentManager, ExperimentSpec; manager = ExperimentManager()",
        "check_status": "python -m src.llm.project_memory",
        "key_files": [
            "PROJECT_STATE.md", "NEXT_ACTION.md", "ARCHITECTURE.md",
            "src/core/dataset_registry.py", "src/core/evidence_ladder.py",
            "src/core/experiment_manager.py", "src/core/knowledge_base.py",
        ],
        "current_priority": "Get ONE hypothesis through all 10 pipeline stages to production",
    }


if __name__ == "__main__":
    print(json.dumps(build_minimal_context(), indent=2))

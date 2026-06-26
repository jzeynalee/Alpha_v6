# src/llm/prompt_generator.py
"""
Prompt Generator — generates optimized prompts for LLM research sessions.
"""

from __future__ import annotations

from pathlib import Path


def generate_research_prompt(hypothesis_id: str, symbol: str = "BTCUSDT", timeframe: str = "15m") -> str:
    """Generate a prompt for running an experiment on a specific hypothesis."""
    return f"""
TASK: Run experiment on hypothesis '{hypothesis_id}'

CONTEXT:
- Project: Alpha_v6 Research Platform
- Data: Use DatasetRegistry (no hard-coded paths)
- Experiment: Use ExperimentManager for standardized execution

STEPS:
1. Load the evidence ladder
2. Load data for {symbol}/{timeframe} via registry.get_ohlcv()
3. Create ExperimentSpec(hypothesis_id="{hypothesis_id}", symbol="{symbol}", timeframe="{timeframe}")
4. Run experiment via ExperimentManager
5. Record results in ladder and knowledge base
6. Report: stages passed, PF, Sharpe, final evidence level

CONSTRAINTS:
- Do NOT hard-code data paths
- Do NOT create standalone reports
- Record findings in KnowledgeBase
- Run full test suite after changes
""".strip()


def generate_analysis_prompt() -> str:
    """Generate a prompt for analyzing current research state."""
    return """
TASK: Analyze current research state and recommend next actions

STEPS:
1. Read PROJECT_STATE.md, NEXT_ACTION.md, ARCHITECTURE.md
2. Load evidence ladder and knowledge base
3. Identify highest-priority hypotheses without experiments
4. Recommend top 3 experiments to run
5. Report current blockers and data gaps

OUTPUT: Bullet-point list of recommended actions with rationale.
""".strip()


if __name__ == "__main__":
    print(generate_research_prompt("btc_mr_l2"))

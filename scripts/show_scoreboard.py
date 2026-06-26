# scripts/show_scoreboard.py
"""
Display the Research Scoreboard.

Usage:
    python scripts/show_scoreboard.py
    python scripts/show_scoreboard.py --compact
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.research_scoreboard import ResearchScoreboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Display the Research Scoreboard.")
    parser.add_argument("--compact", action="store_true", help="Single-line compact display")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    sb = ResearchScoreboard()
    sb.compute()

    if args.json:
        import json
        print(json.dumps(sb.to_dict(), indent=2))
    elif args.compact:
        print(sb.render_compact())
    else:
        print(sb.render())


if __name__ == "__main__":
    main()

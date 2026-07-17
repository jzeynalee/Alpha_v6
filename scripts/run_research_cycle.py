#!/usr/bin/env python
"""Run a single research cycle using the ExperimentScheduler.

Usage:
    python scripts/run_research_cycle.py [--budget N]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.experiment_scheduler import ExperimentScheduler

def main():
    parser = argparse.ArgumentParser(description="Run automated research cycle")
    parser.add_argument("--budget", "-b", type=int, default=3, help="Number of experiments per cycle")
    args = parser.parse_args()

    scheduler = ExperimentScheduler()
    scheduler.generate_candidates()
    results = scheduler.run_cycle(budget=args.budget)

    for r in results:
        print(f"  {r['mechanism_id']:6s} {r['symbol']:8s} {r['timeframe']:4s} -> {r['status']:10s} {r.get('result_summary', '')}")

    print(f"\nCompleted: {len(results)} experiments. Queue saved to {scheduler.queue_path}")

if __name__ == "__main__":
    main()

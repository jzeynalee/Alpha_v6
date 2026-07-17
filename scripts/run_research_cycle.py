#!/usr/bin/env python
"""Run a single research cycle using the ExperimentScheduler.

Usage:
    python scripts/run_research_cycle.py [--budget N] [--promote M002] [--review]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.experiment_scheduler import ExperimentScheduler

def main():
    parser = argparse.ArgumentParser(description="Run automated research cycle")
    parser.add_argument("--budget", "-b", type=int, default=3, help="Number of experiments per cycle")
    parser.add_argument("--promote", type=str, default=None,
                        help="Run advancement checks for the given mechanism ID (e.g. M002)")
    parser.add_argument("--review", action="store_true",
                        help="Print a detailed evidence summary for all mechanisms and exit.")
    args = parser.parse_args()

    scheduler = ExperimentScheduler()

    if args.review:
        from src.core.mechanism_registry import registry as mech_reg
        from src.core.evidence_ladder import EvidenceLadder
        print("\n===== Mechanism Review =====")
        print(f"{'ID':6s}  {'Name':30s}  {'AccLvl':>6s}  {'Confid':>6s}  {'Rep':>4s}  {'Null':>5s}  {'WF+':>6s}  {'EvidenceLvl':>10s}")
        for mid in sorted(mech_reg._mechanisms.keys()):
            mech = mech_reg.get(mid)
            record = scheduler.ladder.get(mid)
            acc = mech.acceptance_level_name()[:6] if mech else "?"
            conf = mech.confidence_score() if mech else 0.0
            rep = f"{mech.n_assets_replicated}/{mech.n_assets_tested}" if mech else "?/?"
            null = "YES" if (mech and mech.null_model_beaten) else "no "
            wf_pos = f"{mech.n_wf_windows_passed}/{mech.n_wf_windows_total}" if mech else "?/?"
            lev = f"L{record.evidence_level.value} ({record.evidence_level.label})" if record else "—"
            print(f"{mid:6s}  {mech.name[:30]:30s}  {acc:>6s}  {conf:.3f}  {rep:>4s}  {null:>5s}  {wf_pos:>6s}  {lev:>10s}")
            if mech and mech.effect_summary:
                for key, val in mech.effect_summary.items():
                    sig = "★" if val.get('p_value',1) < 0.05 else " "
                    print(f"          {key}: {val.get('mean_bp',0):+7.1f}bp p={val.get('p_value',1):.4f} n={val.get('n_events',0)}{sig}")
            print()
        print("Review complete.\n")
        return

    if args.promote:
        print(f"Advancing mechanism {args.promote} ...")
        scheduler.run_advancement_checks(args.promote)
    else:
        scheduler.generate_candidates()
        results = scheduler.run_cycle(budget=args.budget)

        for r in results:
            print(f"  {r['mechanism_id']:6s} {r['symbol']:8s} {r['timeframe']:4s} -> {r['status']:10s} {r.get('result_summary', '')}")

        print(f"\nCompleted: {len(results)} experiments. Queue saved to {scheduler.queue_path}")

if __name__ == "__main__":
    main()

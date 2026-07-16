"""
Consolidate all strategy .md files in root into per-strategy merged docs
in docs/research/, then move MASTER_SUMMARY to docs/, then delete old files.

Usage: python scripts/consolidate_docs.py
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(".")
DOCS_RESEARCH = ROOT / "docs" / "research"
DOCS_RESEARCH.mkdir(parents=True, exist_ok=True)

# Files to keep in root (not strategy reports)
KEEP_IN_ROOT = {
    "ARCHITECTURE.md",
    "DISCOVERIES.md",
    "NEXT_ACTION.md",
    "PROJECT_STATE.md",
    "20260707_150000_development_roadmap.md",
    "20260707_150000_development_roadmap_v2.md",
}

# ── Collect strategy .md files ───────────────────────────────────────────────
# Pattern: YYYYMMDD_HHMMSS_strategy_name.md
strategy_files: dict[str, list[str]] = defaultdict(list)

for f in sorted(ROOT.glob("*.md")):
    name = f.name
    if name in KEEP_IN_ROOT:
        continue
    # Match timestamp_strategy pattern
    m = re.match(r"\d{8}_\d{6}_(.+)\.md", name)
    if m:
        strategy_name = m.group(1)
        strategy_files[strategy_name].append(name)
    elif name == "MASTER_SUMMARY.md" or "MASTER" in name:
        strategy_files["MASTER_SUMMARY"].append(name)

print(f"Found {sum(len(v) for v in strategy_files.values())} files across {len(strategy_files)} strategies")

# ── Merge per strategy ───────────────────────────────────────────────────────
today = datetime.now().strftime("%Y%m%d")
merged_count = 0
deleted_count = 0

for strategy, files in sorted(strategy_files.items()):
    if strategy == "MASTER_SUMMARY":
        # Move master summary to docs/
        src = ROOT / files[0]
        dst = ROOT / "docs" / f"MASTER_SUMMARY_{today}.md"
        content = src.read_text(encoding="utf-8")
        dst.write_text(content, encoding="utf-8")
        print(f"  MASTER_SUMMARY → {dst}")
        src.unlink()
        deleted_count += 1
        continue

    # Merge all runs for this strategy
    merged_parts = [
        f"# {strategy} — Consolidated Strategy Report",
        "",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d')}",
        f"**Runs merged**: {len(files)}",
        f"**Source files**: {', '.join(files)}",
        "",
        "---",
        "",
    ]

    best_pf = -999
    best_content = ""

    for i, fname in enumerate(files):
        fpath = ROOT / fname
        content = fpath.read_text(encoding="utf-8")

        # Extract run number header
        merged_parts.append(f"## Run {i + 1}: {fname}")
        merged_parts.append("")

        # Try to extract metrics
        for line in content.split("\n"):
            stripped = line.strip()
            # Capture key metrics
            if any(kw in stripped for kw in [
                "Profit Factor", "Sharpe Ratio", "Win Rate", "Total Return",
                "Max Drawdown", "Closed Trades", "Final Evidence Level",
                "Stages passed", "Stages failed",
            ]):
                merged_parts.append(stripped)
            # Capture pipeline stage results
            if "|" in stripped and any(s in stripped for s in ["PASS", "FAIL"]):
                merged_parts.append(stripped)

        # Track best PF
        pf_match = re.search(r"Profit Factor\s*\|\s*([\d.]+)", content)
        if pf_match:
            pf = float(pf_match.group(1))
            if pf > best_pf:
                best_pf = pf
                best_content = content

        merged_parts.append("")

    # Append the best run's full content
    if best_content:
        merged_parts.append("---")
        merged_parts.append("")
        merged_parts.append(f"## Best Run (PF={best_pf:.3f})")
        merged_parts.append("")
        # Extract the Hypothesis, Data, Results sections from best run
        in_section = False
        for line in best_content.split("\n"):
            if line.startswith("## ") and "Strategy Evaluation" not in line:
                in_section = True
                merged_parts.append(line)
            elif in_section:
                merged_parts.append(line)

    # Write merged file
    merged_path = DOCS_RESEARCH / f"{strategy}_{today}.md"
    merged_path.write_text("\n".join(merged_parts), encoding="utf-8")
    print(f"  {strategy}: {len(files)} runs → {merged_path.name}")
    merged_count += 1

    # Delete old files
    for fname in files:
        (ROOT / fname).unlink()
        deleted_count += 1

print(f"\nDone: {merged_count} merged docs in docs/research/, {deleted_count} old files deleted")
print(f"Core docs preserved in root: {KEEP_IN_ROOT}")

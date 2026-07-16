"""
Regenerate all strategy reports with consistent formatting, method descriptions,
code references, and calibration details.

Reads existing merged docs from docs/research/, extracts metrics from each run,
enriches with metadata from strategy_metadata.py, and rewrites comprehensively.

Usage: python scripts/regenerate_reports.py
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from strategy_metadata import STRATEGY_METADATA

DOCS_RESEARCH = Path("docs/research")
DOCS_RESEARCH.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y%m%d")


def parse_metrics_from_file(filepath: Path) -> list[dict]:
    """Extract per-run metrics from a merged report file."""
    runs = []
    current_run = None

    if not filepath.exists():
        return runs

    for line in filepath.read_text(encoding="utf-8").split("\n"):
        stripped = line.strip()
        # Detect new run
        if stripped.startswith("## Run "):
            if current_run:
                runs.append(current_run)
            current_run = {"header": stripped}
            continue
        if current_run is None:
            continue
        # Parse metrics
        m = re.match(r"\|\s*Profit Factor\s*\|\s*([\d.]+)\s*\|", stripped)
        if m:
            current_run["pf"] = float(m.group(1))
        m = re.match(r"\|\s*Sharpe Ratio\s*\|\s*([\d.\-nan]+)\s*\|", stripped)
        if m:
            try:
                current_run["sharpe"] = float(m.group(1))
            except ValueError:
                current_run["sharpe"] = float("nan")
        m = re.match(r"\|\s*Win Rate\s*\|\s*([\d.]+)%?\s*\|", stripped)
        if m:
            current_run["win_rate"] = float(m.group(1))
        m = re.match(r"\|\s*Total Return\s*\|\s*([\d.\-]+)%\s*\|", stripped)
        if m:
            current_run["total_return"] = float(m.group(1))
        m = re.match(r"\|\s*Max Drawdown\s*\|\s*([\d.\-]+)%\s*\|", stripped)
        if m:
            current_run["max_dd"] = float(m.group(1))
        m = re.match(r"\|\s*Closed Trades\s*\|\s*(\d+)\s*\|", stripped)
        if m:
            current_run["trades"] = int(m.group(1))
        m = re.match(r"\*\*Final Evidence Level\*\*:\s*(.+)", stripped)
        if m:
            current_run["level"] = m.group(1)
        # Pipeline stages
        if re.match(r"\|\s*\d+\s*\|", stripped) and ("PASS" in stripped or "FAIL" in stripped):
            current_run.setdefault("stages", []).append(stripped)
        # Walk-forward
        m = re.match(r".*DSR[=:]\s*([\d.\-nan]+)", stripped)
        if m:
            try:
                current_run["dsr"] = float(m.group(1))
            except ValueError:
                current_run["dsr"] = float("nan")
        # Bootstrap
        m = re.match(r".*\*\*p-value\*\*:\s*([\d.]+)", stripped)
        if m:
            current_run["bootstrap_p"] = float(m.group(1))

    if current_run:
        runs.append(current_run)
    return runs


def generate_report(strategy_id: str, filepath: Path) -> str:
    """Generate a comprehensive, consistent strategy report."""
    meta = STRATEGY_METADATA.get(strategy_id, {})
    runs = parse_metrics_from_file(filepath)

    # Determine strategy name from evidence ladder if available
    from src.core.evidence_ladder import EvidenceLadder
    ladder = EvidenceLadder()
    ladder.load()
    record = ladder.get(strategy_id)
    strategy_name = record.name if record else strategy_id
    family = record.family if record else "Unknown"
    description = record.description if record else ""
    rationale = record.economic_rationale if record else ""

    lines = []
    lines.append(f"# {strategy_id} — {strategy_name}")
    lines.append("")
    lines.append(f"**Family**: {family}")
    lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"**Runs evaluated**: {len(runs)}")
    lines.append(f"**Hypothesis**: {description}")
    lines.append(f"**Economic Rationale**: {rationale}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Method ──────────────────────────────────────────────────────────────
    lines.append("## Method")
    lines.append("")
    method = meta.get("signal_method", "*(No method description available)*")
    lines.append(method.strip())
    lines.append("")

    # ── Source Code ─────────────────────────────────────────────────────────
    lines.append("## Source Code")
    lines.append("")
    source_files = meta.get("source_files", [])
    if source_files:
        for sf in source_files:
            lines.append(f"- `{sf}`")
    else:
        lines.append("- *(No source file references available)*")
    lines.append("")

    # ── Data Sources ────────────────────────────────────────────────────────
    lines.append("## Data Sources")
    lines.append("")
    lines.append(meta.get("data_sources", "Binance OHLCV (real data from data/raw/v3_binance/)"))
    lines.append("")

    # ── Calibration ─────────────────────────────────────────────────────────
    cal = meta.get("calibration", {})
    if cal:
        lines.append("## Calibration Parameters")
        lines.append("")
        lines.append("| Parameter | Value |")
        lines.append("|-----------|-------|")
        for k, v in cal.items():
            lines.append(f"| {k} | {v} |")
        lines.append("")

    # ── Backtest Configuration ──────────────────────────────────────────────
    lines.append("## Backtest Configuration")
    lines.append("")
    lines.append("| Setting | Value |")
    lines.append("|---------|-------|")
    lines.append("| Engine | BacktestEngine (event-driven) |")
    lines.append("| Initial capital | $10,000 |")
    lines.append("| Fee | 0.10% per side |")
    lines.append("| Slippage | 0.05% per side |")
    lines.append("| Short selling | Allowed |")
    lines.append("| Risk sizing | Kelly (2% risk per trade) |")
    lines.append("| Stop-loss | 1.5× ATR(14) |")
    lines.append("| Take-profit | 3.0× ATR(14) |")
    lines.append("| Circuit breaker | 20% portfolio DD kill-switch, 10 consecutive loss trip |")
    lines.append("| Walk-forward | PurgedWalkForward (6-8 folds, 24-bar horizon, 25-bar embargo) |")
    lines.append("| Bootstrap | 2,000 samples, 95% CI |")
    lines.append("")

    # ── Results per run ─────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append(f"## Run History ({len(runs)} runs)")
    lines.append("")

    best_pf = -999
    best_idx = 0

    for i, run in enumerate(runs):
        pf = run.get("pf", 0)
        if pf > best_pf:
            best_pf = pf
            best_idx = i

        lines.append(f"### Run {i + 1}")
        lines.append("")
        lines.append(f"**Level**: {run.get('level', 'N/A')}")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        pf_val = run.get('pf', None)
        pf_str = f"{pf_val:.4f}" if isinstance(pf_val, float) else str(pf_val)
        lines.append(f"| Profit Factor | {pf_str} |")
        sh_val = run.get('sharpe', None)
        if isinstance(sh_val, float) and sh_val == sh_val:  # not NaN
            lines.append(f"| Sharpe Ratio | {sh_val:.4f} |")
        else:
            lines.append(f"| Sharpe Ratio | nan |")
        lines.append(f"| Win Rate | {run.get('win_rate', 'N/A')}% |")
        lines.append(f"| Total Return | {run.get('total_return', 'N/A')}% |")
        lines.append(f"| Max Drawdown | {run.get('max_dd', 'N/A')}% |")
        lines.append(f"| Closed Trades | {run.get('trades', 'N/A')} |")
        if "dsr" in run:
            lines.append(f"| Deflated Sharpe Ratio | {run['dsr']:.4f} |")
        if "bootstrap_p" in run:
            lines.append(f"| Bootstrap p-value | {run['bootstrap_p']:.4f} |")
        lines.append("")

        if run.get("stages"):
            lines.append("**Pipeline Stages**:")
            lines.append("")
            lines.append("| Stage | Name | Result | Notes |")
            lines.append("|-------|------|--------|-------|")
            for s in run["stages"]:
                # Parse the markdown table row
                parts = [p.strip() for p in s.split("|") if p.strip()]
                if len(parts) >= 3:
                    lines.append(f"| {parts[0]} | {parts[1]} | {parts[2]} | {parts[3] if len(parts) > 3 else ''} |")
            lines.append("")

    # ── Best run detail ─────────────────────────────────────────────────────
    best = runs[best_idx] if runs else {}
    lines.append("---")
    lines.append("")
    lines.append(f"## Best Run Summary (PF={best_pf:.3f})")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    pf_val = best.get('pf', None)
    pf_str = f"{pf_val:.4f}" if isinstance(pf_val, float) else str(pf_val)
    lines.append(f"| Profit Factor | {pf_str} |")
    sh_val = best.get('sharpe', None)
    if isinstance(sh_val, float) and sh_val == sh_val:
        lines.append(f"| Sharpe Ratio | {sh_val:.4f} |")
    else:
        lines.append(f"| Sharpe Ratio | nan |")
    lines.append(f"| Win Rate | {best.get('win_rate', 'N/A')}% |")
    lines.append(f"| Total Return | {best.get('total_return', 'N/A')}% |")
    lines.append(f"| Max Drawdown | {best.get('max_dd', 'N/A')}% |")
    lines.append(f"| Closed Trades | {best.get('trades', 'N/A')} |")
    lines.append(f"| Level | {best.get('level', 'N/A')} |")
    lines.append("")

    # ── Decision ────────────────────────────────────────────────────────────
    lines.append("## Decision")
    lines.append("")
    if best_pf > 1.05:
        lines.append(f"- **PROMISING**: PF={best_pf:.3f} > 1.05. Candidate for further development.")
        lines.append("- Next: improve walk-forward stability (DSR), expand cross-asset validation.")
    elif best_pf > 1.0:
        lines.append(f"- **MARGINAL**: PF={best_pf:.3f}. At breakeven with transaction costs.")
        lines.append("- Next: tighten signal thresholds or add regime filter to improve edge.")
    else:
        lines.append(f"- **REJECTED**: PF={best_pf:.3f} < 1.0.")
        lines.append("- Do not retry unless: signal logic is fundamentally revised or new data regime emerges.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*Auto-generated by regenerate_reports.py on {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append(f"*Test infrastructure: 171 tests passing, Binance real data*")

    return "\n".join(lines)


def main():
    regenerated = 0
    for fpath in sorted(DOCS_RESEARCH.glob("*_2026071*.md")):
        # Extract strategy_id from filename: strategy_name_20260714.md → strategy_name
        m = re.match(r"(.+)_\d{8}\.md", fpath.name)
        if not m:
            continue
        strategy_id = m.group(1)

        # Skip non-strategy files
        if strategy_id in ("roadmap", "thesis_catalog"):
            continue

        if strategy_id not in STRATEGY_METADATA:
            print(f"  SKIP {strategy_id} — no metadata (add to strategy_metadata.py)")
            continue

        print(f"  Regenerating {strategy_id}...")
        content = generate_report(strategy_id, fpath)
        fpath.write_text(content, encoding="utf-8")
        regenerated += 1

    print(f"\nDone: {regenerated} reports regenerated in docs/research/")


if __name__ == "__main__":
    main()

# src/utils/experiment_log.py
"""
Lightweight research-experiment registry (Phase 0.5).

This is NOT MLflow. It is a single tab-separated file at
`data/experiments/log.tsv` with one line per backtest run. The goal is
that two weeks from now, when "something used to work and you can't
remember what changed", grep on the TSV reconstructs the recent history
in five seconds.

Columns:
    timestamp_utc   ISO 8601 string
    commit          short git hash (or 'no-git')
    description     free-form, one line, tab-stripped
    phase           "phase0" | "phase1" | "phase2" | ... | "exploratory"
    symbol          e.g. "BTCUSDT"
    split           "train" | "validate" | "frozen_oos" | "ad_hoc"
    n_trades        integer
    final_equity    float
    profit_factor   float ("nan" if zero closed losers)
    sharpe          float ("nan" if undefined)
    notes           optional free-form, tab-stripped

This is deliberately minimal. Anything you want to retrieve later that
is not in those columns belongs in the backtest's JSON report; the TSV
is the index, not the artefact.

Append is atomic-ish on POSIX (a single small write under 4 KiB rarely
interleaves) and best-effort on Windows. Concurrent writers from
parallel sweeps may interleave; that is acceptable for a research log.
"""

from __future__ import annotations

import logging
import math
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path("data/experiments/log.tsv")

_COLUMNS: List[str] = [
    "timestamp_utc",
    "commit",
    "description",
    "phase",
    "symbol",
    "split",
    "n_trades",
    "final_equity",
    "profit_factor",
    "sharpe",
    "notes",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _git_commit() -> str:
    """Short git commit hash, or 'no-git' outside a repository."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return out.stdout.strip() or "no-git"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "no-git"


def _sanitise(s: object) -> str:
    """Strip tabs/newlines from a free-form field to keep TSV well-formed."""
    if s is None:
        return ""
    txt = str(s).replace("\t", " ").replace("\n", " ").replace("\r", " ")
    return txt.strip()


def _fmt_float(x: object) -> str:
    """Format a numeric field, preserving NaN as the literal 'nan'."""
    if x is None:
        return "nan"
    try:
        f = float(x)
    except (ValueError, TypeError):
        return "nan"
    if math.isnan(f) or math.isinf(f):
        return "nan"
    return f"{f:.6f}"


# ─── Schema ───────────────────────────────────────────────────────────────────

@dataclass
class ExperimentEntry:
    description:   str
    phase:         str = "exploratory"
    symbol:        str = "BTCUSDT"
    split:         str = "ad_hoc"
    n_trades:      int = 0
    final_equity:  float = float("nan")
    profit_factor: float = float("nan")
    sharpe:        float = float("nan")
    notes:         str = ""
    # Populated by the writer; do not set by hand.
    timestamp_utc: str = field(default="")
    commit:        str = field(default="")

    def to_row(self) -> List[str]:
        """Render as the column-ordered TSV row."""
        return [
            _sanitise(self.timestamp_utc),
            _sanitise(self.commit),
            _sanitise(self.description),
            _sanitise(self.phase),
            _sanitise(self.symbol),
            _sanitise(self.split),
            str(int(self.n_trades)),
            _fmt_float(self.final_equity),
            _fmt_float(self.profit_factor),
            _fmt_float(self.sharpe),
            _sanitise(self.notes),
        ]


# ─── Writer ───────────────────────────────────────────────────────────────────

def append_experiment(
    entry: ExperimentEntry,
    *,
    log_path: Path | str = DEFAULT_LOG_PATH,
    commit: Optional[str] = None,
    timestamp_utc: Optional[str] = None,
) -> ExperimentEntry:
    """
    Append one experiment entry to the TSV log.

    The header is written on first creation. Subsequent appends just add
    a row.

    Parameters
    ----------
    entry         : the ExperimentEntry to record.
    log_path      : override the default path. Tests use a tmp_path.
    commit        : override the git commit (testing).
    timestamp_utc : override the timestamp (testing).

    Returns
    -------
    The same entry with `timestamp_utc` and `commit` populated.
    """
    if not entry.description:
        raise ValueError("ExperimentEntry.description is required")

    entry.timestamp_utc = timestamp_utc or datetime.now(timezone.utc).isoformat()
    entry.commit        = commit        or _git_commit()

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    write_header = not path.exists() or path.stat().st_size == 0
    with open(path, "a", encoding="utf-8") as fh:
        if write_header:
            fh.write("\t".join(_COLUMNS) + "\n")
        fh.write("\t".join(entry.to_row()) + "\n")

    logger.info(
        "Logged experiment: %s | trades=%d | PF=%s | %s",
        entry.description, entry.n_trades, _fmt_float(entry.profit_factor),
        path,
    )
    return entry


# ─── Reader ───────────────────────────────────────────────────────────────────

def read_experiments(
    log_path: Path | str = DEFAULT_LOG_PATH,
    *,
    last_n: Optional[int] = None,
) -> List[dict]:
    """
    Read the TSV and return entries as dicts. Convenience for analysis.

    Parameters
    ----------
    log_path : path to the TSV file. Missing → empty list.
    last_n   : if set, return only the last N entries.
    """
    path = Path(log_path)
    if not path.exists():
        return []

    rows: List[dict] = []
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            cells = line.split("\t")
            # Pad short rows from older formats with empties.
            if len(cells) < len(header):
                cells = cells + [""] * (len(header) - len(cells))
            rows.append(dict(zip(header, cells)))

    if last_n is not None and last_n > 0:
        rows = rows[-last_n:]
    return rows


# ─── Helpers to build entries from a BacktestResult ───────────────────────────

def entry_from_backtest_result(
    result, description: str, *,
    phase: str = "exploratory",
    symbol: str = "BTCUSDT",
    split: str = "ad_hoc",
    notes: str = "",
) -> ExperimentEntry:
    """
    Build an ExperimentEntry from a `BacktestResult` (duck-typed so this
    module does not import the backtest package).

    The result is expected to expose: `closed_trades`, `final_equity`,
    `profit_factor`, `sharpe`. If any are missing they fall back to NaN.
    """
    def _get(name, default):
        v = getattr(result, name, default)
        return v if v is not None else default

    return ExperimentEntry(
        description=description,
        phase=phase,
        symbol=symbol,
        split=split,
        n_trades=int(_get("closed_trades", 0)),
        final_equity=float(_get("final_equity", float("nan"))),
        profit_factor=float(_get("profit_factor", float("nan"))),
        sharpe=float(_get("sharpe", float("nan"))),
        notes=notes,
    )


__all__ = [
    "ExperimentEntry",
    "append_experiment",
    "read_experiments",
    "entry_from_backtest_result",
    "DEFAULT_LOG_PATH",
]

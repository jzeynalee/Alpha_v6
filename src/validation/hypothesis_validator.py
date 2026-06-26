# src/validation/hypothesis_validator.py
"""
Hypothesis-document validator (Phase 2.0).

Phase 2.0 of the v3 plan REQUIRES a written alpha-theses document with
specific structural elements per hypothesis: economic rationale,
falsification condition, encoding features, and capacity classification.

A document without these elements indicates the hypothesis isn't ready
to engineer. Rather than relying on memory, this validator parses the
markdown and rejects documents that:

  * Have 0 hypotheses, or > 3 (the v3 plan says "2-3")
  * Have any hypothesis missing one of the four required sections
  * Still contain placeholder text from the template (the words
    "Example:" or "Replace with" in the rendered prose)
  * Have a capacity classification missing the four required fields

The validator is intentionally strict. A "loose" validator that lets
through under-specified hypotheses defeats its own purpose — Phase 2.0
exists precisely BECAUSE it is the place where vague thinking
catastrophically wastes Phase 2-5 time.

Usage:
    python -m src.validation.hypothesis_validator docs/alpha_theses.md

Exit codes:
    0 — document passes
    1 — document fails (validator prints what's wrong)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ─── Result container ─────────────────────────────────────────────────────────

@dataclass
class HypothesisCheck:
    """A single hypothesis's pass/fail and the reason."""
    index:               int          # 1, 2, or 3
    name:                str
    has_rationale:       bool
    has_falsification:   bool
    has_features:        bool
    has_capacity:        bool
    capacity_fields_ok:  bool
    placeholder_free:    bool
    errors:              List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all([
            self.has_rationale, self.has_falsification, self.has_features,
            self.has_capacity, self.capacity_fields_ok, self.placeholder_free,
        ])


@dataclass
class ValidationReport:
    n_hypotheses:    int
    in_count_range:  bool                       # 2 <= n <= 3
    cross_notes_ok:  bool                       # cross-hypothesis section present
    hypotheses:      List[HypothesisCheck] = field(default_factory=list)
    file_errors:     List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            len(self.file_errors) == 0
            and self.in_count_range
            and self.cross_notes_ok
            and all(h.passed for h in self.hypotheses)
        )

    def render(self) -> str:
        lines = []
        head = "ACCEPTED" if self.passed else "REJECTED"
        lines.append(f"=== Hypothesis document validation: {head} ===")
        lines.append(f"  Hypotheses found: {self.n_hypotheses}  "
                     f"(in range 2-3? {self.in_count_range})")
        lines.append(f"  Cross-hypothesis notes: {self.cross_notes_ok}")
        for h in self.hypotheses:
            mark = "PASS" if h.passed else "FAIL"
            lines.append(f"  [{mark}] H{h.index}: {h.name}")
            for e in h.errors:
                lines.append(f"          → {e}")
        for e in self.file_errors:
            lines.append(f"  [FILE] {e}")
        return "\n".join(lines)


# ─── Parsing helpers ──────────────────────────────────────────────────────────

# Headers and required-element strings the validator looks for.
HYPOTHESIS_HEADER_RE   = re.compile(r"^##\s*Hypothesis\s+(\d+)\s*—\s*(.+?)\s*$", re.MULTILINE)
CROSS_NOTES_HEADER_RE  = re.compile(r"^##\s*Cross-hypothesis notes\s*$", re.MULTILINE)

# Required-section markers (these are bold spans in the template).
SECTION_RATIONALE      = "**Economic rationale**"
SECTION_FALSIFICATION  = "**Falsification condition**"
SECTION_FEATURES       = "**Encoding features**"
SECTION_CAPACITY       = "**Capacity classification**"

CAPACITY_FIELDS = ("Type:", "Expected hold:", "Expected trades/day:",
                   "Notional ceiling:", "Scalability tier:")

# Strings that should NOT survive from the template.
PLACEHOLDER_MARKERS = (
    "Replace with your own",
    "Name your hypothesis here",
    "Name your second hypothesis here",
    "<Name your hypothesis here",
    "<Name your second hypothesis here",
    "<Optional third hypothesis",
    "_Example:_",
    "_(why this inefficiency",
    "_(one observation that would kill",
    "_(2-6 features",
)


def _slice_hypothesis_section(md: str, start: int, next_start: Optional[int]) -> str:
    """Return the markdown text belonging to one hypothesis."""
    return md[start:next_start] if next_start is not None else md[start:]


def _has_section(text: str, marker: str) -> bool:
    """True iff the marker appears AND has non-empty content after it."""
    if marker not in text:
        return False
    # Find content between this marker and the next ** marker or hr.
    idx = text.index(marker) + len(marker)
    after = text[idx:]
    # Strip leading colon, whitespace, and quote markers.
    after = after.split("**")[0]              # stop at next bold section
    after = re.sub(r"^[:\s>_*-]+", "", after, flags=re.MULTILINE)
    # Trim trailing whitespace.
    after = after.strip()
    # Require at least 20 non-whitespace characters of real content.
    real = re.sub(r"\s+", "", after)
    return len(real) >= 20


def _has_all_capacity_fields(text: str) -> bool:
    """The capacity classification must mention each of the four fields."""
    # Find the capacity section.
    if SECTION_CAPACITY not in text:
        return False
    block_start = text.index(SECTION_CAPACITY)
    # Block extends to the next bold section or end of hypothesis.
    block_end = len(text)
    for marker in ("**Why this tier matters**",):
        if marker in text[block_start:]:
            block_end = block_start + text[block_start:].index(marker)
            break
    block = text[block_start:block_end]
    # Each field must appear, AND its placeholder bracket must be removed.
    for field in CAPACITY_FIELDS:
        if field not in block:
            return False
        # Find the value after the field name.
        idx = block.index(field) + len(field)
        # Look at the next ~80 chars.
        snippet = block[idx:idx + 200]
        # The line should have actual content (not just an empty bracket).
        first_line = snippet.split("\n", 1)[0].strip()
        # Reject unfilled brackets like [...] or [low-freq | ...].
        if not first_line or first_line.startswith("[") and "|" in first_line:
            return False
    return True


def _is_placeholder_free(text: str) -> bool:
    """True if no template placeholder strings remain in the text."""
    for marker in PLACEHOLDER_MARKERS:
        if marker in text:
            return False
    return True


# ─── Main validator ───────────────────────────────────────────────────────────

def validate_hypothesis_document(path: Path | str) -> ValidationReport:
    """
    Parse and validate a hypothesis document at ``path``.

    Returns a ValidationReport. Render or inspect its `.passed` attribute.
    """
    p = Path(path)
    report = ValidationReport(n_hypotheses=0, in_count_range=False,
                              cross_notes_ok=False)

    if not p.exists():
        report.file_errors.append(f"file not found: {p}")
        return report

    text = p.read_text(encoding="utf-8")

    # Locate all hypothesis headers.
    matches = list(HYPOTHESIS_HEADER_RE.finditer(text))
    n = len(matches)
    report.n_hypotheses = n
    report.in_count_range = 2 <= n <= 3
    if not report.in_count_range:
        report.file_errors.append(
            f"found {n} hypotheses, but the v3 plan requires 2-3"
        )

    # Cross-hypothesis notes section.
    report.cross_notes_ok = bool(CROSS_NOTES_HEADER_RE.search(text))
    if not report.cross_notes_ok:
        report.file_errors.append(
            "missing '## Cross-hypothesis notes' section"
        )

    # Walk hypotheses.
    for i, m in enumerate(matches):
        next_start = matches[i + 1].start() if i + 1 < len(matches) else None
        # Also stop at the cross-notes section, so its template content
        # doesn't leak into the last hypothesis's analysis.
        cross_match = CROSS_NOTES_HEADER_RE.search(text)
        if cross_match and cross_match.start() > m.start():
            if next_start is None or cross_match.start() < next_start:
                next_start = cross_match.start()

        block = _slice_hypothesis_section(text, m.start(), next_start)
        idx   = int(m.group(1))
        name  = m.group(2).strip()

        hc = HypothesisCheck(
            index=idx, name=name,
            has_rationale=_has_section(block, SECTION_RATIONALE),
            has_falsification=_has_section(block, SECTION_FALSIFICATION),
            has_features=_has_section(block, SECTION_FEATURES),
            has_capacity=SECTION_CAPACITY in block,
            capacity_fields_ok=_has_all_capacity_fields(block),
            placeholder_free=_is_placeholder_free(block),
        )
        if not hc.has_rationale:
            hc.errors.append("Economic rationale missing or too short")
        if not hc.has_falsification:
            hc.errors.append("Falsification condition missing or too short")
        if not hc.has_features:
            hc.errors.append("Encoding features list missing or too short")
        if not hc.has_capacity:
            hc.errors.append("Capacity classification block missing")
        if hc.has_capacity and not hc.capacity_fields_ok:
            hc.errors.append(
                "Capacity classification has empty or unfilled fields "
                f"(need: {', '.join(CAPACITY_FIELDS)})"
            )
        if not hc.placeholder_free:
            hc.errors.append(
                "template placeholder text still present — fill in the "
                "example sections with your own content"
            )
        # Catch a name like "<Name your hypothesis here>" — common slip.
        if name.startswith("<") and name.endswith(">"):
            hc.errors.append(f"hypothesis name is still the placeholder: {name!r}")
            hc.placeholder_free = False
        if name.startswith("_") and "Name" in name:
            hc.errors.append(f"hypothesis name still in template format: {name!r}")
            hc.placeholder_free = False
        report.hypotheses.append(hc)

    return report


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Validate an alpha-theses document.")
    ap.add_argument("path", default="docs/alpha_theses.md", nargs="?",
                    help="path to the hypothesis document")
    args = ap.parse_args(argv)
    report = validate_hypothesis_document(args.path)
    print(report.render())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "validate_hypothesis_document",
    "ValidationReport",
    "HypothesisCheck",
]

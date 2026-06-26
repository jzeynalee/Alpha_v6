# src/core/paths.py
"""
Phase 1 — Centralised path resolution for all offline artefacts.

All artefact paths in the codebase are derived from BASE_DATA_DIR so that
the project can be relocated (or mounted inside Docker) by setting a single
environment variable: ALPHA_FACTORY_DATA_DIR.

Usage
-----
    from src.core.paths import ArtifactPaths

    p = ArtifactPaths()
    p.hmm_dir          # Path("data/offline/hmm")
    p.causal_dir       # Path("data/offline/causal")
    p.calibration_dir  # Path("data/offline/calibration")
    p.model_dir        # Path("data/offline/models")
    p.runtime_dir      # Path("data/runtime")
    p.health_file      # Path("data/runtime/health.json")

    # Versioned file helpers
    p.causal_table("v1")           # Path("data/offline/causal/causal_v1.parquet")
    p.calibration_file("v1")       # Path("data/offline/calibration/evidence_calibration_v1.pkl")
    p.decision_model("v1", "BTCUSDT", "micro")
    # → Path("data/offline/models/decision_model_v1_BTCUSDT_micro.pkl")
"""

from __future__ import annotations

import os
from pathlib import Path


def _base() -> Path:
    """
    Return the project-wide data root.

    Priority:
      1. ALPHA_FACTORY_DATA_DIR environment variable (allows Docker / CI override)
      2. ./data  (default — relative to cwd at runtime)

    Using forward slashes everywhere; pathlib normalises to OS-native separators
    automatically, so this works on Windows without backslash literals.
    """
    env = os.getenv("ALPHA_FACTORY_DATA_DIR", "")
    return Path(env) if env else Path("data")


class ArtifactPaths:
    """
    Single source of truth for every artefact path in the project.

    Instantiate once and pass the object around, or use the module-level
    singleton ``paths`` defined at the bottom of this file.
    """

    def __init__(self, base: Path | None = None) -> None:
        self._base = base if base is not None else _base()

    # ── Directory accessors ──────────────────────────────────────────────────

    @property
    def base(self) -> Path:
        return self._base

    @property
    def offline(self) -> Path:
        return self._base / "offline"

    @property
    def hmm_dir(self) -> Path:
        return self.offline / "hmm"

    @property
    def causal_dir(self) -> Path:
        return self.offline / "causal"

    @property
    def calibration_dir(self) -> Path:
        return self.offline / "calibration"

    @property
    def model_dir(self) -> Path:
        return self.offline / "models"

    @property
    def active_dir(self) -> Path:
        """Symlink-resolved 'active' artefact directory used by the factory."""
        return self.offline / "active"

    @property
    def failure_archive_dir(self) -> Path:
        return self.active_dir / "failure_archive"

    @property
    def raw_dir(self) -> Path:
        return self._base / "raw"

    @property
    def runtime_dir(self) -> Path:
        return self._base / "runtime"

    @property
    def health_file(self) -> Path:
        return self.runtime_dir / "health.json"

    @property
    def daily_state_file(self) -> Path:
        return self._base / "daily_state.json"

    # ── Versioned file helpers ────────────────────────────────────────────────

    def causal_table(self, version: str) -> Path:
        """e.g. data/offline/causal/causal_v1.parquet"""
        return self.causal_dir / f"causal_{version}.parquet"

    def causal_meta(self, version: str) -> Path:
        return self.causal_dir / f"causal_{version}_meta.json"

    def calibration_file(self, version: str) -> Path:
        """e.g. data/offline/calibration/evidence_calibration_v1.pkl"""
        return self.calibration_dir / f"evidence_calibration_{version}.pkl"

    def decision_model(self, version: str, symbol: str, timeframe: str) -> Path:
        """e.g. data/offline/models/decision_model_v1_BTCUSDT_micro.pkl"""
        return self.model_dir / f"decision_model_{version}_{symbol}_{timeframe}.pkl"

    def decision_model_legacy(self, version: str) -> Path:
        """Legacy single-model path: data/offline/models/decision_model_v1.pkl"""
        return self.model_dir / f"decision_model_{version}.pkl"

    def hmm_latest(self) -> Path | None:
        """
        Return the path of the most recent hmm_vX.pkl in hmm_dir, or None.
        Matches the glob pattern used in MarketStructureEngine._load_hmm().
        """
        candidates = sorted(self.hmm_dir.glob("hmm_v*.pkl"), reverse=True)
        return candidates[0] if candidates else None

    # ── Directory creation helper ─────────────────────────────────────────────

    def ensure_dirs(self) -> None:
        """Create all required directories if they do not already exist."""
        for d in (
            self.hmm_dir,
            self.causal_dir,
            self.calibration_dir,
            self.model_dir,
            self.active_dir,
            self.failure_archive_dir,
            self.raw_dir,
            self.runtime_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


# ── Module-level singleton ────────────────────────────────────────────────────
#
# Import this object directly when you only need paths and don't care about
# overriding the base directory:
#
#   from src.core.paths import paths
#   paths.hmm_dir  # → Path("data/offline/hmm")
#
paths = ArtifactPaths()
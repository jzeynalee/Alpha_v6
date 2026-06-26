# tests/conftest.py
"""
Root conftest for Alpha_v6 Research Platform.

Minimal conftest — does not require the full v5 feature pipeline.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def v6_project_root():
    """Return the project root path."""
    from pathlib import Path
    return Path(__file__).resolve().parent.parent

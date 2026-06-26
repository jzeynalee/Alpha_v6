# src/llm/repo_summary.py
"""
Repository Summary — generates a structured summary of the entire repo.
"""

from __future__ import annotations

from pathlib import Path


def summarize_repo() -> dict:
    """Count files by type and return a structured summary."""
    src = Path("src")
    total_py = 0
    by_dir = {}
    
    if src.exists():
        for d in sorted(src.iterdir()):
            if d.is_dir() and d.name != "__pycache__":
                py_files = [f for f in d.rglob("*.py") if "__pycache__" not in str(f)]
                if py_files:
                    total_lines = sum(len(f.read_text(encoding='utf-8', errors='ignore').splitlines()) for f in py_files)
                    by_dir[d.name] = {"files": len(py_files), "lines": total_lines}
                    total_py += len(py_files)
    
    return {
        "project": "Alpha_v6",
        "python_files": total_py,
        "by_directory": by_dir,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(summarize_repo(), indent=2))

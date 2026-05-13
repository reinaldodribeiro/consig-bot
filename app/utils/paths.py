"""Path helpers — PyInstaller-aware (works as script, .venv, and frozen .exe)."""
from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    """Returns the directory where config.json, entrada/, saida/ live.

    - Frozen (PyInstaller onefile): parent of sys.executable.
    - Script: parents[2] of this file (consig-bot/).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).resolve().parents[2]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

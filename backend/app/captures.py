"""Helpers for writing captured artifacts (parser dumps) to disk.

Captures land in <repo_root>/captures so they stay out of the database and are
trivial for Claude to read. The directory is gitignored.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# backend/app/captures.py -> parents[2] is the repository root, independent of CWD.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def captures_dir() -> Path:
    """Directory where captures are written (override with CAPTURES_DIR)."""
    override = os.getenv("CAPTURES_DIR")
    if override:
        return Path(override).expanduser()

    return _REPO_ROOT / "captures"


def slugify(value: str | None, fallback: str = "profile") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return text[:60] or fallback


def unique_path(directory: Path, filename: str) -> Path:
    target = directory / filename
    if not target.exists():
        return target

    stem, suffix = target.stem, target.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

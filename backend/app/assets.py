"""Versioned text assets (prompts, scorecards) under assets/<name>/<version>.md.
Loading fingerprints the bytes, so a snapshot pins the exact text, not just a version tag."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Iterable

from .utils import fingerprint

_VERSION_RE = re.compile(r"v(\d+(?:\.\d+)*)")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

__all__ = ["ASSETS_DIR", "AssetLibrary", "TextAsset", "fingerprint"]


@dataclass(frozen=True)
class TextAsset:
    name: str  # logical path under assets/, e.g. 'prompts/linkedin/suggest'
    version: str
    text: str

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.text)

    def spec(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version, "fingerprint": self.fingerprint}

    def as_template(self, fields: Iterable[str] | None = None) -> Template:
        """Wrap the text as a Template. Pass `fields` to assert the ${placeholders} match
        exactly — catches a prompt whose slots drift from its caller."""
        tpl = Template(self.text)
        if not tpl.is_valid():
            raise ValueError(f"{self.name}/{self.version}: invalid template")
        if fields is not None:
            want, got = set(fields), set(tpl.get_identifiers())
            if want != got:
                raise ValueError(f"{self.name}/{self.version}: fields {sorted(got)} != {sorted(want)}")
        return tpl


class AssetLibrary:
    def __init__(self, base: Path) -> None:
        self.base = base

    def load(self, name: str, version: str) -> TextAsset:
        path = self.base / name / f"{version}.md"
        if not path.is_file():
            raise FileNotFoundError(f"no asset {name}/{version} at {path}")
        return TextAsset(name=name, version=version, text=path.read_text(encoding="utf-8"))

    def latest_version(self, name: str) -> str:
        """Highest version under assets/<name>/, ranked by dotted number (`v2.1` ->
        (2, 1), so v1 < v2 < v2.1 < v10). Not by mtime: git doesn't preserve it, so a
        clone would pick at random. Non-`v<num>[.<num>...].md` files are ignored."""
        best: tuple[tuple[int, ...], str] | None = None
        for path in (self.base / name).glob("*.md"):
            m = _VERSION_RE.fullmatch(path.stem)
            if m is None:
                continue
            key = tuple(int(part) for part in m.group(1).split("."))
            if best is None or key > best[0]:
                best = (key, path.stem)
        if best is None:
            raise FileNotFoundError(f"no versioned assets under {self.base / name}")
        return best[1]

    def load_template(self, name: str, version: str, fields: Iterable[str] | None = None) -> Template:
        """Load an asset and return its text as a validated string.Template. `fields`
        asserts the ${placeholders} match exactly (see TextAsset.as_template)."""
        return self.load(name, version).as_template(fields)

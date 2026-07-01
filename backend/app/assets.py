"""Versioned text assets (prompts, scorecards) under assets/<name>/<version>.md.
Loading fingerprints the bytes, so a snapshot pins the exact text, not just a version tag."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Iterable

from .utils import fingerprint

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

__all__ = ["ASSETS_DIR", "AssetLibrary", "TextAsset", "fingerprint"]


@dataclass(frozen=True)
class TextAsset:
    name: str      # logical path under assets/, e.g. 'prompts/linkedin/suggest'
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

"""One metric set derives both judging schemas and the prompt text, so the modes
can't drift. Schemas are strict (additionalProperties:false, all required) to
validate under both OpenAI text.format and Claude tool-calls — see llm/ STRICT
SCHEMA CONTRACT."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ...utils import fingerprint

RATIONALE_KEY = "rationale"  # reserved; a metric key can't reuse it

PREFERENCE_CHOICES = ("a", "b", "tie")

# a metric bullet: "- `key` (lo-hi): description"
_METRIC_RE = re.compile(r"^-\s*`?(?P<key>[A-Za-z0-9_]+)`?\s*\((?P<lo>\d+)-(?P<hi>\d+)\)\s*:\s*(?P<desc>.+)$")


@dataclass(frozen=True)
class Metric:
    key: str
    description: str
    scale: tuple[int, int] = (1, 5)  # inclusive

    def __post_init__(self) -> None:
        lo, hi = self.scale
        if lo > hi:
            raise ValueError(f"metric {self.key!r} has inverted scale {self.scale}")
        if self.key == RATIONALE_KEY:
            raise ValueError(f"metric key {self.key!r} is reserved")

    @property
    def levels(self) -> list[int]:
        lo, hi = self.scale
        return list(range(lo, hi + 1))


@dataclass(frozen=True)
class Scorecard:
    version: str
    metrics: tuple[Metric, ...]

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValueError("a scorecard needs at least one metric")
        keys = [m.key for m in self.metrics]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            raise ValueError(f"duplicate metric keys: {dupes}")

    @classmethod
    def from_markdown(cls, text: str, *, version: str, section: str = "Metrics") -> "Scorecard":
        """Parse a `## <section>` block of `- `key` (lo-hi): desc` bullets into metrics."""
        return cls(version=version, metrics=tuple(_parse_metrics(text, section)))

    @property
    def metric_keys(self) -> list[str]:
        return [m.key for m in self.metrics]

    @property
    def fingerprint(self) -> str:
        """Content hash of the metrics — moves on an edit even if version isn't bumped."""
        payload = repr([(m.key, m.description, m.scale) for m in self.metrics])
        return fingerprint(payload)

    def spec(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "fingerprint": self.fingerprint,
            "metrics": [{"key": m.key, "scale": list(m.scale)} for m in self.metrics],
        }

    def pointwise_schema(self) -> dict[str, Any]:
        """{metric: int-in-scale for each metric} + rationale."""
        props = {m.key: {"type": "integer", "enum": m.levels} for m in self.metrics}
        return self._object_schema(props)

    def pairwise_schema(self) -> dict[str, Any]:
        """{metric: 'a' | 'b' | 'tie' for each metric} + rationale."""
        props = {m.key: {"type": "string", "enum": list(PREFERENCE_CHOICES)} for m in self.metrics}
        return self._object_schema(props)

    def render(self) -> str:
        """Human-readable scorecard text for the judge prompt."""
        lines = [f"Scorecard (version {self.version}):"]
        for m in self.metrics:
            lo, hi = m.scale
            lines.append(f"- {m.key} ({lo}-{hi}): {m.description}")
        return "\n".join(lines)

    def _object_schema(self, metric_props: dict[str, Any]) -> dict[str, Any]:
        props = {**metric_props, RATIONALE_KEY: {"type": "string"}}
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": props,
            "required": list(props.keys()),
        }


def _section_lines(text: str, section: str) -> list[str]:
    lines, capturing = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            capturing = line[3:].strip().casefold() == section.casefold()
        elif capturing:
            lines.append(line)
    return lines


def _parse_metrics(text: str, section: str) -> list[Metric]:
    metrics = []
    for line in _section_lines(text, section):
        if not line.lstrip().startswith("-"):
            continue  # prose (e.g. the scale legend) between bullets
        match = _METRIC_RE.match(line.strip())
        if match is None:
            raise ValueError(f"unparseable metric bullet: {line!r}")
        metrics.append(Metric(match["key"], match["desc"].strip(), (int(match["lo"]), int(match["hi"]))))
    return metrics

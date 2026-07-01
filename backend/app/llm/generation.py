from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GenConfig:
    model_name: str
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int = 4096
    schema: dict[str, Any] | None = None

    def spec(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "structured": self.schema is not None,
        }


@dataclass(frozen=True)
class Completion:
    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

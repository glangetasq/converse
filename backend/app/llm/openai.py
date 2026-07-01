from __future__ import annotations

from typing import Any

from ..config import settings
from .base import ModelError, ProviderClient
from .generation import Completion, GenConfig


def _strip_json_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


class OpenAIClient(ProviderClient):
    suite = "openai"
    max_temperature = 2.0

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        super().__init__(
            base_url=base_url or settings.openai_api_base_url,
            path="/v1/responses",
            timeout_seconds=timeout_seconds,
        )

    def build_body(self, prompt: str, cfg: GenConfig) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": cfg.model_name,
            "input": self.validate_prompt(prompt),
            "store": False,
        }
        if cfg.schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": cfg.schema.get("title", "response"),
                    "strict": True,
                    "schema": cfg.schema,
                }
            }
        return self.apply_sampling(body, cfg)

    def parse(self, raw: dict[str, Any]) -> Completion:
        node: Any = raw
        for step in ("output", 0, "content", 0, "text"):
            if isinstance(node, list):
                if not isinstance(step, int) or step >= len(node):
                    raise ModelError("OpenAI response missing output[0].content[0].text", response_body=raw)
                node = node[step]
            elif isinstance(node, dict):
                node = node.get(step, {})
            else:
                raise ModelError("OpenAI response missing output[0].content[0].text", response_body=raw)
        if not node:
            raise ModelError("OpenAI response missing output[0].content[0].text", response_body=raw)
        return Completion(
            text=_strip_json_code_fence(node),
            usage=raw.get("usage", {}) or {},
            finish_reason=raw.get("status"),
            raw=raw,
        )

    def build_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ModelError("OPENAI_API_KEY is required for OpenAI API calls.")
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

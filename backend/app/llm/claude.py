from __future__ import annotations

import json
from typing import Any

from ..config import settings
from .base import ModelError, ProviderClient
from .generation import BatchRequest, Completion, GenConfig

STRUCTURED_TOOL_NAME = "respond"


class ClaudeClient(ProviderClient):
    suite = "claude"
    max_temperature = 1.0

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.anthropic_api_key
        self.anthropic_version = settings.anthropic_version
        super().__init__(
            base_url=base_url or settings.claude_api_base_url,
            path="/v1/messages",
            timeout_seconds=timeout_seconds,
        )

    def build_body(self, prompt: str, model: str, cfg: GenConfig) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": cfg.max_tokens,
            "messages": [{"role": "user", "content": self.validate_prompt(prompt)}],
        }
        if cfg.schema is not None:
            # strict=True upgrades soft trained-adherence to a hard schema guarantee;
            # requires the schema to carry additionalProperties:false + all-required.
            body["tools"] = [{"name": STRUCTURED_TOOL_NAME, "input_schema": cfg.schema, "strict": True}]
            body["tool_choice"] = {"type": "tool", "name": STRUCTURED_TOOL_NAME}
        return self.apply_sampling(body, cfg)

    def parse(self, raw: dict[str, Any]) -> Completion:
        blocks = raw.get("content")
        if not isinstance(blocks, list) or not blocks:
            raise ModelError("Claude response missing content[0]", response_body=raw)
        text: str | None = None
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                text = json.dumps(block.get("input", {}))
                break
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text = block["text"]
                break
        if text is None:
            raise ModelError("Claude response had no text or tool_use block", response_body=raw)
        return Completion(
            text=text,
            usage=raw.get("usage", {}) or {},
            finish_reason=raw.get("stop_reason"),
            raw=raw,
        )

    def build_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ModelError("ANTHROPIC_API_KEY is required for Claude API calls.")
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
        }

    def submit_batch(self, requests: list[BatchRequest]) -> str:
        # Message Batches (GA): requests are inline, params == the /v1/messages body.
        payload = {
            "requests": [
                {"custom_id": r.custom_id, "params": self.build_body(r.prompt, r.model, r.cfg)} for r in requests
            ]
        }
        return self._call("POST", "/v1/messages/batches", body=payload)["id"]

    def batch_done(self, batch_id: str) -> bool:
        status = self._call("GET", f"/v1/messages/batches/{batch_id}").get("processing_status")
        if status == "canceling":
            raise ModelError(f"Claude batch {batch_id} is being canceled", response_body={"status": status})
        return status == "ended"

    def batch_results(self, batch_id: str) -> dict[str, tuple[str, Any]]:
        results_url = self._call("GET", f"/v1/messages/batches/{batch_id}").get("results_url")
        if not results_url:
            raise ModelError(f"Claude batch {batch_id} ended without a results_url")
        out: dict[str, tuple[str, Any]] = {}
        for line in self._call("GET", results_url, expect_json=False).splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            result = record.get("result") or {}
            if result.get("type") == "succeeded":
                out[record["custom_id"]] = ("ok", result.get("message") or {})
            else:
                out[record["custom_id"]] = ("error", json.dumps(result.get("error") or result))
        return out

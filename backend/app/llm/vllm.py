"""Self-hosted models behind vLLM's OpenAI-compatible server. vLLM has no Responses
API, so this speaks /v1/chat/completions — a sibling of OpenAIClient, not a subclass.
Model ids are `hosted/<served-model-name>`; the prefix is stripped before the request."""

from __future__ import annotations

from typing import Any

from ..config import settings
from .base import ModelError, ProviderClient, strip_json_code_fence
from .generation import Completion, GenConfig


class VLLMClient(ProviderClient):
    suite = "hosted"
    MODEL_PREFIX = "hosted/"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.hosted_api_key
        super().__init__(
            base_url=base_url or settings.hosted_api_base_url,
            path="/v1/chat/completions",
            timeout_seconds=timeout_seconds if timeout_seconds is not None else settings.hosted_api_timeout_seconds,
        )

    @classmethod
    def served_model(cls, model: str) -> str:
        return model.removeprefix(cls.MODEL_PREFIX)

    @classmethod
    def base_url_for(cls, model: str) -> str:
        return settings.hosted_model_base_urls.get(cls.served_model(model), settings.hosted_api_base_url)

    def build_body(self, prompt: str, model: str, cfg: GenConfig) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.served_model(model),
            "messages": [{"role": "user", "content": self.validate_prompt(prompt)}],
            "max_tokens": cfg.max_tokens,
        }
        if cfg.schema is not None:
            # vLLM structured outputs; older servers want `guided_json` instead.
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": cfg.schema.get("title", "response"),
                    "schema": cfg.schema,
                    "strict": True,
                },
            }
        return self.apply_sampling(body, cfg)

    def parse(self, raw: dict[str, Any]) -> Completion:
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ModelError("vLLM response missing choices[0]", response_body=raw)
        message = choices[0].get("message")
        text = message.get("content") if isinstance(message, dict) else None
        finish_reason = choices[0].get("finish_reason")
        if not isinstance(text, str) or not text.strip():
            detail = f" (finish_reason={finish_reason})" if finish_reason else ""
            raise ModelError(f"vLLM response has no message content{detail}", response_body=raw)
        return Completion(
            text=strip_json_code_fence(text),
            usage=raw.get("usage", {}) or {},
            finish_reason=finish_reason,
            raw=raw,
        )

    def build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

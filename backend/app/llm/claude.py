from __future__ import annotations

from typing import Any

from ..config import settings
from .base import Model, ModelError


class ClaudeModel(Model):
    def __init__(
        self,
        model_name: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        relay_base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int = 4096,
    ) -> None:
        configured_relay_base_url = (
            relay_base_url if relay_base_url is not None else settings.claude_relay_base_url
        )
        self.uses_relay = configured_relay_base_url is not None
        self.api_key = None if self.uses_relay else (
            api_key if api_key is not None else settings.anthropic_api_key
        )
        self.anthropic_version = settings.anthropic_version

        super().__init__(
            suite="claude",
            model_name=model_name,
            path="/anthropic/v1/messages" if self.uses_relay else "/v1/messages",
            base_url=configured_relay_base_url or base_url or settings.claude_api_base_url,
            transport_name="relay" if self.uses_relay else "API",
            timeout_seconds=timeout_seconds,
            max_temperature=1.0,
        )
        self.max_tokens = max_tokens

    def build_request_body(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if response_format is not None:
            raise ModelError("Claude models do not support response_format in this client.")

        body: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": self.validate_prompt(prompt)}],
        }
        return self.add_sampling_parameters(body, temperature=temperature, top_p=top_p)

    def build_request_headers(self) -> dict[str, str]:
        headers = super().build_request_headers()
        if self.uses_relay:
            return headers

        if not self.api_key:
            raise ModelError(
                "ANTHROPIC_API_KEY is required for direct Claude API calls. "
                "Set CLAUDE_RELAY_BASE_URL to use a local relay instead."
            )

        headers["x-api-key"] = self.api_key
        headers["anthropic-version"] = self.anthropic_version
        return headers

    def with_options(
        self,
        *,
        base_url: str | None = None,
        relay_base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> ClaudeModel:
        return ClaudeModel(
            self.model_name,
            base_url=base_url if base_url is not None else (None if self.uses_relay else self.base_url),
            api_key=self.api_key,
            relay_base_url=relay_base_url if relay_base_url is not None else (
                self.base_url if self.uses_relay else None
            ),
            timeout_seconds=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
            max_tokens=self.max_tokens,
        )


ClaudeMessagesModel = ClaudeModel

ClaudeOpus47Model = ClaudeModel("claude-opus-4-7")
ClaudeSonnet46Model = ClaudeModel("claude-sonnet-4-6")
ClaudeHaiku45Model = ClaudeModel("claude-haiku-4-5-20251001")

CLAUDE_MODELS: tuple[ClaudeModel, ...] = (
    ClaudeOpus47Model,
    ClaudeSonnet46Model,
    ClaudeHaiku45Model,
)

from __future__ import annotations

from typing import Any

from ..config import settings
from .base import Model, ModelError


class OpenAIModel(Model):
    def __init__(
        self,
        model_name: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        relay_base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        configured_relay_base_url = (
            relay_base_url if relay_base_url is not None else settings.openai_relay_base_url
        )
        self.uses_relay = configured_relay_base_url is not None
        self.api_key = None if self.uses_relay else (
            api_key if api_key is not None else settings.openai_api_key
        )

        super().__init__(
            suite="openai",
            model_name=model_name,
            path="/openai/v1/responses" if self.uses_relay else "/v1/responses",
            base_url=configured_relay_base_url or base_url or settings.openai_api_base_url,
            transport_name="relay" if self.uses_relay else "API",
            timeout_seconds=timeout_seconds,
        )

    def build_request_body(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model_name,
            "input": self.validate_prompt(prompt),
            "store": False,
        }
        if response_format is not None:
            body["text"] = {"format": response_format}
        return self.add_sampling_parameters(body, temperature=temperature, top_p=top_p)

    def build_request_headers(self) -> dict[str, str]:
        headers = super().build_request_headers()
        if self.uses_relay:
            return headers

        if not self.api_key:
            raise ModelError(
                "OPENAI_API_KEY is required for direct OpenAI API calls. "
                "Set OPENAI_RELAY_BASE_URL to use a local relay instead."
            )

        headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def with_options(
        self,
        *,
        base_url: str | None = None,
        relay_base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> OpenAIModel:
        return OpenAIModel(
            self.model_name,
            base_url=base_url if base_url is not None else (None if self.uses_relay else self.base_url),
            api_key=self.api_key,
            relay_base_url=relay_base_url if relay_base_url is not None else (
                self.base_url if self.uses_relay else None
            ),
            timeout_seconds=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
        )


OpenAIResponsesModel = OpenAIModel

GPT55ProModel = OpenAIModel("gpt-5.5-pro")
GPT55Model = OpenAIModel("gpt-5.5")
GPT54ProModel = OpenAIModel("gpt-5.4-pro")
GPT54Model = OpenAIModel("gpt-5.4")
GPT54MiniModel = OpenAIModel("gpt-5.4-mini")
GPT54NanoModel = OpenAIModel("gpt-5.4-nano")

OPENAI_MODELS: tuple[OpenAIModel, ...] = (
    GPT55ProModel,
    GPT55Model,
    GPT54ProModel,
    GPT54Model,
    GPT54MiniModel,
    GPT54NanoModel,
)

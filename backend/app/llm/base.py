from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from .limiter import LlmCallLimiter


class ModelError(RuntimeError):
    """Raised when a relay-backed model call cannot return an API response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class Model(ABC):
    default_timeout_seconds = 120.0

    def __init__(
        self,
        *,
        suite: str,
        model_name: str,
        path: str,
        base_url: str,
        transport_name: str,
        timeout_seconds: float | None = None,
        max_temperature: float = 2.0,
    ) -> None:
        self.suite = suite
        self.model_name = model_name
        self.path = path
        self.base_url = self._normalize_base_url(base_url)
        self.transport_name = transport_name
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        )
        self.max_temperature = max_temperature

    async def __call__(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        response_format: dict[str, Any] | None = None,
        limiter: LlmCallLimiter | None = None,
    ) -> dict[str, Any]:
        return await self.query(
            prompt,
            temperature=temperature,
            top_p=top_p,
            response_format=response_format,
            limiter=limiter,
        )

    async def query(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        response_format: dict[str, Any] | None = None,
        limiter: LlmCallLimiter | None = None,
    ) -> dict[str, Any]:
        body = self.build_request_body(
            prompt,
            temperature=temperature,
            top_p=top_p,
            response_format=response_format,
        )
        if limiter is not None:
            async with limiter:
                return await asyncio.to_thread(self._post_json, body)

        return await asyncio.to_thread(self._post_json, body)

    async def query_multiple(
        self,
        prompts: Iterable[str],
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        response_format: dict[str, Any] | None = None,
        limiter: LlmCallLimiter | None = None,
        max_concurrency: int = 5,
    ) -> list[dict[str, Any]]:
        if isinstance(prompts, str):
            raise TypeError("prompts must be an iterable of strings")

        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
            raise TypeError("max_concurrency must be an integer")

        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")

        semaphore = asyncio.Semaphore(max_concurrency)

        async def query_one(prompt: str) -> dict[str, Any]:
            if limiter is not None:
                return await self.query(
                    prompt,
                    temperature=temperature,
                    top_p=top_p,
                    response_format=response_format,
                    limiter=limiter,
                )

            async with semaphore:
                return await self.query(
                    prompt,
                    temperature=temperature,
                    top_p=top_p,
                    response_format=response_format,
                )

        return await asyncio.gather(*(query_one(prompt) for prompt in prompts))

    @abstractmethod
    def build_request_body(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def with_options(
        self,
        *,
        base_url: str | None = None,
        relay_base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> "Model":
        raise NotImplementedError

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/{self.path.lstrip('/')}"

    def build_request_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def add_sampling_parameters(
        self,
        body: dict[str, Any],
        *,
        temperature: float | None,
        top_p: float | None,
    ) -> dict[str, Any]:
        if temperature is not None:
            body["temperature"] = self._validate_number(
                "temperature",
                temperature,
                minimum=0.0,
                maximum=self.max_temperature,
            )

        if top_p is not None:
            body["top_p"] = self._validate_number("top_p", top_p, minimum=0.0, maximum=1.0)

        return body

    def validate_prompt(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")

        if not prompt.strip():
            raise ValueError("prompt must not be empty")

        return prompt

    def _post_json(self, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=self.build_request_headers(),
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            response_text = error.read().decode("utf-8", errors="replace")
            response_body = self._decode_json_or_text(response_text)
            raise ModelError(
                self._format_http_error(error.code, response_body),
                status_code=error.code,
                response_body=response_body,
            ) from error
        except urllib.error.URLError as error:
            raise ModelError(
                f"Unable to reach {self.suite} {self.transport_name}: {error.reason}"
            ) from error
        except TimeoutError as error:
            raise ModelError(f"{self.suite} {self.transport_name} request timed out") from error

        decoded = self._decode_json_or_text(response_text)
        if not isinstance(decoded, dict):
            raise ModelError(
                f"{self.suite} {self.transport_name} returned a non-object JSON response",
                response_body=decoded,
            )

        return decoded

    def _format_http_error(self, status_code: int, response_body: Any) -> str:
        if isinstance(response_body, dict):
            error = response_body.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                return (
                    f"{self.suite} {self.transport_name} returned "
                    f"HTTP {status_code}: {error['message']}"
                )
            if isinstance(error, str):
                return f"{self.suite} {self.transport_name} returned HTTP {status_code}: {error}"

        return f"{self.suite} {self.transport_name} returned HTTP {status_code}"

    def _decode_json_or_text(self, response_text: str) -> Any:
        if not response_text:
            return {}

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return response_text

    def _normalize_base_url(self, value: str) -> str:
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute http(s) URL")

        return value.rstrip("/")

    def _validate_number(
        self,
        name: str,
        value: float,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")

        parsed = float(value)
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")

        return parsed

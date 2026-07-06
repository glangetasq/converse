"""ProviderClient owns transport + request shaping + response parsing, so provider
JSON never leaves this layer. A client is a provider connection; `GenConfig` carries
model + decoding params. On a structured call, `schema` is a plain JSON Schema object
each client wraps its own way."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any

from .generation import BatchRequest, Completion, GenConfig
from .execution import ONLINE, LlmExecutionStrategy


class ModelError(RuntimeError):
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


class ProviderClient(ABC):
    suite: str
    max_temperature: float = 2.0
    default_timeout_seconds: float = 120.0

    def __init__(self, *, base_url: str, path: str, timeout_seconds: float | None = None) -> None:
        self.base_url = self._normalize_base_url(base_url)
        self.path = path
        self.timeout_seconds = timeout_seconds or self.default_timeout_seconds

    @abstractmethod
    def build_body(self, prompt: str, model: str, cfg: GenConfig) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: dict[str, Any]) -> Completion:
        raise NotImplementedError

    @abstractmethod
    def build_headers(self) -> dict[str, str]:
        raise NotImplementedError

    # Batch API hooks: providers override these three; run_batch orchestrates them.
    def submit_batch(self, requests: list[BatchRequest]) -> str:
        raise NotImplementedError(f"{self.suite} does not support batch submission")

    def batch_done(self, batch_id: str) -> bool:
        """True once the batch is finished; raises ModelError if it failed/expired."""
        raise NotImplementedError

    def batch_results(self, batch_id: str) -> dict[str, tuple[str, Any]]:
        """custom_id -> ("ok", raw_response) | ("error", message). Raw responses are
        the same shape `parse` consumes for online calls."""
        raise NotImplementedError

    async def run_batch(
        self,
        requests: list[BatchRequest],
        *,
        poll_interval: float = 30.0,
    ) -> dict[str, Completion | ModelError]:
        """Submit a batch, poll to completion, and return one result per custom_id.
        Per-item failures are captured as ModelError rather than raised."""
        if not requests:
            return {}
        batch_id = await asyncio.to_thread(self.submit_batch, requests)
        while not await asyncio.to_thread(self.batch_done, batch_id):
            await asyncio.sleep(poll_interval)
        entries = await asyncio.to_thread(self.batch_results, batch_id)
        out: dict[str, Completion | ModelError] = {}
        for req in requests:
            entry = entries.get(req.custom_id)
            if entry is None:
                out[req.custom_id] = ModelError(f"{self.suite} batch returned no result for {req.custom_id}")
                continue
            kind, payload = entry
            if kind != "ok":
                out[req.custom_id] = ModelError(f"{self.suite} batch item failed: {payload}")
                continue
            try:
                out[req.custom_id] = self.parse(payload)
            except ModelError as error:
                out[req.custom_id] = error
        return out

    async def generate(
        self,
        prompt: str,
        model: str,
        cfg: GenConfig,
        *,
        execution: LlmExecutionStrategy = ONLINE,
    ) -> Completion:
        body = self.build_body(prompt, model, cfg)
        limiter = execution.limiter
        if limiter is not None:
            async with limiter:
                raw = await asyncio.to_thread(self._post_json, body)
        else:
            raw = await asyncio.to_thread(self._post_json, body)
        return self.parse(raw)

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model: str,
        cfg: GenConfig,
        *,
        execution: LlmExecutionStrategy = ONLINE,
    ) -> dict[str, Any]:
        completion = await self.generate(prompt, model, replace(cfg, schema=schema), execution=execution)
        try:
            return json.loads(completion.text)
        except json.JSONDecodeError as error:
            raise ModelError(
                f"{self.suite} structured output was not valid JSON",
                response_body=completion.text,
            ) from error

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/{self.path.lstrip('/')}"

    def apply_sampling(self, body: dict[str, Any], cfg: GenConfig) -> dict[str, Any]:
        if cfg.temperature is not None:
            body["temperature"] = self._validate_number(
                "temperature", cfg.temperature, minimum=0.0, maximum=self.max_temperature
            )
        if cfg.top_p is not None:
            body["top_p"] = self._validate_number("top_p", cfg.top_p, minimum=0.0, maximum=1.0)
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
            headers=self.build_headers(),
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
            raise ModelError(f"Unable to reach {self.suite}: {error.reason}") from error
        except TimeoutError as error:
            raise ModelError(f"{self.suite} request timed out") from error

        decoded = self._decode_json_or_text(response_text)
        if not isinstance(decoded, dict):
            raise ModelError(f"{self.suite} returned a non-object JSON response", response_body=decoded)
        return decoded

    def _call(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        extra_headers: dict[str, str] | None = None,
        expect_json: bool = True,
    ) -> Any:
        """Blocking request to `path` (relative to base_url, or an absolute URL) reusing
        this client's auth + error handling. Used by the Batch API hooks."""
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = dict(self.build_headers())
        if extra_headers is not None:
            headers.update(extra_headers)
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            parsed = self._decode_json_or_text(error.read().decode("utf-8", errors="replace"))
            raise ModelError(
                self._format_http_error(error.code, parsed), status_code=error.code, response_body=parsed
            ) from error
        except urllib.error.URLError as error:
            raise ModelError(f"Unable to reach {self.suite}: {error.reason}") from error
        return self._decode_json_or_text(text) if expect_json else text

    def _format_http_error(self, status_code: int, response_body: Any) -> str:
        if isinstance(response_body, dict):
            error = response_body.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                return f"{self.suite} returned HTTP {status_code}: {error['message']}"
            if isinstance(error, str):
                return f"{self.suite} returned HTTP {status_code}: {error}"
        return f"{self.suite} returned HTTP {status_code}"

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

    def _validate_number(self, name: str, value: float, *, minimum: float, maximum: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")
        parsed = float(value)
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
        return parsed

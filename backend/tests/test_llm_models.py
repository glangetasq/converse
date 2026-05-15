from __future__ import annotations

import asyncio
import unittest
from typing import Any

from app.llm import (
    MODEL_NAMES,
    ClaudeModel,
    ClaudeOpus47Model,
    GPT55Model,
    LlmCallLimiter,
    ModelError,
    OpenAIModel,
    get_model,
)
from app.llm.claude import ClaudeModel as ClaudeModelImplementation
from app.llm.openai import OpenAIModel as OpenAIModelImplementation


class RecordingModel(OpenAIModelImplementation):
    def __init__(self) -> None:
        super().__init__("recording-model", api_key="test-key")
        self.active_queries = 0
        self.max_active_queries = 0
        self.seen_prompts: list[str] = []

    async def query(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        response_format: dict[str, Any] | None = None,
        limiter: LlmCallLimiter | None = None,
    ) -> dict[str, Any]:
        if limiter is not None:
            async with limiter:
                return await self._record_query(prompt, temperature, top_p, response_format)

        return await self._record_query(prompt, temperature, top_p, response_format)

    async def _record_query(
        self,
        prompt: str,
        temperature: float | None,
        top_p: float | None,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.seen_prompts.append(prompt)
        self.active_queries += 1
        self.max_active_queries = max(self.max_active_queries, self.active_queries)
        await asyncio.sleep(0.01)
        self.active_queries -= 1
        return {
            "prompt": prompt,
            "temperature": temperature,
            "top_p": top_p,
            "response_format": response_format,
        }


class LlmModelTests(unittest.TestCase):
    def test_registry_includes_latest_openai_and_claude_models(self) -> None:
        self.assertIn("gpt-5.5-pro", MODEL_NAMES)
        self.assertIn("gpt-5.5", MODEL_NAMES)
        self.assertIn("gpt-5.4-pro", MODEL_NAMES)
        self.assertIn("gpt-5.4", MODEL_NAMES)
        self.assertIn("gpt-5.4-mini", MODEL_NAMES)
        self.assertIn("gpt-5.4-nano", MODEL_NAMES)
        self.assertIn("claude-opus-4-7", MODEL_NAMES)
        self.assertIn("claude-sonnet-4-6", MODEL_NAMES)
        self.assertIn("claude-haiku-4-5-20251001", MODEL_NAMES)

    def test_openai_model_builds_responses_payload(self) -> None:
        model = GPT55Model.with_options(relay_base_url="http://relay.local")

        payload = model.build_request_body("hello", temperature=0.2, top_p=0.9)

        self.assertIsInstance(GPT55Model, OpenAIModel)
        self.assertEqual(model.endpoint, "http://relay.local/openai/v1/responses")
        self.assertEqual(
            payload,
            {
                "model": "gpt-5.5",
                "input": "hello",
                "store": False,
                "temperature": 0.2,
                "top_p": 0.9,
            },
        )

    def test_openai_model_builds_structured_output_payload(self) -> None:
        model = GPT55Model.with_options(relay_base_url="http://relay.local")
        response_format = {
            "type": "json_schema",
            "name": "test_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        }

        payload = model.build_request_body("hello", response_format=response_format)

        self.assertEqual(payload["text"], {"format": response_format})

    def test_openai_model_defaults_to_direct_api(self) -> None:
        model = OpenAIModelImplementation("gpt-test", api_key="test-key")

        self.assertEqual(model.endpoint, "https://api.openai.com/v1/responses")
        self.assertEqual(model.build_request_headers()["Authorization"], "Bearer test-key")

    def test_claude_model_builds_messages_payload(self) -> None:
        model = ClaudeOpus47Model.with_options(relay_base_url="http://relay.local")

        payload = model.build_request_body("hello", temperature=0.2, top_p=0.9)

        self.assertIsInstance(ClaudeOpus47Model, ClaudeModel)
        self.assertEqual(model.endpoint, "http://relay.local/anthropic/v1/messages")
        self.assertEqual(payload["model"], "claude-opus-4-7")
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["messages"], [{"role": "user", "content": "hello"}])
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["top_p"], 0.9)

    def test_claude_model_defaults_to_direct_api(self) -> None:
        model = ClaudeModelImplementation("claude-test", api_key="test-key")

        self.assertEqual(model.endpoint, "https://api.anthropic.com/v1/messages")
        self.assertEqual(model.build_request_headers()["x-api-key"], "test-key")
        self.assertEqual(model.build_request_headers()["anthropic-version"], "2023-06-01")

    def test_get_model_returns_configured_model(self) -> None:
        model = get_model("gpt-5.5", relay_base_url="http://relay.local")

        self.assertIsInstance(model, OpenAIModel)
        self.assertIsNot(model, GPT55Model)
        self.assertEqual(model.endpoint, "http://relay.local/openai/v1/responses")

    def test_get_model_returns_singleton_without_options(self) -> None:
        model = get_model("gpt-5.5")

        self.assertIs(model, GPT55Model)

    def test_direct_api_requires_key(self) -> None:
        model = OpenAIModelImplementation("gpt-test", api_key="")

        with self.assertRaises(ModelError):
            model.build_request_headers()

    def test_sampling_validation(self) -> None:
        model = GPT55Model.with_options(relay_base_url="http://relay.local")

        with self.assertRaises(ValueError):
            model.build_request_body("hello", temperature=3)

        with self.assertRaises(ValueError):
            model.build_request_body("hello", top_p=1.1)

        with self.assertRaises(ValueError):
            model.build_request_body(" ")

    def test_query_multiple_preserves_order_and_limits_concurrency(self) -> None:
        model = RecordingModel()

        results = asyncio.run(
            model.query_multiple(
                ["first", "second", "third", "fourth"],
                temperature=0.4,
                top_p=0.8,
                max_concurrency=2,
            )
        )

        self.assertEqual(
            [result["prompt"] for result in results],
            ["first", "second", "third", "fourth"],
        )
        self.assertEqual({result["temperature"] for result in results}, {0.4})
        self.assertEqual({result["top_p"] for result in results}, {0.8})
        self.assertLessEqual(model.max_active_queries, 2)

    def test_query_multiple_uses_shared_limiter(self) -> None:
        model = RecordingModel()
        limiter = LlmCallLimiter(concurrency=1)

        results = asyncio.run(
            model.query_multiple(
                ["first", "second", "third"],
                limiter=limiter,
                max_concurrency=3,
            )
        )

        self.assertEqual([result["prompt"] for result in results], ["first", "second", "third"])
        self.assertLessEqual(model.max_active_queries, 1)

    def test_query_multiple_requires_positive_concurrency(self) -> None:
        model = RecordingModel()

        with self.assertRaises(ValueError):
            asyncio.run(model.query_multiple(["hello"], max_concurrency=0))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest import mock

from app.llm import GenConfig, ModelError, VLLMClient, get_client, provider_for
from app.llm import registry, vllm

SCHEMA = {"title": "reply", "type": "object", "properties": {"text": {"type": "string"}}}


def _raw(text: str, finish_reason: str = "stop") -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish_reason}],
        "usage": {"total_tokens": 7},
    }


class VLLMBuildBodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = VLLMClient(base_url="http://localhost:8000")

    def test_chat_completions_shape_with_prefix_stripped(self) -> None:
        body = self.client.build_body("hi", "hosted/Qwen/Qwen2.5-7B-Instruct", GenConfig(temperature=0.7, top_p=0.9))
        self.assertEqual(body["model"], "Qwen/Qwen2.5-7B-Instruct")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(body["max_tokens"], 4096)
        self.assertEqual(body["temperature"], 0.7)
        self.assertEqual(body["top_p"], 0.9)

    def test_omits_sampling_when_unset(self) -> None:
        body = self.client.build_body("hi", "hosted/m", GenConfig())
        self.assertNotIn("temperature", body)
        self.assertNotIn("top_p", body)

    def test_schema_maps_to_response_format(self) -> None:
        body = self.client.build_body("hi", "hosted/m", GenConfig(schema=SCHEMA))
        self.assertEqual(
            body["response_format"],
            {"type": "json_schema", "json_schema": {"name": "reply", "schema": SCHEMA, "strict": True}},
        )

    def test_endpoint_targets_chat_completions(self) -> None:
        self.assertEqual(self.client.endpoint, "http://localhost:8000/v1/chat/completions")


class VLLMParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = VLLMClient(base_url="http://localhost:8000")

    def test_extracts_message_content(self) -> None:
        completion = self.client.parse(_raw("hello"))
        self.assertEqual(completion.text, "hello")
        self.assertEqual(completion.usage, {"total_tokens": 7})
        self.assertEqual(completion.finish_reason, "stop")

    def test_strips_json_code_fence(self) -> None:
        self.assertEqual(self.client.parse(_raw('```json\n{"a": 1}\n```')).text, '{"a": 1}')

    def test_missing_choices_raises(self) -> None:
        with self.assertRaisesRegex(ModelError, "choices"):
            self.client.parse({"object": "chat.completion"})

    def test_empty_content_reports_finish_reason(self) -> None:
        with self.assertRaisesRegex(ModelError, "finish_reason=length"):
            self.client.parse(_raw("", finish_reason="length"))


class VLLMHeadersTests(unittest.TestCase):
    def test_no_auth_by_default(self) -> None:
        client = VLLMClient(base_url="http://localhost:8000", api_key="")
        self.assertEqual(client.build_headers(), {"Content-Type": "application/json"})

    def test_bearer_when_key_configured(self) -> None:
        client = VLLMClient(base_url="http://localhost:8000", api_key="secret")
        self.assertEqual(client.build_headers()["Authorization"], "Bearer secret")


class VLLMRoutingTests(unittest.TestCase):
    def test_hosted_prefix_routes_to_hosted_provider(self) -> None:
        self.assertEqual(provider_for("hosted/Qwen/Qwen2.5-7B-Instruct"), "hosted")

    def test_get_client_returns_vllm_client(self) -> None:
        self.assertIsInstance(get_client("hosted/some-model"), VLLMClient)

    def test_models_route_to_their_own_service(self) -> None:
        patched = replace(
            vllm.settings,
            hosted_api_base_url="http://default:8000",
            hosted_model_base_urls={"model-a": "http://model-a:8000"},
        )
        with mock.patch.object(vllm, "settings", patched):
            registry._client.cache_clear()
            client_a = get_client("hosted/model-a")
            client_b = get_client("hosted/model-b")
        self.addCleanup(registry._client.cache_clear)
        self.assertEqual(client_a.base_url, "http://model-a:8000")
        self.assertEqual(client_b.base_url, "http://default:8000")
        self.assertIsNot(client_a, client_b)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import asyncio
import io
import unittest
import urllib.error
from types import SimpleNamespace
from typing import Any
from unittest import mock

from app.llm import embeddings
from app.llm.embeddings import EmbeddingError, OpenAIEmbedder, get_embedder


class StubEmbedder(OpenAIEmbedder):
    """OpenAIEmbedder with the HTTP transport (`_post`) mocked out.

    Returns a canned OpenAI-style payload and records every request body, so the
    embed()/parse orchestration can be tested without touching the network.
    """

    def __init__(self, response: dict[str, Any]) -> None:
        super().__init__()
        self._response = response
        self.bodies: list[dict[str, Any]] = []

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        self.bodies.append(body)
        return self._response


def _fake_settings(api_key: str) -> SimpleNamespace:
    return SimpleNamespace(openai_api_key=api_key, openai_api_base_url="https://api.openai.com")


class EmbedOrchestrationTests(unittest.TestCase):
    def test_empty_input_returns_empty_without_transport_call(self) -> None:
        embedder = StubEmbedder({"data": []})

        self.assertEqual(asyncio.run(embedder.embed([])), [])
        self.assertEqual(embedder.bodies, [])

    def test_sends_model_and_input_and_preserves_order(self) -> None:
        # Response arrives index-shuffled; embed() must reorder to input order.
        embedder = StubEmbedder(
            {
                "data": [
                    {"index": 2, "embedding": [2.0]},
                    {"index": 0, "embedding": [0.0]},
                    {"index": 1, "embedding": [1.0]},
                ]
            }
        )
        inputs = ["zero", "one", "two"]

        vectors = asyncio.run(embedder.embed(inputs))

        self.assertEqual(vectors, [[0.0], [1.0], [2.0]])
        self.assertEqual(
            embedder.bodies,
            [{"model": "text-embedding-3-small", "input": inputs}],
        )

    def test_rejects_non_list_input(self) -> None:
        embedder = StubEmbedder({"data": []})

        with self.assertRaises(TypeError):
            asyncio.run(embedder.embed("not a list"))  # type: ignore[arg-type]
        self.assertEqual(embedder.bodies, [])

    def test_rejects_non_string_items(self) -> None:
        embedder = StubEmbedder({"data": []})

        with self.assertRaises(TypeError):
            asyncio.run(embedder.embed(["ok", 123]))  # type: ignore[list-item]
        self.assertEqual(embedder.bodies, [])

    def test_rejects_count_mismatch(self) -> None:
        embedder = StubEmbedder({"data": [{"index": 0, "embedding": [0.0]}]})

        with self.assertRaises(EmbeddingError):
            asyncio.run(embedder.embed(["a", "b"]))

    def test_rejects_malformed_item(self) -> None:
        embedder = StubEmbedder({"data": [{"index": 0, "embedding": "not-a-list"}]})

        with self.assertRaises(EmbeddingError):
            asyncio.run(embedder.embed(["a"]))

    def test_rejects_incomplete_indices(self) -> None:
        # Two items collide on index 0, leaving slot 1 unfilled.
        embedder = StubEmbedder(
            {
                "data": [
                    {"index": 0, "embedding": [0.1]},
                    {"index": 0, "embedding": [0.2]},
                ]
            }
        )

        with self.assertRaises(EmbeddingError):
            asyncio.run(embedder.embed(["a", "b"]))


class TransportTests(unittest.TestCase):
    def test_post_requires_api_key(self) -> None:
        embedder = OpenAIEmbedder()

        with mock.patch.object(embeddings, "settings", _fake_settings("")):
            with self.assertRaises(EmbeddingError):
                embedder._post({"model": "m", "input": ["x"]})

    def test_post_maps_http_error_to_embedding_error(self) -> None:
        http_error = urllib.error.HTTPError(
            "https://api.openai.com/v1/embeddings",
            429,
            "Too Many Requests",
            None,
            io.BytesIO(b"rate limited"),
        )
        embedder = OpenAIEmbedder()

        with mock.patch.object(embeddings, "settings", _fake_settings("key")), mock.patch(
            "app.llm.embeddings.urllib.request.urlopen", side_effect=http_error
        ):
            with self.assertRaises(EmbeddingError) as ctx:
                embedder._post({"model": "m", "input": ["x"]})

        message = str(ctx.exception)
        self.assertIn("429", message)
        self.assertIn("rate limited", message)

    def test_post_maps_url_error_to_embedding_error(self) -> None:
        embedder = OpenAIEmbedder()

        with mock.patch.object(embeddings, "settings", _fake_settings("key")), mock.patch(
            "app.llm.embeddings.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with self.assertRaises(EmbeddingError) as ctx:
                embedder._post({"model": "m", "input": ["x"]})

        self.assertIn("connection refused", str(ctx.exception))


class FactoryTests(unittest.TestCase):
    def test_get_embedder_returns_cached_singleton(self) -> None:
        self.assertIs(get_embedder(), get_embedder())
        self.assertEqual(get_embedder().dim, 1536)
        self.assertEqual(get_embedder().model_name, "text-embedding-3-small")


if __name__ == "__main__":
    unittest.main()

"""Direct OpenAI text-embedding client.

Deliberately standalone: no dependency on the chat provider clients.
A single batched POST to the OpenAI embeddings endpoint, authenticated with the
API key. Swap `OpenAIEmbedder` for a local/frozen implementation later by keeping
the `Embedder` contract.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from ..config import settings


class EmbeddingError(RuntimeError):
    """Raised when an embedding request cannot be completed."""


class Embedder(ABC):
    """Abstract text-embedding client returning fixed-width float vectors."""

    model_name: str
    dim: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts``, returning one vector per input in the same order.

        Returns ``[]`` for empty input without performing any API call.
        """
        raise NotImplementedError


class OpenAIEmbedder(Embedder):
    """Batched OpenAI embedder calling the API directly."""

    model_name = "text-embedding-3-small"
    dim = 1536

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self._endpoint = settings.openai_api_base_url.rstrip("/") + "/v1/embeddings"
        self._timeout_seconds = timeout_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            raise TypeError("texts must be a list of strings")
        if not texts:
            return []

        response = await asyncio.to_thread(self._post, {"model": self.model_name, "input": texts})
        return self._parse(response, expected_count=len(texts))

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        if not settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY is required for embedding requests.")

        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.openai_api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            raise EmbeddingError(f"OpenAI embeddings HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise EmbeddingError(f"OpenAI embeddings request failed: {error.reason}") from error

    def _parse(self, response: dict[str, Any], *, expected_count: int) -> list[list[float]]:
        data = response.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise EmbeddingError(f"Unexpected embeddings payload: {response}")

        ordered: list[list[float] | None] = [None] * expected_count
        for item in data:
            index = item.get("index") if isinstance(item, dict) else None
            embedding = item.get("embedding") if isinstance(item, dict) else None
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < expected_count
                or not isinstance(embedding, list)
            ):
                raise EmbeddingError(f"Malformed embeddings item: {item}")
            ordered[index] = embedding

        if any(vector is None for vector in ordered):
            raise EmbeddingError("Incomplete embeddings payload (missing index).")

        return [vector for vector in ordered if vector is not None]


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Return a cached, configured :class:`Embedder` singleton."""
    return OpenAIEmbedder()

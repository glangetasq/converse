from __future__ import annotations

import asyncio
import unittest
from typing import Any

from app.llm import BatchRequest, Completion, GenConfig
from app.llm.base import ModelError, ProviderClient


class StubBatchClient(ProviderClient):
    """Overrides the three batch hooks so run_batch's orchestration can be tested
    without a network; `parse` raises on a raw carrying {"boom": True}."""

    suite = "stub"

    def __init__(self, entries: dict[str, tuple[str, Any]]) -> None:
        super().__init__(base_url="https://example.test", path="/v1/x")
        self._entries = entries
        self.submitted: list[BatchRequest] | None = None

    def build_body(self, prompt: str, model: str, cfg: GenConfig) -> dict[str, Any]:
        return {"prompt": prompt}

    def parse(self, raw: dict[str, Any]) -> Completion:
        if raw.get("boom"):
            raise ModelError("unparseable")
        return Completion(text=raw["text"])

    def build_headers(self) -> dict[str, str]:
        return {}

    def submit_batch(self, requests: list[BatchRequest]) -> str:
        self.submitted = requests
        return "batch-1"

    def batch_done(self, batch_id: str) -> bool:
        return True

    def batch_results(self, batch_id: str) -> dict[str, tuple[str, Any]]:
        return self._entries


def _req(custom_id: str) -> BatchRequest:
    return BatchRequest(custom_id=custom_id, prompt=f"p{custom_id}", model="m", cfg=GenConfig())


class RunBatchTests(unittest.TestCase):
    def test_maps_each_outcome_by_custom_id(self) -> None:
        client = StubBatchClient(
            {
                "a": ("ok", {"text": "hello"}),
                "b": ("error", "provider said no"),
                "d": ("ok", {"boom": True}),
            }
        )
        out = asyncio.run(client.run_batch([_req("a"), _req("b"), _req("c"), _req("d")]))

        self.assertEqual(out["a"], Completion(text="hello"))
        self.assertIsInstance(out["b"], ModelError)
        self.assertIn("provider said no", str(out["b"]))
        self.assertIsInstance(out["c"], ModelError)  # missing from batch output
        self.assertIn("no result", str(out["c"]))
        self.assertIsInstance(out["d"], ModelError)  # parse() rejected it

    def test_empty_requests_skip_submission(self) -> None:
        client = StubBatchClient({})
        self.assertEqual(asyncio.run(client.run_batch([])), {})
        self.assertIsNone(client.submitted)


if __name__ == "__main__":
    unittest.main()

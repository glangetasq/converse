from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from unittest import mock

from app.evaluation.linkedin import factory
from app.llm.generation import Completion
from app.prompting import AdditionalContextAugmentor, CompositeAugmentor
from app.prompting.additional_context import HEADER as CONTEXT_HEADER
from app.prompting.builder import Augmentor
from app.retrieval.search import FactRow, RetrievedFact


@dataclass
class Ctx:
    thread: list[Mapping[str, Any]]
    sender_name: str = "Quentin Glangetas"
    recipient_name: str = "Maya Lindqvist"
    meta: Mapping[str, Any] = field(default_factory=dict)


def fact(content: str, fact_id: str = "1", *, person_id: str | None = None) -> FactRow:
    return FactRow(
        id=fact_id,
        person_id=person_id,
        memory_type="about",
        content=content,
        created_at=datetime(2026, 1, 1),
        embedding=[0.0],
    )


class RecordingAugmentor(Augmentor):
    def __init__(self, name: str, marker: str, provenance: dict) -> None:
        self.name = name
        self.marker = marker
        self._provenance = provenance

    async def augment(self, context, prompt):
        return f"{prompt}\n{self.marker}", self.marker, self._provenance


class AdditionalContextAugmentorTests(unittest.IsolatedAsyncioTestCase):
    async def test_appends_context_from_meta(self) -> None:
        ctx = Ctx(thread=[], meta={"additional_context": "Mention the Berlin conference."})
        prompt, evidence, provenance = await AdditionalContextAugmentor().augment(ctx, "BASE")

        self.assertTrue(prompt.startswith("BASE"))
        self.assertIn(CONTEXT_HEADER, prompt)
        self.assertTrue(prompt.rstrip().endswith("Mention the Berlin conference."))
        self.assertIsNone(evidence)  # instruction, not evidence
        self.assertEqual(provenance, {"additional_context": True})

    async def test_blank_context_is_a_noop(self) -> None:
        for value in ("", "   \n ", None):
            ctx = Ctx(thread=[], meta={"additional_context": value})
            prompt, evidence, provenance = await AdditionalContextAugmentor().augment(ctx, "BASE")
            self.assertEqual(prompt, "BASE")
            self.assertIsNone(evidence)
            self.assertEqual(provenance, {})

    async def test_missing_meta_key_is_a_noop(self) -> None:
        prompt, _, provenance = await AdditionalContextAugmentor().augment(Ctx(thread=[], meta={}), "BASE")
        self.assertEqual(prompt, "BASE")
        self.assertEqual(provenance, {})


class CompositeAugmentorTests(unittest.IsolatedAsyncioTestCase):
    async def test_chains_prompt_merges_provenance_concats_evidence(self) -> None:
        composite = CompositeAugmentor(
            [
                RecordingAugmentor("a", "[A]", {"fact_ids": ["1", "2"]}),
                RecordingAugmentor("b", "[B]", {"additional_context": True}),
            ]
        )
        prompt, evidence, provenance = await composite.augment(Ctx(thread=[]), "BASE")

        self.assertEqual(prompt, "BASE\n[A]\n[B]")  # order preserved
        self.assertEqual(evidence, "[A]\n\n[B]")
        self.assertEqual(provenance, {"fact_ids": ["1", "2"], "additional_context": True})

    async def test_spec_lists_children(self) -> None:
        composite = CompositeAugmentor([AdditionalContextAugmentor()])
        spec = composite.spec()
        self.assertEqual(spec["name"], "composite")
        self.assertEqual(spec["augmentors"], [{"name": "additional_context"}])


class StubClient:
    def __init__(self, text: str = "STUB REPLY", *, error: Exception | None = None) -> None:
        self.text = text
        self.error = error

    async def generate(self, prompt, model, cfg, **kwargs):
        if self.error is not None:
            raise self.error
        return Completion(text=self.text, usage={"input_tokens": 3})


def live_kwargs(**overrides) -> dict:
    base = {
        "thread": [{"sender_name": "Quentin Glangetas", "sent_time": None, "body": "Great chat!"}],
        "sender_name": "Quentin Glangetas",
        "recipient_name": "Maya Lindqvist",
        "user_id": "u1",
        "person_id": "p1",
        "additional_context": "Mention the Berlin conference.",
    }
    base.update(overrides)
    return base


class LiveFactoryTests(unittest.IsolatedAsyncioTestCase):
    def stub_retrieval(self, facts):
        async def fake_retrieve(user_id, person_id, thread, *, config):  # noqa: ANN001
            return facts

        return mock.patch("app.prompting.rag.retrieve_facts_for_thread", new=fake_retrieve)

    async def test_preview_orders_rag_then_context_and_surfaces_provenance(self) -> None:
        facts = [RetrievedFact(fact=fact("Quentin ships ML", "42", person_id=None), label="about_you")]
        with self.stub_retrieval(facts):
            prompt = await factory.preview_live("claude-haiku-4-5-20251001", **live_kwargs())

        self.assertLess(prompt.prompt.index("Relevant background:"), prompt.prompt.index(CONTEXT_HEADER))
        self.assertIn("- Quentin ships ML", prompt.prompt)
        self.assertEqual(prompt.fact_ids, ("42",))
        self.assertIsNone(prompt.rag_error)
        self.assertIn("- Quentin ships ML", prompt.evidence)
        augmentors = prompt.spec["builder"]["augment"]["augmentors"]
        self.assertEqual([a["name"] for a in augmentors], ["rag", "additional_context"])

    async def test_preview_degrades_when_retrieval_fails(self) -> None:
        async def boom(*args, **kwargs):  # noqa: ANN001, ANN002
            raise RuntimeError("embedder down")

        with mock.patch("app.prompting.rag.retrieve_facts_for_thread", new=boom):
            prompt = await factory.preview_live("claude-haiku-4-5-20251001", **live_kwargs())

        self.assertNotIn("Relevant background:", prompt.prompt)
        self.assertIn(CONTEXT_HEADER, prompt.prompt)  # context still appended
        self.assertEqual(prompt.rag_error, "embedder down")
        self.assertEqual(prompt.fact_ids, ())

    async def test_generate_returns_text_and_no_error(self) -> None:
        with self.stub_retrieval([]), mock.patch.object(factory, "get_client", return_value=StubClient("HELLO")):
            generation = await factory.generate_live("claude-haiku-4-5-20251001", **live_kwargs())

        self.assertEqual(generation.text, "HELLO")
        self.assertIsNone(generation.error)
        self.assertEqual(generation.usage, {"input_tokens": 3})
        self.assertIn(CONTEXT_HEADER, generation.prompt.prompt)

    async def test_generate_captures_model_error(self) -> None:
        client = StubClient(error=RuntimeError("no api key"))
        with self.stub_retrieval([]), mock.patch.object(factory, "get_client", return_value=client):
            generation = await factory.generate_live("claude-haiku-4-5-20251001", **live_kwargs())

        self.assertEqual(generation.text, "")
        self.assertIn("no api key", generation.error)

    async def test_unknown_model_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            await factory.preview_live("not-a-real-model", **live_kwargs())


if __name__ == "__main__":
    unittest.main()

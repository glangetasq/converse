from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass, field
from datetime import datetime
from string import Template
from typing import Any, Mapping
from unittest.mock import patch

from app.prompting import RagAugmentor, SuggestionPromptBuilder
from app.prompting.builder import Augmentor
from app.retrieval.search import FactRow, RetrievedFact


@dataclass
class Ctx:
    """Minimal PromptContext: thread items are {sender_name, body}."""

    thread: list[Mapping[str, Any]]
    sender_name: str = "Alice"
    recipient_name: str = "Bob"
    meta: Mapping[str, Any] = field(default_factory=dict)


def _fact(content: str, *, person_id: str | None = None) -> FactRow:
    return FactRow(
        id="1",
        person_id=person_id,
        memory_type="about",
        content=content,
        created_at=datetime(2026, 1, 1),
        embedding=[0.0],
    )


class AppendAugmentor(Augmentor):
    name = "append"

    async def augment(self, context: Any, prompt: str) -> str:
        return prompt + "\n[AUG]"


def _template() -> Template:
    return Template("To $recipient_name from $sender_name:\n$thread")


class SuggestionPromptBuilderTests(unittest.TestCase):
    def test_no_augmentor_is_plain_template_substitution(self) -> None:
        builder = SuggestionPromptBuilder(_template(), "v1")
        ctx = Ctx(thread=[{"sender_name": "Alice", "body": "hi"}])

        prompt = asyncio.run(builder.build(ctx))

        self.assertEqual(prompt, "To Bob from Alice:\nAlice: hi")

    def test_augmentor_runs_after_template(self) -> None:
        builder = SuggestionPromptBuilder(_template(), "v1", AppendAugmentor())
        ctx = Ctx(thread=[{"sender_name": "Alice", "body": "hi"}])

        prompt = asyncio.run(builder.build(ctx))

        self.assertTrue(prompt.endswith("\n[AUG]"))
        self.assertIn("To Bob from Alice:", prompt)

    def test_spec_pins_fingerprint_and_reports_augment(self) -> None:
        no_aug = SuggestionPromptBuilder(_template(), "v1").spec()
        with_aug = SuggestionPromptBuilder(_template(), "v1", AppendAugmentor()).spec()

        self.assertEqual(no_aug["version"], "v1")
        self.assertTrue(no_aug["fingerprint"])              # non-empty content hash
        self.assertIsNone(no_aug["augment"])                # no_rag reports no augment
        self.assertEqual(with_aug["augment"], {"name": "append"})
        self.assertEqual(no_aug["fingerprint"], with_aug["fingerprint"])   # same template text


class RagAugmentorTests(unittest.TestCase):
    def _augment(self, facts: list[RetrievedFact], ctx: Ctx | None = None) -> str:
        ctx = ctx or Ctx(
            thread=[{"sender_name": "Alice", "body": "hi"}],
            meta={"user_id": "u1", "person_id": "p1"},
        )

        async def fake_retrieve(user_id, person_id, thread, *, config):  # noqa: ANN001
            return facts

        with patch("app.prompting.rag.retrieve_facts_for_thread", new=fake_retrieve):
            return asyncio.run(RagAugmentor().augment(ctx, "BASE PROMPT"))

    def test_injects_labeled_block(self) -> None:
        facts = [
            RetrievedFact(fact=_fact("Alice ships ML", person_id=None), label="about_you"),
            RetrievedFact(fact=_fact("Bob leads infra", person_id="p1"), label="about_them"),
        ]

        out = self._augment(facts)

        self.assertTrue(out.startswith("BASE PROMPT"))
        self.assertIn("Relevant background:", out)
        self.assertIn("About Alice:", out)
        self.assertIn("- Alice ships ML", out)
        self.assertIn("About Bob:", out)
        self.assertIn("- Bob leads infra", out)

    def test_shared_ground_pairs_both_names(self) -> None:
        pair = RetrievedFact(
            fact=_fact("Alice studied at MIT", person_id=None),
            label="shared_ground",
            matched=_fact("Bob studied at MIT", person_id="p1"),
        )

        out = self._augment([pair])

        self.assertIn("Shared ground:", out)
        self.assertIn("Alice: Alice studied at MIT", out)
        self.assertIn("Bob: Bob studied at MIT", out)

    def test_empty_facts_leaves_prompt_unchanged(self) -> None:
        out = self._augment([])

        self.assertEqual(out, "BASE PROMPT")

    def test_missing_meta_ids_raises_keyerror(self) -> None:
        ctx = Ctx(thread=[{"sender_name": "Alice", "body": "hi"}], meta={"user_id": "u1"})

        with self.assertRaises(KeyError):
            self._augment([], ctx)

    def test_spec_reports_name_and_k(self) -> None:
        spec = RagAugmentor().spec()

        self.assertEqual(spec["name"], "rag")
        self.assertEqual(spec["k"], 8)   # RetrievalConfig default


if __name__ == "__main__":
    unittest.main()

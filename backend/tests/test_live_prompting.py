from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from app.prompting import LiveContext, build_live_prompt
from app.prompting.live import ADDITIONAL_CONTEXT_HEADER


def make_context() -> LiveContext:
    return LiveContext(
        thread=[
            {"sender_name": "Quentin Glangetas", "sent_time": None, "body": "Great meeting you!"},
            {"sender_name": "Maya Lindqvist", "sent_time": None, "body": "Likewise, let's talk soon."},
        ],
        sender_name="Quentin Glangetas",
        recipient_name="Maya Lindqvist",
        meta={"user_id": "u-1", "person_id": "p-1"},
    )


def stub_fact(fact_id: str, matched_id: str | None = None) -> SimpleNamespace:
    matched = SimpleNamespace(id=matched_id) if matched_id else None
    return SimpleNamespace(fact=SimpleNamespace(id=fact_id), matched=matched)


class StubAugmentor:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def augment_with_facts(self, context, prompt):
        facts = [stub_fact("fact-1"), stub_fact("fact-2", matched_id="fact-3")]
        return f"{prompt}\n\nRelevant background:\n- stub fact", "- stub fact", facts

    def spec(self):
        return {"name": "rag", "k": 5}


class FailingAugmentor(StubAugmentor):
    async def augment_with_facts(self, context, prompt):
        raise RuntimeError("embeddings unavailable")


class BuildLivePromptTests(unittest.IsolatedAsyncioTestCase):
    async def test_renders_template_with_thread_and_names(self) -> None:
        with mock.patch("app.prompting.live.RagAugmentor", StubAugmentor):
            built = await build_live_prompt(make_context())

        self.assertIn("Quentin Glangetas", built.prompt)
        self.assertIn("Maya Lindqvist", built.prompt)
        self.assertIn("Quentin Glangetas: Great meeting you!", built.prompt)
        self.assertEqual(built.evidence, "- stub fact")
        self.assertIsNone(built.rag_error)
        self.assertTrue(built.version)
        self.assertEqual(built.fact_ids, ("fact-1", "fact-2", "fact-3"))
        self.assertEqual(built.spec["augment"], {"name": "rag", "k": 5})
        self.assertEqual(built.spec["version"], built.version)
        self.assertTrue(built.spec["fingerprint"])

    async def test_additional_context_is_appended_last(self) -> None:
        with mock.patch("app.prompting.live.RagAugmentor", StubAugmentor):
            built = await build_live_prompt(make_context(), "Mention the Berlin conference.")

        expected_tail = f"{ADDITIONAL_CONTEXT_HEADER}\nMention the Berlin conference."
        self.assertTrue(built.prompt.endswith(expected_tail))
        self.assertGreater(built.prompt.index(ADDITIONAL_CONTEXT_HEADER), built.prompt.index("Relevant background:"))

    async def test_blank_additional_context_is_ignored(self) -> None:
        with mock.patch("app.prompting.live.RagAugmentor", StubAugmentor):
            built = await build_live_prompt(make_context(), "   \n ")

        self.assertNotIn(ADDITIONAL_CONTEXT_HEADER, built.prompt)

    async def test_rag_failure_degrades_to_plain_prompt(self) -> None:
        with mock.patch("app.prompting.live.RagAugmentor", FailingAugmentor):
            built = await build_live_prompt(make_context(), "Keep it short.")

        self.assertIsNone(built.evidence)
        self.assertEqual(built.rag_error, "embeddings unavailable")
        self.assertNotIn("Relevant background:", built.prompt)
        self.assertIn(ADDITIONAL_CONTEXT_HEADER, built.prompt)
        self.assertEqual(built.fact_ids, ())
        self.assertIsNone(built.spec["augment"])


if __name__ == "__main__":
    unittest.main()

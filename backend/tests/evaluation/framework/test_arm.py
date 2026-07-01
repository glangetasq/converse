from __future__ import annotations

import asyncio
import unittest
from typing import Any

from app.evaluation.framework.arm import Arm
from app.evaluation.framework.core import Case
from app.llm import Completion, GenConfig


class StubBuilder:
    """Duck-types SuggestionPromptBuilder: returns a canned prompt, records the case."""

    def __init__(self, prompt: str = "PROMPT", *, raises: Exception | None = None) -> None:
        self._prompt = prompt
        self._raises = raises
        self.built_for: list[str] = []

    async def build(self, case: Case) -> str:
        if self._raises is not None:
            raise self._raises
        self.built_for.append(case.id)
        return self._prompt

    def spec(self) -> dict[str, Any]:
        return {"template": "stub"}


class StubClient:
    """Duck-types ProviderClient.generate."""

    def __init__(
        self, completion: Completion | None = None, *, raises: Exception | None = None
    ) -> None:
        self._completion = completion or Completion(text="hello", usage={"total_tokens": 3})
        self._raises = raises
        self.prompts: list[str] = []

    async def generate(self, prompt: str, cfg: GenConfig, *, limiter: Any = None) -> Completion:
        self.prompts.append(prompt)
        if self._raises is not None:
            raise self._raises
        return self._completion


def _case() -> Case:
    return Case(id="c1", thread=[], sender_name="A", recipient_name="B")


def _arm(builder: Any, client: Any) -> Arm:
    return Arm(name="no_rag", builder=builder, client=client, cfg=GenConfig(model_name="gpt-5.4-nano"))


class ArmRunTests(unittest.TestCase):
    def test_produces_candidate_from_completion(self) -> None:
        client = StubClient(Completion(text="hi there", usage={"total_tokens": 7}))
        arm = _arm(StubBuilder("PROMPT"), client)

        cand = asyncio.run(arm.run(_case(), repeat_index=2))

        self.assertEqual(cand.text, "hi there")
        self.assertEqual(cand.arm_name, "no_rag")
        self.assertEqual(cand.repeat_index, 2)
        self.assertEqual(cand.case_id, "c1")
        self.assertEqual(cand.prompt, "PROMPT")
        self.assertEqual(cand.usage, {"total_tokens": 7})
        self.assertIsNone(cand.error)
        self.assertEqual(client.prompts, ["PROMPT"])

    def test_generation_error_captured_not_raised(self) -> None:
        arm = _arm(StubBuilder(), StubClient(raises=RuntimeError("boom")))

        cand = asyncio.run(arm.run(_case()))

        self.assertEqual(cand.text, "")
        self.assertIsNone(cand.prompt)
        self.assertEqual(cand.error, "RuntimeError: boom")

    def test_builder_error_captured_not_raised(self) -> None:
        client = StubClient()
        arm = _arm(StubBuilder(raises=ValueError("no facts")), client)

        cand = asyncio.run(arm.run(_case()))

        self.assertEqual(cand.error, "ValueError: no facts")
        self.assertEqual(client.prompts, [])   # never reached the model

    def test_spec_round_trips_config(self) -> None:
        arm = _arm(StubBuilder(), StubClient())

        spec = arm.spec()

        self.assertEqual(spec["name"], "no_rag")
        self.assertEqual(spec["builder"], {"template": "stub"})
        self.assertEqual(spec["gen"]["model_name"], "gpt-5.4-nano")


if __name__ == "__main__":
    unittest.main()

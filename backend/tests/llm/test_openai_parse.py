from __future__ import annotations

import unittest

from app.llm import ModelError
from app.llm.openai import OpenAIClient


def _message(text: str) -> dict:
    return {"type": "message", "content": [{"type": "output_text", "text": text}]}


class OpenAIParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = OpenAIClient(api_key="test")

    def test_extracts_message_text(self) -> None:
        raw = {"output": [_message("hello")], "usage": {"total_tokens": 5}, "status": "completed"}
        completion = self.client.parse(raw)
        self.assertEqual(completion.text, "hello")
        self.assertEqual(completion.usage, {"total_tokens": 5})
        self.assertEqual(completion.finish_reason, "completed")

    def test_skips_leading_reasoning_item(self) -> None:
        raw = {"output": [{"type": "reasoning", "summary": []}, _message("answer")], "status": "completed"}
        self.assertEqual(self.client.parse(raw).text, "answer")

    def test_strips_json_code_fence(self) -> None:
        raw = {"output": [_message('```json\n{"a": 1}\n```')]}
        self.assertEqual(self.client.parse(raw).text, '{"a": 1}')

    def test_refusal_raises(self) -> None:
        raw = {"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]}
        with self.assertRaisesRegex(ModelError, "refused"):
            self.client.parse(raw)

    def test_incomplete_reports_reason(self) -> None:
        raw = {
            "output": [{"type": "reasoning"}],
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
        }
        with self.assertRaisesRegex(ModelError, "max_output_tokens"):
            self.client.parse(raw)


if __name__ == "__main__":
    unittest.main()

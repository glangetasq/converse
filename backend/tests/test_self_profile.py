from __future__ import annotations

import unittest

from app.ingestion.self_profile import (
    SelfProfileIngestor,
    parse_self_profile_markdown,
)

SAMPLE = """\
# Quentin — Self Profile

## Headline
- Quentin is an ML Engineer moving into product.

## Networking Goals
- Quentin wants a referral.
- Quentin wants to learn the roles.

## Why I'm Moving to Tech
- Quentin wants real-world product impact.

## Experience
- Quentin is an ML Engineer at Goldman Sachs.

## Education
- Quentin holds an MSc from Columbia.

## Projects
- Quentin built a pricing system.

## Skills
- Python, SQL, Java.
"""


class ParseMarkdownTests(unittest.TestCase):
    def test_title_extracted_but_not_a_memory(self) -> None:
        title, drafts = parse_self_profile_markdown(SAMPLE)
        self.assertEqual(title, "Quentin — Self Profile")
        self.assertNotIn("Quentin — Self Profile", [d.content for d in drafts])

    def test_one_memory_per_bullet(self) -> None:
        _title, drafts = parse_self_profile_markdown(SAMPLE)
        self.assertEqual(len(drafts), 8)
        self.assertEqual(drafts[0].content, "Quentin is an ML Engineer moving into product.")

    def test_section_heading_selects_memory_type(self) -> None:
        _title, drafts = parse_self_profile_markdown(SAMPLE)
        by_type = {}
        for draft in drafts:
            by_type.setdefault(draft.memory_type, []).append(draft.content)
        self.assertEqual(by_type["user.headline"], ["Quentin is an ML Engineer moving into product."])
        self.assertEqual(len(by_type["user.goal"]), 2)
        self.assertEqual(by_type["user.constraint"], ["Quentin wants real-world product impact."])
        self.assertEqual(by_type["user.experience"], ["Quentin is an ML Engineer at Goldman Sachs."])
        self.assertEqual(by_type["user.education"], ["Quentin holds an MSc from Columbia."])
        self.assertEqual(by_type["user.project"], ["Quentin built a pricing system."])
        self.assertEqual(by_type["user.skill"], ["Python, SQL, Java."])

    def test_content_before_first_section_is_ignored(self) -> None:
        _title, drafts = parse_self_profile_markdown("loose text\nmore text\n")
        self.assertEqual(drafts, [])

    def test_wrapped_bullet_joins_into_one_memory(self) -> None:
        text = "## Skills\n- Python and\n  pandas and numpy.\n"
        _title, drafts = parse_self_profile_markdown(text)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].content, "Python and pandas and numpy.")

    def test_paragraph_block_becomes_a_memory(self) -> None:
        text = "## Experience\nQuentin works at Goldman Sachs.\n"
        _title, drafts = parse_self_profile_markdown(text)
        self.assertEqual([d.content for d in drafts], ["Quentin works at Goldman Sachs."])

    def test_unknown_heading_falls_back(self) -> None:
        text = "## Hobbies\n- Quentin plays tennis.\n"
        _title, drafts = parse_self_profile_markdown(text)
        self.assertEqual(drafts[0].memory_type, "user.note")

    def test_html_comment_block_is_stripped(self) -> None:
        # A comment containing heading/bullet syntax must not leak into memories.
        text = "<!--\nguide: ## Section -> user.goal\n- not a real bullet\n-->\n" "## Skills\n- Python.\n"
        _title, drafts = parse_self_profile_markdown(text)
        self.assertEqual([(d.memory_type, d.content) for d in drafts], [("user.skill", "Python.")])


class IngestorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ingestor = SelfProfileIngestor()

    def test_parse_is_a_self_document(self) -> None:
        parsed = self.ingestor.parse(SAMPLE, None)
        self.assertEqual(parsed.kind, "self_profile")
        self.assertEqual(parsed.source, "manual")
        self.assertIsNone(parsed.person)  # person_id stays NULL
        self.assertEqual(parsed.content["markdown"], SAMPLE)
        self.assertEqual(parsed.content["title"], "Quentin — Self Profile")
        self.assertEqual(parsed.raw_text, SAMPLE)

    def test_parse_accepts_markdown_payload_dict(self) -> None:
        parsed = self.ingestor.parse({"markdown": SAMPLE}, None)
        self.assertEqual(parsed.content["markdown"], SAMPLE)

    def test_parse_rejects_unexpected_payload(self) -> None:
        with self.assertRaises(ValueError):
            self.ingestor.parse(123, None)  # type: ignore[arg-type]

    def test_chunk_reads_content_from_document_row(self) -> None:
        document = {"content": {"markdown": SAMPLE}}
        drafts = self.ingestor.chunk(document)
        self.assertEqual(len(drafts), 8)

    def test_chunk_accepts_json_string_content(self) -> None:
        import json

        document = {"content": json.dumps({"markdown": SAMPLE})}
        drafts = self.ingestor.chunk(document)
        self.assertEqual(len(drafts), 8)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.evaluation.framework.scorecard import (
    PREFERENCE_CHOICES,
    RATIONALE_KEY,
    Metric,
    Scorecard,
)


def _scorecard() -> Scorecard:
    return Scorecard(
        version="v1",
        metrics=(
            Metric("relevance", "on-topic", (1, 5)),
            Metric("tone", "matches sender voice", (1, 3)),
        ),
    )


def _assert_strict(test: unittest.TestCase, schema: dict) -> None:
    """Every object node must be strict: additionalProperties:false + all props required."""
    if schema.get("type") == "object":
        props = schema.get("properties", {})
        test.assertIs(schema["additionalProperties"], False)
        test.assertEqual(set(schema["required"]), set(props))
        for sub in props.values():
            _assert_strict(test, sub)
    for sub in schema.get("items", {}) if isinstance(schema.get("items"), dict) else []:
        _assert_strict(test, sub)


class MetricTests(unittest.TestCase):
    def test_levels_are_inclusive(self) -> None:
        self.assertEqual(Metric("m", "d", (1, 5)).levels, [1, 2, 3, 4, 5])
        self.assertEqual(Metric("m", "d", (0, 2)).levels, [0, 1, 2])

    def test_inverted_scale_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Metric("m", "d", (5, 1))

    def test_reserved_key_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Metric(RATIONALE_KEY, "d")


class ScorecardValidationTests(unittest.TestCase):
    def test_empty_scorecard_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scorecard(version="v1", metrics=())

    def test_duplicate_keys_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scorecard(version="v1", metrics=(Metric("m", "a"), Metric("m", "b")))

    def test_metric_keys(self) -> None:
        self.assertEqual(_scorecard().metric_keys, ["relevance", "tone"])


class ScorecardFingerprintTests(unittest.TestCase):
    def test_fingerprint_stable_for_same_metrics(self) -> None:
        self.assertEqual(_scorecard().fingerprint, _scorecard().fingerprint)

    def test_fingerprint_changes_when_a_description_changes(self) -> None:
        edited = Scorecard(
            version="v1",  # deliberately NOT bumped — the fingerprint must still move
            metrics=(
                Metric("relevance", "on-topic AND useful", (1, 5)),
                Metric("tone", "matches sender voice", (1, 3)),
            ),
        )
        self.assertNotEqual(_scorecard().fingerprint, edited.fingerprint)

    def test_spec_carries_version_fingerprint_and_metrics(self) -> None:
        spec = _scorecard().spec()
        self.assertEqual(spec["version"], "v1")
        self.assertEqual(spec["fingerprint"], _scorecard().fingerprint)
        self.assertEqual(
            spec["metrics"],
            [{"key": "relevance", "scale": [1, 5]}, {"key": "tone", "scale": [1, 3]}],
        )


class PointwiseSchemaTests(unittest.TestCase):
    def test_one_property_per_metric_plus_rationale(self) -> None:
        schema = _scorecard().pointwise_schema()
        self.assertEqual(
            set(schema["properties"]),
            {"relevance", "tone", RATIONALE_KEY},
        )

    def test_scores_are_int_enums_over_scale(self) -> None:
        schema = _scorecard().pointwise_schema()
        self.assertEqual(schema["properties"]["relevance"]["enum"], [1, 2, 3, 4, 5])
        self.assertEqual(schema["properties"]["tone"]["enum"], [1, 2, 3])
        self.assertEqual(schema["properties"]["relevance"]["type"], "integer")

    def test_strict(self) -> None:
        _assert_strict(self, _scorecard().pointwise_schema())


class PairwiseSchemaTests(unittest.TestCase):
    def test_one_property_per_metric_plus_rationale(self) -> None:
        schema = _scorecard().pairwise_schema()
        self.assertEqual(
            set(schema["properties"]),
            {"relevance", "tone", RATIONALE_KEY},
        )

    def test_preferences_are_abc_tie_enums(self) -> None:
        schema = _scorecard().pairwise_schema()
        self.assertEqual(schema["properties"]["tone"]["type"], "string")
        self.assertEqual(schema["properties"]["tone"]["enum"], list(PREFERENCE_CHOICES))

    def test_strict(self) -> None:
        _assert_strict(self, _scorecard().pairwise_schema())


class RenderTests(unittest.TestCase):
    def test_render_lists_every_metric_with_scale(self) -> None:
        text = _scorecard().render()
        self.assertIn("version v1", text)
        self.assertIn("relevance (1-5): on-topic", text)
        self.assertIn("tone (1-3): matches sender voice", text)


_MARKDOWN = """
## Metrics

Score each axis on its scale.

- `relevance` (1-5): on-topic given the thread
- `tone` (1-3): matches sender voice

## Other
- ignored: not a metric bullet
"""


class FromMarkdownTests(unittest.TestCase):
    def test_parses_key_description_and_scale_from_section(self) -> None:
        sc = Scorecard.from_markdown(_MARKDOWN, version="v1")
        self.assertEqual(sc.version, "v1")
        self.assertEqual(sc.metric_keys, ["relevance", "tone"])  # order preserved
        relevance, tone = sc.metrics
        self.assertEqual((relevance.description, relevance.scale), ("on-topic given the thread", (1, 5)))
        self.assertEqual(tone.scale, (1, 3))

    def test_only_the_named_section_is_read(self) -> None:
        sc = Scorecard.from_markdown(_MARKDOWN, version="v1")
        self.assertNotIn("ignored", sc.metric_keys)  # bullets outside ## Metrics are skipped

    def test_malformed_bullet_raises(self) -> None:
        bad = "## Metrics\n- relevance: no scale here\n"
        with self.assertRaises(ValueError):
            Scorecard.from_markdown(bad, version="v1")

    def test_missing_section_yields_no_metrics_and_raises(self) -> None:
        with self.assertRaises(ValueError):
            Scorecard.from_markdown("## Nope\n- `x` (1-5): y", version="v1")


if __name__ == "__main__":
    unittest.main()

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
        self.assertEqual(
            schema["properties"]["tone"]["enum"], list(PREFERENCE_CHOICES)
        )

    def test_strict(self) -> None:
        _assert_strict(self, _scorecard().pairwise_schema())


class RenderTests(unittest.TestCase):
    def test_render_lists_every_metric_with_scale(self) -> None:
        text = _scorecard().render()
        self.assertIn("version v1", text)
        self.assertIn("relevance (1-5): on-topic", text)
        self.assertIn("tone (1-3): matches sender voice", text)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.evaluation.linkedin.factory import LIBRARY, SCORECARD, scorecard

_EXPECTED_METRICS = {
    "contextual_relevance",
    "natural_next_move",
    "actual_message_overlap",
    "inferable_goal_coverage",
    "private_intent_coverage",
    "groundedness",
    "tone_match",
    "clarity",
}


class ScorecardTests(unittest.TestCase):
    def test_parsed_from_asset_with_eight_metrics(self) -> None:
        sc = scorecard()
        self.assertEqual(set(sc.metric_keys), _EXPECTED_METRICS)
        self.assertEqual(sc.version, "v1")

    def test_pointwise_schema_is_strict_and_covers_every_metric(self) -> None:
        schema = scorecard().pointwise_schema()
        self.assertEqual(set(schema["properties"]), _EXPECTED_METRICS | {"rationale"})
        self.assertFalse(schema["additionalProperties"])

    def test_descriptions_and_scale_come_from_the_md(self) -> None:
        text = LIBRARY.load(SCORECARD, "v1").text
        for metric in scorecard().metrics:
            self.assertEqual(metric.scale, (1, 5))
            self.assertIn(metric.description, text)


if __name__ == "__main__":
    unittest.main()

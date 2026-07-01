from __future__ import annotations

from ..framework.scorecard import Metric, Scorecard

# Keys/scales drive the schema; descriptions mirror scorecards/linkedin/v1.md.
LINKEDIN_METRICS: tuple[Metric, ...] = (
    Metric("contextual_relevance", "Does the suggestion make sense given the past conversation alone?"),
    Metric("natural_next_move", "Is the suggestion a plausible thing the user might naturally say next?"),
    Metric("actual_message_overlap", "How much does the suggestion overlap with the actual next message?"),
    Metric("inferable_goal_coverage", "How well does it cover goals that were directly implied or weakly suggested by the conversation?"),
    Metric("private_intent_coverage", "How well does it cover goals that were not inferable from the conversation?"),
    Metric("groundedness", "Does it avoid inventing facts, commitments, motivations, dates, or assumptions not supported by the conversation?"),
    Metric("tone_match", "Does it match the sender's tone, vocabulary, formality, warmth, directness, and message length?"),
    Metric("clarity", "Is the suggestion easy to understand and unambiguous?"),
)

LINKEDIN_SCORECARD_V1 = Scorecard(version="v1", metrics=LINKEDIN_METRICS)

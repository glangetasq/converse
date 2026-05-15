from __future__ import annotations

from pathlib import Path

from ..utils import get_prompt_template

LINKEDIN_EVAL_PROMPT = get_prompt_template(
    Path(__file__).with_name("linkedin_eval_prompt.md"),
    ["sender_name", "recipient_name", "past_conversation"],
)
JUDGE_PROMPT = get_prompt_template(
    Path(__file__).with_name("judge_prompt.md"),
    [
        "sender_name",
        "recipient_name",
        "past_conversation",
        "actual_next_message",
        "suggested_next_message",
    ],
)

SCORE_SCHEMA = {"type": "integer", "enum": [1, 2, 3, 4, 5]}

SUGGESTION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "name": "linkedin_followup_suggestion",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "suggestion": {"type": "string"},
            "inferred_stage": {"type": "string"},
            "inferred_tone": {"type": "string"},
            "inferred_open_loops": {"type": "string"},
            "estimated_length": {"type": "integer"},
        },
        "required": [
            "suggestion",
            "inferred_stage",
            "inferred_tone",
            "inferred_open_loops",
            "estimated_length",
        ],
    },
}

JUDGE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "name": "linkedin_followup_judgement",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "actual_message_goals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "goal": {"type": "string"},
                        "inferability": {
                            "type": "string",
                            "enum": ["directly_implied", "weakly_suggested", "not_inferable"],
                        },
                        "covered_by_suggestion": {"type": "boolean"},
                    },
                    "required": ["goal", "inferability", "covered_by_suggestion"],
                },
            },
            "scores": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "contextual_relevance": SCORE_SCHEMA,
                    "natural_next_move": SCORE_SCHEMA,
                    "actual_message_overlap": SCORE_SCHEMA,
                    "inferable_goal_coverage": SCORE_SCHEMA,
                    "private_intent_coverage": SCORE_SCHEMA,
                    "groundedness": SCORE_SCHEMA,
                    "tone_match": SCORE_SCHEMA,
                    "clarity": SCORE_SCHEMA,
                },
                "required": [
                    "contextual_relevance",
                    "natural_next_move",
                    "actual_message_overlap",
                    "inferable_goal_coverage",
                    "private_intent_coverage",
                    "groundedness",
                    "tone_match",
                    "clarity",
                ],
            },
            "missed_inferable_goals": {"type": "array", "items": {"type": "string"}},
            "missed_private_goals": {"type": "array", "items": {"type": "string"}},
            "unsupported_assumptions": {"type": "array", "items": {"type": "string"}},
            "verdict": {
                "type": "string",
                "enum": [
                    "good",
                    "reasonable_but_low_overlap",
                    "reasonable_but_misses_private_intent",
                    "misses_inferable_goals",
                    "unsupported_or_hallucinated",
                    "poor",
                ],
            },
            "rationale": {"type": "string"},
        },
        "required": [
            "actual_message_goals",
            "scores",
            "missed_inferable_goals",
            "missed_private_goals",
            "unsupported_assumptions",
            "verdict",
            "rationale",
        ],
    },
}

SCORE_COLUMNS = list(JUDGE_RESPONSE_FORMAT["schema"]["properties"]["scores"]["properties"].keys())
ERROR_COLUMNS = ["error_stage", "error_type", "error_message"]
OUTPUT_TEXT_PATH_ERROR = "Completion did not contain output[0].content[0].text"
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

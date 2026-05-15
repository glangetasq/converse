import asyncio
import json
import random
import re
from datetime import datetime, timedelta

import pandas as pd

from .. import db
from .. import users
from ..config import settings
from ..llm import LlmCallLimiter, Model, ModelError, GPT54NanoModel
from ..routers import persons
from .linkedin_eval_config import (
    ERROR_COLUMNS,
    JUDGE_PROMPT,
    JUDGE_RESPONSE_FORMAT,
    LINKEDIN_EVAL_PROMPT,
    OUTPUT_TEXT_PATH_ERROR,
    RETRYABLE_STATUS_CODES,
    SCORE_COLUMNS,
    SUGGESTION_RESPONSE_FORMAT,
)


def retry_delay_seconds(error: ModelError, attempt: int) -> float:
    message = str(error)
    seconds_match = re.search(r"Please try again in ([0-9.]+)s", message)
    if seconds_match:
        suggested_delay = float(seconds_match.group(1))
    else:
        ms_match = re.search(r"Please try again in ([0-9.]+)ms", message)
        suggested_delay = float(ms_match.group(1)) / 1000 if ms_match else 0

    backoff_delay = min(60, 2**attempt)
    return max(suggested_delay, backoff_delay) + random.random()


def strip_json_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_completion_text(completion: dict) -> str:
    completion = completion or {}
    json_path = ["output", 0, "content", 0, "text"]
    for step in json_path:
        if isinstance(completion, list):
            if not isinstance(step, int) or step >= len(completion):
                raise ValueError(OUTPUT_TEXT_PATH_ERROR)
            completion = completion[step]
        elif isinstance(completion, dict):
            completion = completion.get(step, {})
        else:
            raise ValueError(OUTPUT_TEXT_PATH_ERROR)
    if not completion:
        raise ValueError(OUTPUT_TEXT_PATH_ERROR)
    return strip_json_code_fence(completion)


def returned_chat_json(completion: dict) -> dict:
    completion = extract_completion_text(completion)
    try:
        return json.loads(completion)
    except json.JSONDecodeError as error:
        start = max(0, error.pos - 300)
        end = min(len(completion), error.pos + 300)
        nearby = completion[start:end]
        raise ValueError(
            f"Invalid JSON at line {error.lineno}, column {error.colno}. "
            f"Nearby text: {nearby!r}"
        ) from error

# prompts + models -> suggestions -> judges -> scores
async def get_linkedin_examples() -> list[dict]:
    # empty past_context <=> introductions, so filtered out here
    sql = """
    SELECT *
    FROM eval_examples
    WHERE
        source = %s
        AND past_context IS NOT NULL
        AND past_context <> '{}'::jsonb
        AND past_context <> '[]'::jsonb
    """
    examples = await db.fetch_all(sql, ("linkedin",))
    return examples


def create_evaluation_row(example: dict, suggestion: dict, verdict_id, verdict: dict) -> dict:
    row = {
        "example_id": example["id"],
        "ground_truth": example["ground_truth_reply"],
        "ground_truth_quality": example["quality_rating"],
        "recipient_replied": example["recipient_replied"],
        "recipient_quality": example["recipient_quality_rating"],
        "suggestion": suggestion["suggestion"],
        "verdict_id": verdict_id,
        "verdict": verdict["verdict"],
        "rationale": verdict["rationale"],
        **verdict["scores"],
        "actual_message_goals": verdict["actual_message_goals"],
        "missed_inferable_goals": verdict["missed_inferable_goals"],
        "missed_private_goals": verdict["missed_private_goals"],
        "unsupported_assumptions": verdict["unsupported_assumptions"],
    }
    row.update({column: None for column in ERROR_COLUMNS})
    return row


def create_error_row(
    example: dict,
    verdict_id: int | None,
    stage: str,
    error: Exception,
    suggestion: dict | None = None,
) -> dict:
    suggestion = suggestion or {}
    row = {
        "example_id": example["id"],
        "ground_truth": example["ground_truth_reply"],
        "ground_truth_quality": example["quality_rating"],
        "recipient_replied": example["recipient_replied"],
        "recipient_quality": example["recipient_quality_rating"],
        "suggestion": suggestion.get("suggestion"),
        "verdict_id": verdict_id,
        "verdict": "error",
        "rationale": None,
        "actual_message_goals": None,
        "missed_inferable_goals": None,
        "missed_private_goals": None,
        "unsupported_assumptions": None,
        "error_stage": stage,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    row.update({score: None for score in SCORE_COLUMNS})
    return row


async def call_llm(
    model: Model,
    prompt: str,
    llm_limiter: LlmCallLimiter,
    response_format: dict | None = None,
    max_attempts: int = 6,
) -> dict:
    for attempt in range(max_attempts):
        try:
            return returned_chat_json(
                await model.query(
                    prompt,
                    response_format=response_format,
                    limiter=llm_limiter,
                )
            )
        except ModelError as error:
            is_retryable = error.status_code in RETRYABLE_STATUS_CODES
            if not is_retryable or attempt == max_attempts - 1:
                raise

            await asyncio.sleep(retry_delay_seconds(error, attempt))

    raise RuntimeError("LLM call exhausted retry attempts")


async def evaluate_example(
    example: dict,
    suggestor: Model,
    judge: Model,
    verdicts: int,
    example_sem: asyncio.Semaphore,
    llm_limiter: LlmCallLimiter,
) -> list[dict]:
    rows = []

    async with example_sem:
        suggestion_prompt = LINKEDIN_EVAL_PROMPT.substitute(
            sender_name=example["user_name"],
            recipient_name=example["recipient_name"],
            past_conversation=example["past_context"],
        )
        try:
            suggestion = await call_llm(
                suggestor,
                suggestion_prompt,
                llm_limiter,
                SUGGESTION_RESPONSE_FORMAT,
            )
        except Exception as error:
            return [create_error_row(example, None, "suggestion", error)]

        judge_prompt = JUDGE_PROMPT.substitute(
            sender_name=example["user_name"],
            recipient_name=example["recipient_name"],
            past_conversation=example["past_context"],
            actual_next_message=example["ground_truth_reply"],
            suggested_next_message=suggestion.get("suggestion", "no suggested next message"),
        )

        results = await asyncio.gather(
            *[
                call_llm(judge, judge_prompt, llm_limiter, JUDGE_RESPONSE_FORMAT)
                for _ in range(verdicts)
            ],
            return_exceptions=True,
        )

        for verdict_id, verdict in enumerate(results, start=1):
            if isinstance(verdict, Exception):
                rows.append(create_error_row(example, verdict_id, "judge", verdict, suggestion))
                continue

            try:
                rows.append(create_evaluation_row(example, suggestion, verdict_id, verdict))
            except Exception as error:
                rows.append(create_error_row(example, verdict_id, "row_build", error, suggestion))

    return rows


async def evaluate(
    suggestor: Model,
    judge: Model,
    verdicts: int = 1,
    concurrency: int = 10,
    max_llm_calls_per_minute: int = 50,
) -> pd.DataFrame:
    examples = await get_linkedin_examples()
    user_id_to_name = await users.get_user_id_to_name_dict()
    recipient_id_to_name = await persons.get_person_id_to_name_dict()

    example_sem = asyncio.Semaphore(3 * concurrency)
    llm_limiter = LlmCallLimiter(concurrency, max_llm_calls_per_minute)
    tasks = []

    for example in examples:
        user_id = str(example["user_id"])
        recipient_id = str(example["recipient_id"])
        named_example = {
            **example,
            "user_name": user_id_to_name.get(user_id, "unknown name"),
            "recipient_name": recipient_id_to_name.get(recipient_id, "unknown name"),
        }

        tasks.append(
            evaluate_example(named_example, suggestor, judge, verdicts, example_sem, llm_limiter)
        )

    nested_rows = await asyncio.gather(*tasks)

    df = pd.DataFrame([row for rows in nested_rows for row in rows])

    return df


def print_evaluation_summary(df: pd.DataFrame, elapsed_seconds: float) -> None:
    error_rows = df[df["verdict"] == "error"] if "verdict" in df else pd.DataFrame()
    print(f"Evaluation time: {elapsed_seconds:.0f}s")
    print(f"Total verdicts: {len(df)}")
    print(f"Error rows: {len(error_rows)}")
    if error_rows.empty:
        return

    print("Errors by stage/type:")
    print(
        error_rows.groupby(["error_stage", "error_type"])
        .size()
        .sort_values(ascending=False)
        .to_string()
    )
    print("Sample errors:")
    print(
        error_rows[
            ["example_id", "verdict_id", "error_stage", "error_type", "error_message"]
        ]
        .head(5)
        .to_string(index=False)
    )


async def main() -> None:
    t0 = datetime.now()
    async with db.open_database(settings.database_url):
        df = await evaluate(GPT54NanoModel, GPT54NanoModel, 2)
        # print(examples[0] if examples else "No linkedin eval examples found.")
    t1 = datetime.now()
    print_evaluation_summary(df, (t1 - t0) / timedelta(seconds=1))


if __name__ == "__main__":
    asyncio.run(main())

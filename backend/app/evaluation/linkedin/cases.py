from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from ... import db
from ...web.models import LoginRequest
from ...routers.persons import get_person_id_to_name_dict
from ...identity.users import DEV_USER_DISPLAY_NAME, get_user_id_to_name_dict
from ..framework.core import Case

# empty past_context <=> a cold intro, dropped so every case has real thread context
_EXAMPLES_SQL = """
SELECT id, user_id, recipient_id, past_context, ground_truth_reply, quality_rating
FROM eval_examples
WHERE source = %s
  AND past_context IS NOT NULL
  AND past_context <> '{}'::jsonb
  AND past_context <> '[]'::jsonb
ORDER BY id
"""

# Human name to use when the account is the decoupled "Local Dev User" placeholder.
DEV_SENDER_NAME = LoginRequest.model_fields["username"].default


def _sender_name(account_name: str | None) -> str:
    if not account_name or account_name == DEV_USER_DISPLAY_NAME:
        return DEV_SENDER_NAME
    return account_name


async def thread_depths(case_ids: Iterable[str] | None = None) -> dict[str, int]:
    """Message count of each case's thread, keyed by `case_id` (the eval_examples id as
    text). Depth is a per-case property, so one value regardless of pointwise/pairwise."""
    where = ""
    params: tuple = ()
    if case_ids is not None:
        ids = [int(c) for c in case_ids]
        if not ids:
            return {}
        where = "WHERE id = ANY(%s)"
        params = (ids,)
    rows = await db.fetch_all(
        f"SELECT id::text AS case_id, jsonb_array_length(past_context) AS depth FROM eval_examples {where}",
        params,
    )
    return {row["case_id"]: row["depth"] for row in rows}


async def attach_thread_depth(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `thread_depth` column to a load_run frame by joining on `case_id`."""
    depths = await thread_depths(df["case_id"].unique())
    return df.assign(thread_depth=df["case_id"].map(depths))


async def load_cases() -> list[Case]:
    rows = await db.fetch_all(_EXAMPLES_SQL, ("linkedin",))
    user_names = await get_user_id_to_name_dict()
    person_names = await get_person_id_to_name_dict()

    cases = []
    for row in rows:
        thread = row["past_context"]
        user_id = str(row["user_id"])
        person_id = str(row["recipient_id"]) if row["recipient_id"] else None
        cases.append(
            Case(
                id=str(row["id"]),
                thread=thread,
                sender_name=_sender_name(user_names.get(user_id)),
                recipient_name=person_names.get(person_id or "", "unknown name"),
                ground_truth=row["ground_truth_reply"],
                meta={
                    "user_id": user_id,
                    "person_id": person_id,  # RagAugmentor reads these two from meta
                    "thread_depth": len(thread),
                    "quality": row["quality_rating"],
                },
            )
        )
    return cases

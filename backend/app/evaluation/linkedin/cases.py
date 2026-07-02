from __future__ import annotations

from ... import db
from ...models import LoginRequest
from ...routers.persons import get_person_id_to_name_dict
from ...users import DEV_USER_DISPLAY_NAME, get_user_id_to_name_dict
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

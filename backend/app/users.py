from __future__ import annotations

import re
import unicodedata
from typing import Any

from . import db


def normalize_username(value: str) -> str:
    return " ".join(value.split()).strip()


def username_to_email(username: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", username).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", ".", ascii_name.lower()).strip(".") or "user"
    return f"{slug}@converse.local"


async def get_or_create_user_by_name(user_name: str) -> dict[str, Any]:
    normalized_name = normalize_username(user_name)
    if not normalized_name:
        raise ValueError("User name is required.")

    row = await db.fetch_one(
        """
        INSERT INTO users (email, display_name)
        VALUES (%s, %s)
        ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name
        RETURNING id, email, display_name, created_at
        """,
        (username_to_email(normalized_name), normalized_name),
    )

    if row is None:
        raise RuntimeError("Unable to resolve user.")

    return row


async def get_or_create_user_id_by_name(user_name: str) -> str:
    user = await get_or_create_user_by_name(user_name)
    return str(user["id"])


async def get_user_id_to_name_dict() -> dict[str, str]:
    rows = await db.fetch_all(
        """
        SELECT id, display_name AS name
        FROM users
        ORDER BY display_name, id
        """
    )

    return {str(row["id"]): row["name"] or "" for row in rows}

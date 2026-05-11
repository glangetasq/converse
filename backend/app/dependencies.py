from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from . import db
from .config import settings
from .serialization import to_api


async def get_current_user() -> dict[str, Any]:
    row = await db.fetch_one(
        """
        INSERT INTO users (email, display_name)
        VALUES (%s, %s)
        ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name
        RETURNING id, email, display_name, created_at
        """,
        (settings.local_dev_user_email, "Local Dev User"),
    )

    if row is None:
        raise RuntimeError("Unable to resolve local development user.")

    return to_api(row)


def jsonb(value: Any) -> Jsonb:
    return Jsonb(value if value is not None else {})


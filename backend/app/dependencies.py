from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from .serialization import to_api
from .users import get_or_create_dev_user


async def get_current_user() -> dict[str, Any]:
    return to_api(await get_or_create_dev_user())


def jsonb(value: Any) -> Jsonb:
    return Jsonb(value if value is not None else {})


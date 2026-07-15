from __future__ import annotations

import secrets
from typing import Any

from fastapi import Header, HTTPException, status
from psycopg.types.json import Jsonb

from .serialization import to_api
from ..config import settings
from ..identity.users import get_or_create_dev_user


async def require_api_key(authorization: str | None = Header(default=None)) -> None:
    # Route dependency, not middleware: CORS answers the headerless OPTIONS preflight before this runs.
    expected = settings.api_key
    if expected is None:  # unset -> gate off for local dev
        return
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


async def get_current_user() -> dict[str, Any]:
    return to_api(await get_or_create_dev_user())


def jsonb(value: Any) -> Jsonb:
    return Jsonb(value if value is not None else {})

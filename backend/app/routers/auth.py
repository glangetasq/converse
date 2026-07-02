from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..models import LoginRequest
from ..serialization import to_api
from ..users import get_or_create_user_by_name, normalize_username

router = APIRouter()


@router.post("/login")
async def login(payload: LoginRequest) -> dict[str, Any]:
    username = normalize_username(payload.username)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username is required.",
        )

    try:
        row = await get_or_create_user_by_name(username)
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Unable to authenticate user.")
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    user = to_api(row)
    user_id = str(row["id"])
    return {
        "current_user": username,
        "current_user_id": user_id,
        "currentUser": username,
        "currentUserId": user_id,
        "user": user,
    }

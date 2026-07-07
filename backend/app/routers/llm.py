from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..config import settings
from ..llm import KNOWN_MODELS, provider_for

router = APIRouter()


@router.get("/models")
async def list_models() -> dict[str, Any]:
    """Model menu for the extension; the default is always included."""
    model_ids = list(KNOWN_MODELS)
    if settings.default_model not in model_ids:
        model_ids.insert(0, settings.default_model)

    return {
        "models": [{"id": model_id, "provider": provider_for(model_id)} for model_id in model_ids],
        "default": settings.default_model,
    }

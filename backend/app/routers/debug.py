from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, status

from ..captures import captures_dir, slugify, unique_path
from ..loggers import debug_logger
from ..models import ParseDumpRequest

router = APIRouter()


@router.post("/parse_dump", status_code=status.HTTP_201_CREATED)
async def dump_parse_result(payload: ParseDumpRequest) -> dict[str, Any]:
    """Save a parsed LinkedIn profile's JSON to a file on disk for Claude to read."""
    directory = captures_dir()
    directory.mkdir(parents=True, exist_ok=True)

    target = unique_path(directory, f"{slugify(payload.label)}.json")
    serialized = json.dumps(payload.result, indent=2, ensure_ascii=False, default=str) + "\n"
    target.write_text(serialized, encoding="utf-8")

    debug_logger.info(f"Saved parse dump -> {target}")

    return {"status": "saved", "filename": target.name, "path": str(target)}

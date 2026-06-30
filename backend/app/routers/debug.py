from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db, ingestion
from ..dependencies import get_current_user
from ..loggers import debug_logger
from ..models import ParseDumpRequest

router = APIRouter()


@router.post("/parse_dump", status_code=status.HTTP_201_CREATED)
async def dump_parse_result(
    payload: ParseDumpRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Ingest a parsed profile into persons + source_documents."""
    if not ingestion.supports(payload.parser_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No ingester registered for parser_id {payload.parser_id!r}.",
        )

    async for conn in db.connection():
        async with conn.transaction():
            ingested = await ingestion.ingest(
                conn,
                user["id"],
                parser_id=payload.parser_id,
                result=payload.result,
                source_url=payload.source_url,
            )

    debug_logger.info(
        f"Ingested {payload.parser_id}: {ingested.status} "
        f"(document={ingested.source_document_id}, person={ingested.person_id})"
    )

    return {
        "status": ingested.status,
        "sourceDocumentId": ingested.source_document_id,
        "personId": ingested.person_id,
    }

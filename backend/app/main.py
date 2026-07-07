from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import settings
from .loggers import api_logger, get_current_log_file_path
from .routers import auth, conversations, debug, eval_examples, followups, health, llm, memory, persons


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    api_logger.info("Starting Converse API; logging to %s", get_current_log_file_path())
    await db.open_pool(settings.database_url)
    if settings.auto_create_tables:
        await db.init_schema()

    try:
        yield
    finally:
        api_logger.info("Stopping Converse API")
        await db.close_pool()


app = FastAPI(title="Converse API", version="1.0.0", lifespan=lifespan)

chrome_extension_wildcard = "chrome-extension://*"
allow_origin_regex = r"chrome-extension://.*" if chrome_extension_wildcard in settings.allowed_origins else None
allow_origins = [origin for origin in settings.allowed_origins if origin != chrome_extension_wildcard]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(persons.router, prefix="/api/persons", tags=["persons"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(followups.router, prefix="/api/followups", tags=["followups"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(eval_examples.router, prefix="/api/eval_examples", tags=["eval_examples"])
app.include_router(debug.router, prefix="/api/debug", tags=["debug"])


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)

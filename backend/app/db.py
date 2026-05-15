from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .loggers import db_logger


pool: AsyncConnectionPool | None = None


async def open_pool(database_url: str) -> None:
    global pool
    db_logger.info("Opening database pool")
    pool = AsyncConnectionPool(database_url, open=False, kwargs={"row_factory": dict_row})
    await pool.open(wait=True)


async def close_pool() -> None:
    global pool
    if pool is not None:
        db_logger.info("Closing database pool")
        await pool.close()
        pool = None


@asynccontextmanager
async def open_database(database_url: str) -> AsyncIterator[None]:
    await open_pool(database_url)
    try:
        yield
    finally:
        await close_pool()


async def connection() -> AsyncIterator[AsyncConnection]:
    if pool is None:
        raise RuntimeError("Database pool has not been opened.")

    async with pool.connection() as conn:
        yield conn


async def fetch_one(query: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    if pool is None:
        raise RuntimeError("Database pool has not been opened.")

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchone()

    return None


async def fetch_all(query: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    if pool is None:
        raise RuntimeError("Database pool has not been opened.")

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
            return list(rows)

    return []


async def init_schema() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    db_logger.info("Initializing database schema from %s", schema_path)

    async for conn in connection():
        async with conn.cursor() as cur:
            await cur.execute(sql)
        await conn.commit()

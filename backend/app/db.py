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
    # min_size=0 keeps a cold start from blocking on a suspended Neon; prepare_threshold=None is
    # required for Neon's pooled (PgBouncer) endpoint, which breaks server-side prepared statements.
    pool = AsyncConnectionPool(
        database_url,
        open=False,
        min_size=0,
        max_size=5,
        max_idle=120,
        check=AsyncConnectionPool.check_connection,
        kwargs={"row_factory": dict_row, "prepare_threshold": None, "connect_timeout": 10},
    )
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
    sql_dir = Path(__file__).resolve().parents[1] / "sql"
    files = sorted(sql_dir.glob("*.sql"))  # numeric prefixes order FK dependencies
    db_logger.info("Initializing database schema from %s (%d files)", sql_dir, len(files))

    async for conn in connection():
        async with conn.cursor() as cur:
            for path in files:
                db_logger.info("Applying %s", path.name)
                await cur.execute(path.read_text(encoding="utf-8"))
        await conn.commit()

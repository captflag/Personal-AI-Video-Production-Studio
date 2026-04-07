"""
db.py
-----
Asyncpg connection pool singleton for the AI Studio backend.

Why asyncpg instead of the `supabase-py` client for DB writes?
- supabase-py uses httpx under the hood (REST), adding network round-trip overhead.
- asyncpg speaks native Postgres wire protocol — ~5-10x faster for bulk inserts.
- A shared pool prevents "too many clients" errors under concurrent ARQ tasks.

Usage:
    from backend.db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SELECT 1")
"""
import os
import asyncpg
import structlog

logger = structlog.get_logger()

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """
    Returns the process-level asyncpg connection pool, creating it on first call.
    Supabase exposes a standard Postgres endpoint — we connect directly using the
    DATABASE_URL environment variable (postgres://...).
    """
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.warning(
                "db_pool_skipped",
                reason="DATABASE_URL not set — returning None. Supabase REST will be used as fallback.",
            )
            return None  # type: ignore[return-value]

        try:
            _pool = await asyncpg.create_pool(
                dsn=database_url,
                min_size=2,
                max_size=5,  # Matches max_jobs + 1 management slot
                command_timeout=30,
            )
            logger.info("db_pool_created", min_size=2, max_size=5)
        except Exception as e:
            logger.error("db_pool_creation_failed", error=str(e))
            return None  # type: ignore[return-value]

    return _pool


async def close_pool() -> None:
    """Call during FastAPI shutdown to cleanly drain the pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("db_pool_closed")
    else:
        logger.debug("db_pool_already_null_or_never_created")

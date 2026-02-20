"""
Postgres persistence layer for validation records.

Uses psycopg3 AsyncConnectionPool (already in requirements as psycopg-pool).
The pool is opened on FastAPI startup and closed on shutdown.

The `validations` table stores all validation records so history survives
uvicorn restarts. MemorySaver (LangGraph HITL checkpointer) stays in-memory;
only the application-level metadata is persisted here.

Connection string: strip the SQLAlchemy prefix — psycopg3 uses postgresql://
"""

import json
from typing import Any, Dict, List, Optional

import psycopg
from psycopg_pool import AsyncConnectionPool

from config.settings import settings

# Convert SQLAlchemy-style URI to plain psycopg3 URI
_DSN = settings.PGVECTOR_CONNECTION_STRING.replace(
    "postgresql+psycopg://", "postgresql://"
)

pool: Optional[AsyncConnectionPool] = None


async def init_pool() -> None:
    global pool
    pool = AsyncConnectionPool(conninfo=_DSN, min_size=1, max_size=5, open=False)
    await pool.open()
    await _create_table()


async def close_pool() -> None:
    if pool:
        await pool.close()


async def _create_table() -> None:
    async with pool.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS validations (
                id          TEXT PRIMARY KEY,
                url         TEXT NOT NULL,
                requested_by TEXT,
                created_at  TIMESTAMPTZ NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                overall_score REAL,
                overall_passed BOOLEAN,
                findings    JSONB DEFAULT '[]',
                errors      JSONB DEFAULT '[]',
                human_decision TEXT,
                human_feedback TEXT,
                reviewed_by TEXT,
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


async def upsert_validation(state: Dict[str, Any]) -> None:
    """Insert or update a validation record from a ValidationState dict."""
    findings = state.get("findings", [])
    findings_json = json.dumps([
        f.model_dump() if hasattr(f, "model_dump") else f
        for f in findings
    ])
    errors_json = json.dumps(state.get("errors", []))

    async with pool.connection() as conn:
        await conn.execute("""
            INSERT INTO validations
                (id, url, requested_by, created_at, status,
                 overall_score, overall_passed, findings, errors,
                 human_decision, human_feedback, reviewed_by, updated_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                status         = EXCLUDED.status,
                overall_score  = EXCLUDED.overall_score,
                overall_passed = EXCLUDED.overall_passed,
                findings       = EXCLUDED.findings,
                errors         = EXCLUDED.errors,
                human_decision = EXCLUDED.human_decision,
                human_feedback = EXCLUDED.human_feedback,
                reviewed_by    = EXCLUDED.reviewed_by,
                updated_at     = NOW()
        """, (
            state.get("validation_id"),
            state.get("url"),
            state.get("requested_by"),
            state.get("created_at"),
            state.get("status", "pending"),
            state.get("overall_score"),
            state.get("overall_passed"),
            findings_json,
            errors_json,
            state.get("human_decision"),
            state.get("human_feedback"),
            state.get("reviewed_by"),
        ))


async def get_validation(vid: str) -> Optional[Dict[str, Any]]:
    """Fetch a single validation record by ID."""
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                "SELECT * FROM validations WHERE id = %s", (vid,)
            )
            row = await cur.fetchone()
    if not row:
        return None
    return _row_to_dict(row)


async def list_validations(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent validations ordered by created_at desc."""
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                "SELECT * FROM validations ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(row)
    # Postgres returns created_at/updated_at as datetime objects
    for key in ("created_at", "updated_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat()
    # Rename DB column 'id' → 'validation_id' to match frontend expectations
    d["validation_id"] = d.pop("id", d.get("validation_id"))
    return d

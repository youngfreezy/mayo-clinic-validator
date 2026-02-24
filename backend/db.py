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
                routing_decision JSONB DEFAULT NULL,
                skipped_agents JSONB DEFAULT '[]',
                trace_url TEXT DEFAULT NULL,
                judge_recommendation JSONB DEFAULT NULL,
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        # Idempotent migrations — add columns that may be missing from older schemas
        for col, defn in [
            ("routing_decision", "JSONB DEFAULT NULL"),
            ("skipped_agents", "JSONB DEFAULT '[]'"),
            ("trace_url", "TEXT DEFAULT NULL"),
            ("judge_recommendation", "JSONB DEFAULT NULL"),
        ]:
            await conn.execute(
                f"ALTER TABLE validations ADD COLUMN IF NOT EXISTS {col} {defn}"
            )


async def upsert_validation(state: Dict[str, Any]) -> None:
    """Insert or update a validation record from a ValidationState dict."""
    findings = state.get("findings", [])
    findings_json = json.dumps([
        f.model_dump() if hasattr(f, "model_dump") else f
        for f in findings
    ])
    errors_json = json.dumps(state.get("errors", []))
    routing_json = json.dumps(state.get("routing_decision")) if state.get("routing_decision") else None
    skipped_json = json.dumps(state.get("skipped_agents", []))
    judge_json = json.dumps(state.get("judge_recommendation")) if state.get("judge_recommendation") else None

    async with pool.connection() as conn:
        await conn.execute("""
            INSERT INTO validations
                (id, url, requested_by, created_at, status,
                 overall_score, overall_passed, findings, errors,
                 human_decision, human_feedback, reviewed_by,
                 routing_decision, skipped_agents, trace_url,
                 judge_recommendation, updated_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s,
                 %s::jsonb, %s::jsonb, %s, %s::jsonb, NOW())
            ON CONFLICT (id) DO UPDATE SET
                status           = EXCLUDED.status,
                overall_score    = EXCLUDED.overall_score,
                overall_passed   = EXCLUDED.overall_passed,
                findings         = EXCLUDED.findings,
                errors           = EXCLUDED.errors,
                human_decision   = EXCLUDED.human_decision,
                human_feedback   = EXCLUDED.human_feedback,
                reviewed_by      = EXCLUDED.reviewed_by,
                routing_decision = EXCLUDED.routing_decision,
                skipped_agents   = EXCLUDED.skipped_agents,
                trace_url        = EXCLUDED.trace_url,
                judge_recommendation = EXCLUDED.judge_recommendation,
                updated_at       = NOW()
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
            routing_json,
            skipped_json,
            state.get("trace_url"),
            judge_json,
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

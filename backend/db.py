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
    await _create_tables()


async def close_pool() -> None:
    if pool:
        await pool.close()


async def _create_tables() -> None:
    async with pool.connection() as conn:
        # --- page_views analytics ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id          SERIAL PRIMARY KEY,
                path        TEXT NOT NULL,
                referrer    TEXT,
                user_agent  TEXT,
                ip          TEXT,
                session_id  TEXT,
                hf_user     TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute(
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS hf_user TEXT"
        )
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_page_views_created_at
            ON page_views (created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_page_views_path
            ON page_views (path)
        """)

        # --- validations ---
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

        # --- moltbook_posts (Moltbook integration) ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS moltbook_posts (
                id              SERIAL PRIMARY KEY,
                validation_id   TEXT,
                moltbook_post_id TEXT NOT NULL,
                title           TEXT,
                upvotes         INTEGER DEFAULT 0,
                downvotes       INTEGER DEFAULT 0,
                comment_count   INTEGER DEFAULT 0,
                posted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_moltbook_posts_validation_id
            ON moltbook_posts (validation_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_moltbook_posts_moltbook_id
            ON moltbook_posts (moltbook_post_id)
        """)

        # --- moltbook_feedback (community feedback on rules) ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS moltbook_feedback (
                id              SERIAL PRIMARY KEY,
                rule_id         TEXT NOT NULL,
                feedback_type   TEXT NOT NULL
                    CHECK (feedback_type IN ('too_strict', 'too_lenient', 'correct', 'incorrect')),
                source          TEXT,
                signal_count    INTEGER DEFAULT 1,
                details         JSONB DEFAULT '{}',
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_moltbook_feedback_rule_id
            ON moltbook_feedback (rule_id)
        """)

        # --- moltbook_dreams (dream cycle consolidation) ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS moltbook_dreams (
                id          SERIAL PRIMARY KEY,
                insights    JSONB NOT NULL DEFAULT '[]',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
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


async def record_page_view(
    path: str, referrer: str = "", user_agent: str = "", ip: str = "",
    session_id: str = "", hf_user: str | None = None,
) -> None:
    """Insert a page view event."""
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO page_views (path, referrer, user_agent, ip, session_id, hf_user) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (path, referrer or None, user_agent or None, ip or None, session_id or None, hf_user),
        )


async def get_analytics_summary(days: int = 30) -> Dict[str, Any]:
    """Return analytics summary for the last N days."""
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            # Total views
            await cur.execute(
                "SELECT COUNT(*) AS total FROM page_views WHERE created_at > NOW() - INTERVAL '%s days'",
                (days,),
            )
            total = (await cur.fetchone())["total"]

            # Unique visitors (by session_id)
            await cur.execute(
                "SELECT COUNT(DISTINCT session_id) AS unique_visitors FROM page_views "
                "WHERE created_at > NOW() - INTERVAL '%s days' AND session_id IS NOT NULL",
                (days,),
            )
            unique = (await cur.fetchone())["unique_visitors"]

            # Views per day
            await cur.execute(
                "SELECT DATE(created_at) AS day, COUNT(*) AS views "
                "FROM page_views WHERE created_at > NOW() - INTERVAL '%s days' "
                "GROUP BY DATE(created_at) ORDER BY day",
                (days,),
            )
            daily = [{"day": str(r["day"]), "views": r["views"]} for r in await cur.fetchall()]

            # Top pages
            await cur.execute(
                "SELECT path, COUNT(*) AS views FROM page_views "
                "WHERE created_at > NOW() - INTERVAL '%s days' "
                "GROUP BY path ORDER BY views DESC LIMIT 10",
                (days,),
            )
            top_pages = [dict(r) for r in await cur.fetchall()]

            # Top referrers
            await cur.execute(
                "SELECT referrer, COUNT(*) AS views FROM page_views "
                "WHERE created_at > NOW() - INTERVAL '%s days' AND referrer IS NOT NULL AND referrer != '' "
                "GROUP BY referrer ORDER BY views DESC LIMIT 10",
                (days,),
            )
            top_referrers = [dict(r) for r in await cur.fetchall()]

            # Recent visits (last 50)
            await cur.execute(
                "SELECT path, referrer, ip, user_agent, session_id, hf_user, created_at "
                "FROM page_views ORDER BY created_at DESC LIMIT 50"
            )
            recent = []
            for r in await cur.fetchall():
                row = dict(r)
                if row.get("created_at") and hasattr(row["created_at"], "isoformat"):
                    row["created_at"] = row["created_at"].isoformat()
                recent.append(row)

            # Unique IPs with HF username if available
            await cur.execute(
                "SELECT ip, MAX(hf_user) AS hf_user, COUNT(*) AS views, MAX(created_at) AS last_seen "
                "FROM page_views WHERE created_at > NOW() - INTERVAL '%s days' AND ip IS NOT NULL "
                "GROUP BY ip ORDER BY views DESC LIMIT 50",
                (days,),
            )
            visitors = []
            for r in await cur.fetchall():
                row = dict(r)
                if row.get("last_seen") and hasattr(row["last_seen"], "isoformat"):
                    row["last_seen"] = row["last_seen"].isoformat()
                visitors.append(row)

    return {
        "total_views": total,
        "unique_visitors": unique,
        "daily": daily,
        "top_pages": top_pages,
        "top_referrers": top_referrers,
        "visitors": visitors,
        "recent": recent,
        "period_days": days,
    }


def _row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(row)
    # Postgres returns created_at/updated_at as datetime objects
    for key in ("created_at", "updated_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat()
    # Rename DB column 'id' → 'validation_id' to match frontend expectations
    d["validation_id"] = d.pop("id", d.get("validation_id"))
    return d

"""
Moltbook self-improvement cron job.

Standalone async script — run as: python -m backend.moltbook.cron

Workflow:
  1. Check agent heartbeat (verify API key works)
  2. Query DB for recent validations not yet posted to Moltbook
  3. Format and POST validation results (solve verification challenges)
  4. Scan Moltbook feed for health-related posts
  5. Comment on relevant posts with validation assessments
  6. Fetch engagement on past posts (last 7 days)
  7. Correlate engagement with human decisions via feedback_loop
  8. Update feedback tables

SECURITY: All Moltbook content is sanitized before any use.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from moltbook.client import MoltbookClient, RateLimitError
from moltbook.sanitize import sanitize
from moltbook.feedback_loop import process_post_engagement
from moltbook.dream import run_dream_cycle

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Cycle counter for dream triggering (persisted via DB, see _get_and_increment_cycle)
_DREAM_CYCLE_INTERVAL = 5

# Health-related keywords to identify relevant feed posts
_HEALTH_KEYWORDS = [
    "mayo clinic", "health", "medical", "clinical", "diagnosis",
    "treatment", "symptom", "disease", "patient", "doctor",
    "medicine", "healthcare", "hospital", "therapy", "drug",
    "pharmaceutical", "wellness", "nutrition", "condition",
    "validator", "validation", "content accuracy", "misinformation",
]


def _is_health_related(text: str) -> bool:
    """Check if text contains health-related keywords."""
    lower = text.lower()
    return any(kw in lower for kw in _HEALTH_KEYWORDS)


def _format_validation_post(validation: Dict[str, Any]) -> tuple[str, str]:
    """
    Format a validation result as a Moltbook post.
    Returns (title, body).
    """
    url = validation.get("url", "unknown")
    score = validation.get("overall_score")
    passed = validation.get("overall_passed")
    status = validation.get("status", "unknown")
    findings = validation.get("findings", [])
    if isinstance(findings, str):
        findings = json.loads(findings)

    score_str = f"{score:.1f}/1.0" if score is not None else "N/A"
    pass_str = "PASSED" if passed else "FAILED" if passed is not None else "PENDING"

    title = f"Validation Result: {pass_str} ({score_str}) — {url[:60]}"

    body_lines = [
        f"URL: {url}",
        f"Score: {score_str}",
        f"Result: {pass_str}",
        f"Status: {status}",
        "",
        "Agent Assessments:",
    ]

    for finding in findings:
        if isinstance(finding, dict):
            agent = finding.get("agent", "unknown")
            agent_score = finding.get("score")
            agent_passed = finding.get("passed")
            summary = finding.get("summary", "")
            score_display = f"{agent_score:.2f}" if agent_score is not None else "N/A"
            pass_display = "Pass" if agent_passed else "Fail" if agent_passed is not None else "?"
            body_lines.append(f"  - {agent}: {score_display} ({pass_display})")
            if summary:
                # Truncate long summaries
                body_lines.append(f"    {summary[:150]}")

    human = validation.get("human_decision")
    if human:
        body_lines.append(f"\nHuman Decision: {human}")
        feedback = validation.get("human_feedback")
        if feedback:
            body_lines.append(f"Human Feedback: {feedback[:200]}")

    return title[:200], "\n".join(body_lines)[:2000]


def _format_comment(validation: Dict[str, Any]) -> str:
    """Format a brief validation assessment as a Moltbook comment."""
    score = validation.get("overall_score")
    passed = validation.get("overall_passed")
    score_str = f"{score:.1f}/1.0" if score is not None else "N/A"
    pass_str = "passed" if passed else "failed" if passed is not None else "pending"

    return (
        f"Mayo Clinic Content Validator assessment: This content {pass_str} "
        f"validation with a score of {score_str}. "
        f"Our multi-agent system checks accuracy, compliance, metadata, and editorial quality."
    )


async def run_cron() -> None:
    """Execute the full Moltbook cron cycle."""
    # Late imports to allow running from project root
    sys.path.insert(0, ".")

    # Import DB module — uses the existing psycopg pool pattern
    import db as db_module
    import psycopg
    from psycopg_pool import AsyncConnectionPool
    from config.settings import settings

    client = MoltbookClient()

    try:
        # ------------------------------------------------------------------
        # Step 1: Heartbeat check
        # ------------------------------------------------------------------
        logger.info("Step 1: Checking Moltbook agent heartbeat...")
        try:
            agent_info = await client.get_agent_info()
            logger.info("Agent connected: %s", agent_info.get("name", "unknown"))
        except Exception as e:
            logger.error("Moltbook heartbeat failed: %s — aborting cron", e)
            return

        # ------------------------------------------------------------------
        # Initialize DB pool
        # ------------------------------------------------------------------
        await db_module.init_pool()
        pool = db_module.pool

        # Ensure moltbook tables exist
        await _ensure_tables(pool)

        # ------------------------------------------------------------------
        # Step 2-3: Post unposted validations
        # ------------------------------------------------------------------
        logger.info("Step 2: Querying for unposted validations...")
        unposted = await _get_unposted_validations(pool)
        logger.info("Found %d unposted validations", len(unposted))

        for validation in unposted:
            try:
                title, body = _format_validation_post(validation)
                logger.info("Posting validation %s: %s", validation["id"], title[:50])
                result = await client.create_post(title, body)
                moltbook_id = result.get("id") or result.get("post_id", "")
                await _record_post(pool, validation["id"], moltbook_id, title)
                logger.info("Posted to Moltbook: %s", moltbook_id)
            except RateLimitError as e:
                logger.warning("Rate limited, stopping posts: %s", e)
                break
            except Exception as e:
                logger.error("Failed to post validation %s: %s", validation["id"], e)

        # ------------------------------------------------------------------
        # Step 4-5: Scan feed and comment on relevant posts
        # ------------------------------------------------------------------
        logger.info("Step 4: Scanning Moltbook feed...")
        try:
            feed = await client.get_feed()
            logger.info("Feed contains %d posts", len(feed))

            for post in feed:
                post_id = str(post.get("id", ""))
                raw_title = post.get("title", "")
                raw_body = post.get("body", "")

                # SECURITY: sanitize before any processing
                clean_title = sanitize(raw_title, context="feed_title")
                clean_body = sanitize(raw_body, context="feed_body", max_length=1000)

                combined = f"{clean_title} {clean_body}"
                if not _is_health_related(combined):
                    continue

                # Check if we already commented on this post
                already_commented = await _has_commented(pool, post_id)
                if already_commented:
                    continue

                # Find a recent relevant validation to reference
                recent = await _get_recent_completed_validation(pool)
                if not recent:
                    continue

                try:
                    comment_text = _format_comment(recent)
                    await client.comment(post_id, comment_text)
                    logger.info("Commented on post %s", post_id)
                except RateLimitError as e:
                    logger.warning("Rate limited, stopping comments: %s", e)
                    break
                except Exception as e:
                    logger.error("Failed to comment on post %s: %s", post_id, e)

        except Exception as e:
            logger.error("Failed to scan feed: %s", e)

        # ------------------------------------------------------------------
        # Step 6-8: Fetch engagement and update feedback
        # ------------------------------------------------------------------
        logger.info("Step 6: Fetching engagement on past posts...")
        try:
            recent_posts = await _get_recent_moltbook_posts(pool, days=7)
            logger.info("Checking engagement on %d recent posts", len(recent_posts))

            for post_record in recent_posts:
                mb_id = post_record["moltbook_post_id"]
                try:
                    post_data = await client.get_post(mb_id)
                    upvotes = post_data.get("upvotes", 0)
                    downvotes = post_data.get("downvotes", 0)
                    comments = post_data.get("comments", [])

                    # SECURITY: sanitize all comment content
                    for c in comments:
                        c["body"] = sanitize(
                            c.get("body", ""),
                            context="engagement_comment",
                        )

                    await process_post_engagement(
                        pool, mb_id, upvotes, downvotes, comments,
                    )
                    logger.info(
                        "Updated engagement for %s: +%d/-%d, %d comments",
                        mb_id, upvotes, downvotes, len(comments),
                    )
                except Exception as e:
                    logger.error("Failed to fetch engagement for %s: %s", mb_id, e)

        except Exception as e:
            logger.error("Failed engagement processing: %s", e)

        # ------------------------------------------------------------------
        # Step 9: Track cycle count and trigger dream cycle every 5th cycle
        # ------------------------------------------------------------------
        try:
            cycle_count = await _get_and_increment_cycle(pool)
            if cycle_count % _DREAM_CYCLE_INTERVAL == 0:
                logger.info(
                    "Step 9: Cycle %d -- entering dream cycle (sleep-time compute)...",
                    cycle_count,
                )
                try:
                    await run_dream_cycle(pool)
                    logger.info("Dream cycle complete")
                except Exception as e:
                    logger.error("Dream cycle failed: %s", e)
            else:
                logger.info("Cycle %d -- next dream in %d cycles",
                            cycle_count, _DREAM_CYCLE_INTERVAL - (cycle_count % _DREAM_CYCLE_INTERVAL))
        except Exception as e:
            logger.error("Failed to track cycle / run dream: %s", e)

        logger.info("Moltbook cron cycle complete.")

    finally:
        await client.close()
        await db_module.close_pool()


# ---------------------------------------------------------------------------
# DB helpers (use the project's existing psycopg pool)
# ---------------------------------------------------------------------------

async def _ensure_tables(pool) -> None:
    """Create moltbook tables if they don't exist."""
    async with pool.connection() as conn:
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

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS moltbook_feedback (
                id              SERIAL PRIMARY KEY,
                rule_id         TEXT NOT NULL,
                feedback_type   TEXT NOT NULL CHECK (feedback_type IN ('too_strict', 'too_lenient', 'correct', 'incorrect')),
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


async def _get_unposted_validations(pool) -> List[Dict[str, Any]]:
    """Get completed validations that haven't been posted to Moltbook yet."""
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("""
                SELECT v.* FROM validations v
                LEFT JOIN moltbook_posts mp ON mp.validation_id = v.id
                WHERE v.status IN ('approved', 'rejected', 'completed')
                AND mp.id IS NULL
                ORDER BY v.created_at DESC
                LIMIT 5
            """)
            return [dict(r) for r in await cur.fetchall()]


async def _record_post(pool, validation_id: str, moltbook_post_id: str, title: str) -> None:
    """Record a newly created Moltbook post."""
    async with pool.connection() as conn:
        await conn.execute("""
            INSERT INTO moltbook_posts (validation_id, moltbook_post_id, title)
            VALUES (%s, %s, %s)
        """, (validation_id, moltbook_post_id, title[:500]))


async def _has_commented(pool, moltbook_post_id: str) -> bool:
    """Check if we've already processed/commented on a post."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM moltbook_posts WHERE moltbook_post_id = %s LIMIT 1",
                (moltbook_post_id,),
            )
            return await cur.fetchone() is not None


async def _get_recent_completed_validation(pool) -> Dict[str, Any] | None:
    """Get a recent completed validation to reference in comments."""
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("""
                SELECT * FROM validations
                WHERE status IN ('approved', 'rejected', 'completed')
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = await cur.fetchone()
            return dict(row) if row else None


async def _get_and_increment_cycle(pool) -> int:
    """Track cron cycle count in a single-row DB table.

    Creates the table on first use. Returns the new cycle count.
    """
    async with pool.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS moltbook_cron_state (
                id          INTEGER PRIMARY KEY DEFAULT 1,
                cycle_count INTEGER NOT NULL DEFAULT 0,
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CHECK (id = 1)
            )
        """)
        await conn.execute("""
            INSERT INTO moltbook_cron_state (id, cycle_count, updated_at)
            VALUES (1, 1, NOW())
            ON CONFLICT (id) DO UPDATE
            SET cycle_count = moltbook_cron_state.cycle_count + 1,
                updated_at = NOW()
        """)
        async with conn.cursor() as cur:
            await cur.execute("SELECT cycle_count FROM moltbook_cron_state WHERE id = 1")
            row = await cur.fetchone()
            return row[0] if row else 1


async def _get_recent_moltbook_posts(pool, days: int = 7) -> List[Dict[str, Any]]:
    """Get Moltbook posts from the last N days."""
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("""
                SELECT * FROM moltbook_posts
                WHERE posted_at > NOW() - INTERVAL '%s days'
                ORDER BY posted_at DESC
            """, (days,))
            return [dict(r) for r in await cur.fetchall()]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_cron())

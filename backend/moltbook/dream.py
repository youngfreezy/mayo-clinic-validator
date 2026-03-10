"""
Dream cycle -- sleep-time compute / memory consolidation for the Moltbook loop.

Periodically (every ~5 cron cycles) the agent enters a "dream" state where it:
  1. Reviews recent validation posts and engagement data
  2. Reflects on patterns via LLM call
  3. Consolidates insights into compressed, durable learnings
  4. Prunes stale or contradictory feedback entries
  5. Stores dream log in moltbook_dreams table

Dreams are deeper reflection, not reactive signal processing.

SECURITY: All LLM dream outputs are sanitized before storage.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from moltbook.sanitize import sanitize

logger = logging.getLogger(__name__)

MAX_DREAM_LOGS = 10

# Contradiction pairs for feedback pruning
_CONTRADICTION_PAIRS = [
    ("too_strict", "too_lenient"),
    ("too_lenient", "too_strict"),
]


async def _ensure_dream_table(pool) -> None:
    """Create moltbook_dreams table if it doesn't exist."""
    async with pool.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS moltbook_dreams (
                id          SERIAL PRIMARY KEY,
                insights    JSONB NOT NULL DEFAULT '[]',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


async def run_dream_cycle(pool) -> None:
    """Execute a dream cycle -- deep reflection on recent activity.

    Queries recent posts + feedback from Postgres, calls an LLM for
    reflection, sanitizes the output, stores consolidated insights,
    and prunes contradictory feedback entries.
    """
    import psycopg

    await _ensure_dream_table(pool)

    # Gather recent posts and feedback
    recent_posts = await _get_recent_posts(pool)
    recent_feedback = await _get_recent_feedback(pool)

    if not recent_posts and not recent_feedback:
        logger.info("[dream] No recent posts or feedback -- skipping dream cycle")
        return

    # Build context for reflection
    post_summaries = []
    for p in recent_posts:
        post_summaries.append(
            f"- Post '{(p.get('title') or 'untitled')[:60]}': "
            f"upvotes={p.get('upvotes', 0)}, downvotes={p.get('downvotes', 0)}, "
            f"comments={p.get('comment_count', 0)}"
        )

    feedback_summaries = []
    for f in recent_feedback:
        feedback_summaries.append(
            f"- Rule '{f.get('rule_id', '?')}': {f.get('feedback_type', '?')} "
            f"(signals={f.get('signal_count', 0)})"
        )

    # Load previous dream insights for continuity
    previous_insights = await get_latest_dream_insights(pool)
    prev_context = ""
    if previous_insights:
        prev_context = "\n\nPrevious consolidated insights:\n" + "\n".join(
            f"{i + 1}. {ins}" for i, ins in enumerate(previous_insights)
        )

    reflection_prompt = (
        "Review these recent validations, their community reception, and accumulated "
        "rule feedback. What patterns emerge? Are any rules consistently flagged? "
        "What should change? Compress into 3-5 actionable insights.\n\n"
        f"Recent posts:\n{chr(10).join(post_summaries) if post_summaries else 'None'}\n\n"
        f"Rule feedback:\n{chr(10).join(feedback_summaries) if feedback_summaries else 'None'}"
        f"{prev_context}\n\n"
        "Respond with ONLY a JSON array of 3-5 insight strings. Example:\n"
        '["insight 1", "insight 2", "insight 3"]\n\n'
        "Do not include any text outside the JSON array."
    )

    try:
        logger.info("[dream] Starting dream cycle -- reflecting on %d posts, %d feedback entries...",
                     len(recent_posts), len(recent_feedback))

        insights = await _call_llm_for_reflection(reflection_prompt)

        if not insights:
            logger.warn("[dream] No insights returned from LLM -- skipping")
            return

        # Sanitize each insight
        clean_insights = []
        for insight in insights[:5]:
            if isinstance(insight, str):
                clean = sanitize(insight, max_length=300, context="dream_insight")
                if clean:
                    clean_insights.append(clean)

        if not clean_insights:
            logger.warning("[dream] All insights empty after sanitization -- skipping")
            return

        # Store dream entry
        await _store_dream(pool, clean_insights)

        # Prune contradictory feedback entries
        await _prune_contradictory_feedback(pool, clean_insights)

        logger.info("[dream] Dream cycle complete -- stored %d insights", len(clean_insights))

    except Exception as e:
        logger.error("[dream] Dream cycle failed: %s", e)


async def _call_llm_for_reflection(prompt: str) -> List[str]:
    """Call an LLM for dream reflection.

    Uses the same OpenAI pattern as the rest of the Mayo Clinic backend.
    """
    try:
        from config.settings import settings
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            max_tokens=1024,
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a reflective meta-analyst. Your job is to find patterns "
                        "in health content validation performance and community feedback, "
                        "then compress your analysis into concise, actionable bullet points. "
                        "Be specific and evidence-based. Output only a JSON array of strings."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        raw_text = response.choices[0].message.content or ""
        json_str = raw_text.strip()

        # Strip markdown code fences if present
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[1] if "\n" in json_str else json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

        result = json.loads(json_str)
        if isinstance(result, list):
            return [str(item) for item in result if isinstance(item, str)]

        logger.warning("[dream] LLM did not return a JSON array")
        return []

    except ImportError:
        logger.warning("[dream] OpenAI SDK not available -- skipping LLM call")
        return []
    except Exception as e:
        logger.error("[dream] LLM reflection call failed: %s", e)
        return []


async def _get_recent_posts(pool) -> List[Dict[str, Any]]:
    """Get recent moltbook_posts for dream reflection."""
    import psycopg
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("""
                SELECT title, upvotes, downvotes, comment_count, posted_at
                FROM moltbook_posts
                ORDER BY posted_at DESC
                LIMIT 20
            """)
            return [dict(r) for r in await cur.fetchall()]


async def _get_recent_feedback(pool) -> List[Dict[str, Any]]:
    """Get recent moltbook_feedback for dream reflection."""
    import psycopg
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("""
                SELECT rule_id, feedback_type, signal_count, created_at
                FROM moltbook_feedback
                ORDER BY updated_at DESC
                LIMIT 30
            """)
            return [dict(r) for r in await cur.fetchall()]


async def _store_dream(pool, insights: List[str]) -> None:
    """Store a dream entry, enforcing MAX_DREAM_LOGS cap."""
    async with pool.connection() as conn:
        # Insert new dream
        await conn.execute(
            "INSERT INTO moltbook_dreams (insights, created_at) VALUES (%s::jsonb, NOW())",
            (json.dumps(insights),),
        )

        # Enforce cap -- delete oldest entries beyond MAX_DREAM_LOGS
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM moltbook_dreams")
            count = (await cur.fetchone())[0]

        if count > MAX_DREAM_LOGS:
            excess = count - MAX_DREAM_LOGS
            await conn.execute("""
                DELETE FROM moltbook_dreams
                WHERE id IN (
                    SELECT id FROM moltbook_dreams
                    ORDER BY created_at ASC
                    LIMIT %s
                )
            """, (excess,))
            logger.info("[dream] Rotated out %d oldest dream entries", excess)


async def get_latest_dream_insights(pool) -> List[str]:
    """Get insights from the most recent dream entry.

    Returns an empty list if no dreams exist or DB is unavailable.
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT insights FROM moltbook_dreams
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                row = await cur.fetchone()
                if row and row[0]:
                    insights = row[0]
                    if isinstance(insights, str):
                        insights = json.loads(insights)
                    if isinstance(insights, list):
                        return [str(i) for i in insights]
        return []
    except Exception as e:
        logger.debug("[dream] Failed to load dream insights: %s", e)
        return []


async def _prune_contradictory_feedback(pool, insights: List[str]) -> None:
    """Prune feedback entries that contradict dream insights.

    Dreams cannot override the 5+ signal threshold for patches.
    This only removes low-signal contradictory feedback entries.
    """
    if not insights:
        return

    insight_text = " ".join(insights).lower()

    # If insights suggest rules are "too strict", prune "too_lenient" feedback (and vice versa)
    prune_types = []
    if "too strict" in insight_text or "overly strict" in insight_text:
        prune_types.append("too_lenient")
    if "too lenient" in insight_text or "overly lenient" in insight_text:
        prune_types.append("too_strict")

    if not prune_types:
        return

    async with pool.connection() as conn:
        for fb_type in prune_types:
            async with conn.cursor() as cur:
                # Only prune low-signal entries (below the 5-signal threshold)
                await cur.execute("""
                    DELETE FROM moltbook_feedback
                    WHERE feedback_type = %s AND signal_count < 5
                """, (fb_type,))
                if cur.rowcount > 0:
                    logger.info(
                        "[dream] Pruned %d contradictory '%s' feedback entries (low-signal)",
                        cur.rowcount, fb_type,
                    )

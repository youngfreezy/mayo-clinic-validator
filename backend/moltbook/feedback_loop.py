"""
Feedback processing loop for Moltbook engagement data.

Reads engagement metrics (votes, comments) from Moltbook posts,
correlates them with stored validation outcomes in Postgres,
and generates rule adjustment recommendations when enough consistent
signals accumulate.

SECURITY: All Moltbook content is sanitized before processing.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg

from moltbook.sanitize import sanitize

logger = logging.getLogger(__name__)

# Feedback types
FEEDBACK_TYPES = ("too_strict", "too_lenient", "correct", "incorrect")

# Signal threshold before flagging for rule review
SIGNAL_THRESHOLD = 5

# Maximum feedback entries per rule (rotate oldest when exceeded)
MAX_FEEDBACK_PER_RULE = 50

# Keywords that signal feedback type in comments
_STRICT_KEYWORDS = [
    "too strict", "too harsh", "overly strict", "false positive",
    "not a real issue", "shouldn't fail", "should pass",
]
_LENIENT_KEYWORDS = [
    "too lenient", "too lax", "missed", "should have caught",
    "false negative", "should fail", "shouldn't pass",
]
_INCORRECT_KEYWORDS = [
    "wrong", "incorrect", "inaccurate", "error in", "mistake",
    "bad analysis", "flawed",
]


def _classify_comment(text: str) -> Optional[str]:
    """
    Classify a sanitized comment into a feedback type.
    Returns None if no clear signal is detected.
    """
    lower = text.lower()
    for kw in _STRICT_KEYWORDS:
        if kw in lower:
            return "too_strict"
    for kw in _LENIENT_KEYWORDS:
        if kw in lower:
            return "too_lenient"
    for kw in _INCORRECT_KEYWORDS:
        if kw in lower:
            return "incorrect"
    return None


async def process_post_engagement(
    pool,
    moltbook_post_id: str,
    upvotes: int,
    downvotes: int,
    comments: List[Dict[str, Any]],
) -> None:
    """
    Process engagement data for a single Moltbook post.

    1. Update the moltbook_posts table with latest vote/comment counts.
    2. Classify comments into feedback signals.
    3. Accumulate feedback in moltbook_feedback table.
    4. Flag rules for review when threshold is reached.
    """
    async with pool.connection() as conn:
        # Update post engagement metrics
        await conn.execute("""
            UPDATE moltbook_posts
            SET upvotes = %s, downvotes = %s, comment_count = %s, updated_at = NOW()
            WHERE moltbook_post_id = %s
        """, (upvotes, downvotes, len(comments), moltbook_post_id))

        # Look up the validation_id linked to this post
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                "SELECT validation_id FROM moltbook_posts WHERE moltbook_post_id = %s",
                (moltbook_post_id,),
            )
            row = await cur.fetchone()

        if not row or not row.get("validation_id"):
            return

        validation_id = row["validation_id"]

        # Get the validation's findings to know which rules were involved
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                "SELECT findings FROM validations WHERE id = %s",
                (validation_id,),
            )
            val_row = await cur.fetchone()

        if not val_row:
            return

        findings = val_row.get("findings", [])
        if isinstance(findings, str):
            findings = json.loads(findings)

        # Extract rule IDs from findings
        rule_ids = set()
        for finding in findings:
            agent = finding.get("agent", "")
            # Use agent name as a rule identifier if no explicit rule_id
            rule_ids.add(agent)
            for issue in finding.get("issues", []):
                if isinstance(issue, dict) and issue.get("rule_id"):
                    rule_ids.add(issue["rule_id"])

        # Classify each comment (filter spam, sanitize first!)
        for comment in comments:
            # Skip spam comments
            if comment.get("is_spam", False):
                continue

            raw_body = comment.get("body", "") or comment.get("text", "")
            clean_body = sanitize(raw_body, context="moltbook_comment", max_length=500)
            feedback_type = _classify_comment(clean_body)

            if not feedback_type:
                continue

            # Apply feedback to all rules involved in this validation
            for rule_id in rule_ids:
                await _upsert_feedback(
                    conn,
                    rule_id=rule_id,
                    feedback_type=feedback_type,
                    source=f"moltbook_comment:{moltbook_post_id}",
                    details={
                        "comment_text": clean_body[:200],
                        "validation_id": validation_id,
                        "upvotes": upvotes,
                        "downvotes": downvotes,
                    },
                )

        # Also use vote ratio as a signal
        total_votes = upvotes + downvotes
        if total_votes >= 3:
            ratio = downvotes / total_votes
            if ratio > 0.7:
                # Heavy downvotes suggest the validation was wrong
                for rule_id in rule_ids:
                    await _upsert_feedback(
                        conn,
                        rule_id=rule_id,
                        feedback_type="incorrect",
                        source=f"moltbook_votes:{moltbook_post_id}",
                        details={
                            "upvotes": upvotes,
                            "downvotes": downvotes,
                            "ratio": ratio,
                            "validation_id": validation_id,
                        },
                    )


async def _upsert_feedback(
    conn,
    rule_id: str,
    feedback_type: str,
    source: str,
    details: Dict[str, Any],
) -> None:
    """
    Insert or increment feedback for a rule.

    If the same (rule_id, feedback_type) exists, increment signal_count.
    Enforce MAX_FEEDBACK_PER_RULE cap by rotating oldest entries.
    """
    if feedback_type not in FEEDBACK_TYPES:
        logger.warning("Invalid feedback type %r, skipping", feedback_type)
        return

    # Check existing entry count for this rule
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM moltbook_feedback WHERE rule_id = %s",
            (rule_id,),
        )
        count = (await cur.fetchone())["cnt"]

    # Rotate oldest if at cap
    if count >= MAX_FEEDBACK_PER_RULE:
        await conn.execute("""
            DELETE FROM moltbook_feedback
            WHERE id IN (
                SELECT id FROM moltbook_feedback
                WHERE rule_id = %s
                ORDER BY created_at ASC
                LIMIT %s
            )
        """, (rule_id, count - MAX_FEEDBACK_PER_RULE + 1))

    # Try to increment existing matching feedback
    async with conn.cursor() as cur:
        await cur.execute("""
            UPDATE moltbook_feedback
            SET signal_count = signal_count + 1,
                details = %s::jsonb,
                updated_at = NOW()
            WHERE rule_id = %s AND feedback_type = %s AND source = %s
        """, (json.dumps(details), rule_id, feedback_type, source))

        if cur.rowcount == 0:
            # Insert new feedback entry
            await conn.execute("""
                INSERT INTO moltbook_feedback
                    (rule_id, feedback_type, source, signal_count, details, created_at, updated_at)
                VALUES (%s, %s, %s, 1, %s::jsonb, NOW(), NOW())
            """, (rule_id, feedback_type, source, json.dumps(details)))

    # Check if threshold reached — flag for human review
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute("""
            SELECT feedback_type, SUM(signal_count) AS total
            FROM moltbook_feedback
            WHERE rule_id = %s
            GROUP BY feedback_type
            ORDER BY total DESC
        """, (rule_id,))
        rows = await cur.fetchall()

    for row in rows:
        if row["total"] >= SIGNAL_THRESHOLD:
            logger.warning(
                "RULE REVIEW FLAGGED: rule_id=%s has %d signals of type '%s' — "
                "human review recommended before any adjustment",
                rule_id,
                row["total"],
                row["feedback_type"],
            )


async def get_rule_feedback_summary(pool, rule_id: str) -> Dict[str, Any]:
    """
    Get aggregated feedback summary for a rule.
    Used by the rules loader to inject community context.
    """
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("""
                SELECT feedback_type, SUM(signal_count) AS total
                FROM moltbook_feedback
                WHERE rule_id = %s
                GROUP BY feedback_type
                ORDER BY total DESC
            """, (rule_id,))
            rows = await cur.fetchall()

    summary: Dict[str, int] = {}
    for row in rows:
        summary[row["feedback_type"]] = row["total"]

    return {
        "rule_id": rule_id,
        "signals": summary,
        "total_signals": sum(summary.values()),
        "needs_review": any(v >= SIGNAL_THRESHOLD for v in summary.values()),
    }


async def get_all_actionable_feedback(pool) -> List[Dict[str, Any]]:
    """
    Return all rules with feedback signals >= SIGNAL_THRESHOLD.
    These are candidates for rule adjustment (pending human review).
    """
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute("""
                SELECT rule_id, feedback_type, SUM(signal_count) AS total
                FROM moltbook_feedback
                GROUP BY rule_id, feedback_type
                HAVING SUM(signal_count) >= %s
                ORDER BY total DESC
            """, (SIGNAL_THRESHOLD,))
            rows = await cur.fetchall()

    return [dict(r) for r in rows]

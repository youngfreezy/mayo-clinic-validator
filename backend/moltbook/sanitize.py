"""
SECURITY-CRITICAL input sanitization for Moltbook content.

All external text from Moltbook (posts, comments, usernames) MUST pass through
sanitize() before being stored, displayed, or injected into LLM context.
"""

import base64
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt-injection patterns (case-insensitive)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|context)",
        r"ignore\s+all\s+prior",
        r"you\s+are\s+now\b",
        r"^system\s*:",
        r"^assistant\s*:",
        r"^human\s*:",
        r"<\s*system\s*>",
        r"<\s*/?\s*system\s*>",
        r"\bIMPORTANT\s*:",
        r"\bOVERRIDE\b",
        r"new\s+instructions\s*:",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"forget\s+(all\s+)?(previous|prior|above)",
        r"do\s+not\s+follow\s+(previous|prior|above)",
        r"act\s+as\s+if\s+you\s+are",
        r"\bpretend\s+you\s+are\b",
        r"jailbreak",
        r"DAN\s+mode",
    ]
]

# Match markdown code blocks: ```...```
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

# Match XML/HTML tags
_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^>]*)?>")

# Match URLs (keep github.com)
_URL_RE = re.compile(
    r"https?://(?!github\.com)[^\s<>\"')\]]+",
    re.IGNORECASE,
)

# Match base64 blobs (40+ chars of base64 alphabet)
_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


def sanitize(
    text: Optional[str],
    *,
    max_length: int = 500,
    context: str = "unknown",
) -> str:
    """
    Sanitize external Moltbook content for safe use.

    Args:
        text: Raw input text (may be None).
        max_length: Maximum output length in characters.
        context: Label for log messages (e.g. "comment", "post_title").

    Returns:
        Cleaned text, guaranteed <= max_length chars.
    """
    if not text:
        return ""

    original_len = len(text)
    clean = text

    # 1. Strip markdown code blocks
    clean = _CODE_BLOCK_RE.sub("", clean)

    # 2. Remove XML/HTML tags
    clean = _TAG_RE.sub("", clean)

    # 3. Remove prompt injection patterns
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(clean)
        if match:
            logger.warning(
                "Sanitization [%s]: removed injection pattern %r from content (len=%d)",
                context,
                match.group(),
                original_len,
            )
            clean = pattern.sub("", clean)

    # 4. Remove base64 encoded strings
    b64_match = _BASE64_RE.search(clean)
    if b64_match:
        # Verify it actually decodes as base64 before removing
        try:
            base64.b64decode(b64_match.group(), validate=True)
            logger.warning(
                "Sanitization [%s]: removed base64 blob (%d chars)",
                context,
                len(b64_match.group()),
            )
            clean = _BASE64_RE.sub("", clean)
        except Exception:
            pass  # Not real base64, leave it

    # 5. Remove non-GitHub URLs
    url_matches = _URL_RE.findall(clean)
    if url_matches:
        logger.warning(
            "Sanitization [%s]: removed %d non-GitHub URL(s)",
            context,
            len(url_matches),
        )
        clean = _URL_RE.sub("", clean)

    # 6. Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()

    # 7. Truncate
    if len(clean) > max_length:
        logger.info(
            "Sanitization [%s]: truncated from %d to %d chars",
            context,
            len(clean),
            max_length,
        )
        clean = clean[:max_length]

    if len(clean) < original_len * 0.5 and original_len > 20:
        logger.warning(
            "Sanitization [%s]: removed >50%% of content (original=%d, clean=%d)",
            context,
            original_len,
            len(clean),
        )

    return clean

"""
Async HTTP client for the Moltbook social API.

Handles authentication, rate limiting, and math verification challenges.
All responses are returned as dicts; callers handle domain logic.
"""

import logging
import os
import re
import time
from collections import deque
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.moltbook.com/api/v1"


class RateLimitError(Exception):
    """Raised when a Moltbook rate limit would be violated."""


class MoltbookClient:
    """
    Async Moltbook API client with built-in rate limiting.

    Rate limits (enforced client-side to avoid bans):
      - 1 post per 30 minutes
      - 50 comments per day (rolling 24h window)
      - 30 writes (any mutation) per 60 seconds
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = BASE_URL):
        self.api_key = api_key or os.environ.get("MOLTBOOK_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self._http: Optional[httpx.AsyncClient] = None

        # Rate limit tracking (timestamps as float epoch seconds)
        self._post_timestamps: deque[float] = deque(maxlen=100)
        self._comment_timestamps: deque[float] = deque(maxlen=200)
        self._write_timestamps: deque[float] = deque(maxlen=200)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _prune(self, dq: deque, window_seconds: float) -> None:
        cutoff = time.time() - window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()

    def _check_post_limit(self) -> None:
        self._prune(self._post_timestamps, 1800)  # 30 min
        if len(self._post_timestamps) >= 1:
            raise RateLimitError("Post rate limit: 1 post per 30 minutes")

    def _check_comment_limit(self) -> None:
        self._prune(self._comment_timestamps, 86400)  # 24h
        if len(self._comment_timestamps) >= 50:
            raise RateLimitError("Comment rate limit: 50 comments per 24 hours")

    def _check_write_limit(self) -> None:
        self._prune(self._write_timestamps, 60)
        if len(self._write_timestamps) >= 30:
            raise RateLimitError("Write rate limit: 30 writes per 60 seconds")

    def _record_write(self) -> None:
        now = time.time()
        self._write_timestamps.append(now)

    def _record_post(self) -> None:
        now = time.time()
        self._post_timestamps.append(now)
        self._record_write()

    def _record_comment(self) -> None:
        now = time.time()
        self._comment_timestamps.append(now)
        self._record_write()

    # ------------------------------------------------------------------
    # Verification challenge solver
    # ------------------------------------------------------------------

    @staticmethod
    def solve_challenge(challenge_text: str) -> str:
        """
        Parse and solve a Moltbook math verification challenge.

        Moltbook sends weirdly formatted challenge_text like:
          "What is 12 plus 7?"
          "Calculate: 45 minus 12"
          "Solve 8 times 3"
          "What's 100 divided by 5?"
          "15 + 8 = ?"
          "   3  *   7   "

        Returns the answer as "XX.00" format string.
        """
        text = challenge_text.strip().lower()

        # Map word operators to symbols
        text = text.replace("plus", "+").replace("minus", "-")
        text = text.replace("times", "*").replace("multiplied by", "*")
        text = text.replace("divided by", "/")

        # Extract all numbers
        numbers = [float(n) for n in re.findall(r"-?\d+\.?\d*", text)]
        if len(numbers) < 2:
            raise ValueError(f"Could not parse two numbers from challenge: {challenge_text!r}")

        a, b = numbers[0], numbers[1]

        # Detect operation from the text between the numbers
        # Find the operator symbol between/around the numbers
        if "+" in text:
            result = a + b
        elif "-" in text or "minus" in challenge_text.lower():
            result = a - b
        elif "*" in text:
            result = a * b
        elif "/" in text:
            if b == 0:
                raise ValueError("Division by zero in challenge")
            result = a / b
        else:
            # Default: try addition (some challenges are ambiguous)
            logger.warning("Could not detect operation in %r, defaulting to addition", challenge_text)
            result = a + b

        return f"{result:.2f}"

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    async def verify(self, challenge_id: str, challenge_text: str) -> Dict[str, Any]:
        """Solve a math verification challenge and POST the answer."""
        answer = self.solve_challenge(challenge_text)
        client = await self._client()
        resp = await client.post("/verify", json={
            "challenge_id": challenge_id,
            "answer": answer,
        })
        resp.raise_for_status()
        return resp.json()

    async def create_post(self, title: str, body: str) -> Dict[str, Any]:
        """Create a new Moltbook post. Handles verification if required."""
        self._check_post_limit()
        self._check_write_limit()

        client = await self._client()
        resp = await client.post("/posts", json={"title": title, "body": body})

        # Handle verification challenge
        if resp.status_code == 202:
            challenge = resp.json()
            logger.info("Moltbook verification challenge received: %s", challenge.get("challenge_id"))
            verify_result = await self.verify(
                challenge["challenge_id"],
                challenge["challenge_text"],
            )
            # Retry post after verification
            resp = await client.post("/posts", json={"title": title, "body": body})

        resp.raise_for_status()
        self._record_post()
        return resp.json()

    async def comment(self, post_id: str, body: str) -> Dict[str, Any]:
        """Comment on a Moltbook post."""
        self._check_comment_limit()
        self._check_write_limit()

        client = await self._client()
        resp = await client.post(f"/posts/{post_id}/comments", json={"body": body})
        resp.raise_for_status()
        self._record_comment()
        return resp.json()

    async def vote(self, post_id: str, direction: str = "up") -> Dict[str, Any]:
        """Upvote or downvote a Moltbook post."""
        self._check_write_limit()

        client = await self._client()
        resp = await client.post(f"/posts/{post_id}/vote", json={"direction": direction})
        resp.raise_for_status()
        self._record_write()
        return resp.json()

    async def get_feed(self) -> List[Dict[str, Any]]:
        """Get the Moltbook home feed."""
        client = await self._client()
        resp = await client.get("/home")
        resp.raise_for_status()
        data = resp.json()
        # API may return {"posts": [...]} or a list directly
        if isinstance(data, dict):
            return data.get("posts", [])
        return data

    async def get_agent_info(self) -> Dict[str, Any]:
        """Get current agent profile/info."""
        client = await self._client()
        resp = await client.get("/agents/me")
        resp.raise_for_status()
        return resp.json()

    async def get_post(self, post_id: str) -> Dict[str, Any]:
        """Get a single post with its comments."""
        client = await self._client()
        resp = await client.get(f"/posts/{post_id}")
        resp.raise_for_status()
        return resp.json()

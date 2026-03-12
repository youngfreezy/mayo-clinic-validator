"""
Mayo Clinic URL scraper using curl_cffi (Chrome TLS impersonation) + BeautifulSoup.

curl_cffi impersonates Chrome's exact TLS fingerprint, bypassing bot detection
that blocks standard Python HTTP clients (httpx/requests) on cloud IPs.
Falls back to Google Cache if direct fetch still gets blocked.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAYO_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

DATE_PATTERN = re.compile(
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?)\s+\d{1,2},\s+\d{4}",
    re.IGNORECASE,
)


async def _fetch_with_curl_cffi(url: str) -> str:
    """Fetch URL using curl_cffi with Chrome browser impersonation."""
    from curl_cffi.requests import AsyncSession

    async with AsyncSession() as session:
        response = await session.get(
            url,
            impersonate="chrome",
            headers=MAYO_HEADERS,
            timeout=30,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.text


async def _fetch_with_google_cache(url: str) -> str:
    """Fetch Google's cached version of the URL as a fallback."""
    import httpx

    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote_plus(url)}"
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            **MAYO_HEADERS,
        },
    ) as client:
        response = await client.get(cache_url)
        response.raise_for_status()
        return response.text


async def scrape_mayo_url(url: str) -> Dict[str, Any]:
    """
    Fetch and parse a Mayo Clinic content page.

    Strategy:
    1. Try curl_cffi with Chrome TLS impersonation (bypasses fingerprint detection).
    2. Fall back to Google Cache if direct fetch is blocked (403/503).

    Returns a dict with: title, meta_description, body_text, structured_data,
    last_reviewed, headings, canonical_url, og_tags, internal_links, external_links.
    """
    raw_html = None

    # Strategy 1: curl_cffi with Chrome impersonation
    try:
        raw_html = await _fetch_with_curl_cffi(url)
        logger.info("Successfully fetched %s via curl_cffi", url)
    except Exception as e:
        logger.warning("curl_cffi failed for %s: %s — trying Google Cache", url, e)

    # Strategy 2: Google Cache fallback
    if raw_html is None:
        try:
            raw_html = await _fetch_with_google_cache(url)
            logger.info("Successfully fetched %s via Google Cache", url)
        except Exception as e:
            logger.warning("Google Cache failed for %s: %s", url, e)

    if raw_html is None:
        raise RuntimeError(
            f"All fetch strategies failed for '{url}'. "
            "Mayo Clinic may be blocking requests from this server's IP."
        )

    soup = BeautifulSoup(raw_html, "lxml")

    return {
        "raw_html": raw_html,
        "title": _extract_title(soup),
        "meta_description": _extract_meta(soup, "description"),
        "canonical_url": _extract_canonical(soup),
        "og_tags": _extract_og_tags(soup),
        "structured_data": _extract_json_ld(soup),
        "body_text": _extract_body(soup),
        "last_reviewed": _extract_last_reviewed(soup),
        "headings": _extract_headings(soup),
        "internal_links": _extract_links(soup, internal=True),
        "external_links": _extract_links(soup, internal=False),
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True).split("|")[0].strip()
    return ""


def _extract_meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name})
    if tag:
        return tag.get("content", "")
    return ""


def _extract_canonical(soup: BeautifulSoup) -> Optional[str]:
    tag = soup.find("link", attrs={"rel": "canonical"})
    return tag.get("href") if tag else None


def _extract_og_tags(soup: BeautifulSoup) -> Dict[str, str]:
    og: Dict[str, str] = {}
    for tag in soup.find_all("meta", attrs={"property": True}):
        prop = tag.get("property", "")
        if prop.startswith("og:"):
            og[prop] = tag.get("content", "")
    return og


def _extract_json_ld(soup: BeautifulSoup) -> List[Dict]:
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
        except (json.JSONDecodeError, TypeError):
            pass
    return results


def _extract_body(soup: BeautifulSoup) -> str:
    """
    Extract main article body text. Mayo Clinic uses several possible containers.
    Cascade through selectors from most specific to least.
    """
    main = (
        soup.find("div", id="main-content")
        or soup.find("main")
        or soup.find("article")
        or soup.find("div", class_="content")
        or soup.find("div", class_="aem-Grid")
        or soup.body
    )
    if not main:
        return ""
    text = main.get_text(separator="\n", strip=True)
    # Truncate to 8000 chars to stay within LLM context window
    return text[:8000]


def _extract_last_reviewed(soup: BeautifulSoup) -> Optional[str]:
    """
    Mayo Clinic shows "Updated by Mayo Clinic Staff — June 14, 2024" or
    "Reviewed by Mayo Clinic Staff" near the bottom of articles.
    """
    review_phrases = [
        "updated by mayo clinic",
        "reviewed by mayo clinic",
        "last updated:",
        "mayo clinic staff",
    ]
    for el in soup.find_all(["p", "div", "span", "time"]):
        text = el.get_text(strip=True).lower()
        if any(phrase in text for phrase in review_phrases):
            full_text = el.get_text(strip=True)
            match = DATE_PATTERN.search(full_text)
            if match:
                return match.group(0)
    return None


def _extract_headings(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    headings = []
    main = (
        soup.find("div", id="main-content")
        or soup.find("main")
        or soup.find("article")
        or soup.body
    )
    if not main:
        return headings
    for tag in main.find_all(["h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if text:
            headings.append({"level": int(tag.name[1]), "text": text})
    return headings


def _extract_links(soup: BeautifulSoup, internal: bool) -> List[str]:
    links = []
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        is_internal = href.startswith("/") or "mayoclinic.org" in href
        if internal and is_internal:
            links.append(href)
        elif not internal and href.startswith("http") and not is_internal:
            links.append(href)
    return links[:50]

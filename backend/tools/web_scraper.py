"""
Mayo Clinic URL scraper using httpx + BeautifulSoup.

Mayo Clinic serves server-side rendered HTML, so httpx is sufficient.
A real browser User-Agent is required — without it you get a 403 or JS-only shell.
"""

import json
import re
from typing import Dict, Any, List, Optional

import httpx
from bs4 import BeautifulSoup

MAYO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

DATE_PATTERN = re.compile(
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?)\s+\d{1,2},\s+\d{4}",
    re.IGNORECASE,
)


async def scrape_mayo_url(url: str) -> Dict[str, Any]:
    """
    Fetch and parse a Mayo Clinic content page.

    Returns a dict with: title, meta_description, body_text, structured_data,
    last_reviewed, headings, canonical_url, og_tags, internal_links, external_links.

    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30.0,
        headers=MAYO_HEADERS,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    raw_html = response.text
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

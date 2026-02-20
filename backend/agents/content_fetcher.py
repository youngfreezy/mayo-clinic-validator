"""
Content fetcher node — the first node in the LangGraph pipeline.
Scrapes the Mayo Clinic URL and stores results in ValidationState.
"""

from pipeline.state import ValidationState
from tools.web_scraper import scrape_mayo_url


async def fetch_content_node(state: ValidationState) -> dict:
    """
    Scrapes the Mayo Clinic URL from state["url"].
    Returns scraped_content dict and updates status to "running".
    On failure, sets status to "failed" and appends to errors.
    """
    url = state["url"]
    try:
        scraped = await scrape_mayo_url(url)
        return {
            "scraped_content": scraped,
            "status": "running",
        }
    except Exception as e:
        return {
            "scraped_content": None,
            "status": "failed",
            "errors": [f"Failed to scrape URL '{url}': {str(e)}"],
        }

"""
Backend API integration tests.

Uses FastAPI's TestClient (sync) and AsyncClient (async) with mocked
external dependencies (OpenAI, web scraper, PGVector) so tests run offline.

Run: pytest tests/ -v
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures: mock all external calls before importing main
# ---------------------------------------------------------------------------

MOCK_SCRAPED = {
    "title": "Diabetes — Symptoms and causes",
    "meta_description": "Diabetes is a disease that occurs when your blood glucose, also called blood sugar, is too high.",
    "body_text": "Diabetes mellitus is a group of metabolic diseases characterized by high blood sugar.\n" * 20,
    "structured_data": [{"@type": "MedicalWebPage", "name": "Diabetes"}],
    "last_reviewed": "June 14, 2024",
    "headings": [
        {"level": 1, "text": "Diabetes — Symptoms and causes"},
        {"level": 2, "text": "Overview"},
        {"level": 2, "text": "Symptoms"},
        {"level": 2, "text": "Causes"},
        {"level": 2, "text": "Treatment"},
    ],
    "canonical_url": "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444",
    "og_tags": {
        "og:title": "Diabetes — Symptoms and causes - Mayo Clinic",
        "og:description": "Diabetes is a disease that occurs when your blood glucose is too high.",
        "og:type": "article",
    },
    "internal_links": ["/diseases-conditions/diabetes/diagnosis-treatment/drc-20371451"],
    "external_links": [],
}

MOCK_AGENT_RESPONSE = json.dumps({
    "passed": True,
    "score": 0.9,
    "issues": [],
    "recommendations": ["Consider adding more internal links"],
})


@pytest.fixture(autouse=True)
def mock_external_calls():
    """Patch all external calls (OpenAI, scraper, PGVector) for every test."""
    mock_llm_msg = MagicMock()
    mock_llm_msg.content = MOCK_AGENT_RESPONSE

    mock_ainvoke = AsyncMock(return_value=mock_llm_msg)

    with (
        patch("tools.web_scraper.scrape_mayo_url", new=AsyncMock(return_value=MOCK_SCRAPED)),
        patch("langchain_openai.ChatOpenAI", autospec=True) as mock_llm_cls,
        patch("tools.rag_retriever.get_retriever") as mock_retriever,
    ):
        # Make ChatOpenAI return a mock that supports __or__ (chain) and ainvoke
        mock_chain = MagicMock()
        mock_chain.ainvoke = mock_ainvoke
        mock_llm_instance = MagicMock()
        mock_llm_instance.__or__ = MagicMock(return_value=mock_chain)
        mock_llm_cls.return_value = mock_llm_instance

        # Mock retriever
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.ainvoke = AsyncMock(return_value=[])
        mock_retriever.return_value = mock_retriever_instance

        yield


@pytest.fixture
def client():
    from main import app
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "mayo-clinic-validator"


# ---------------------------------------------------------------------------
# Validation submission
# ---------------------------------------------------------------------------

def test_validate_submit_valid_url(client):
    resp = client.post(
        "/api/validate",
        json={"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "validation_id" in body
    assert len(body["validation_id"]) == 36  # UUID format


def test_validate_submit_non_mayo_url(client):
    resp = client.post(
        "/api/validate",
        json={"url": "https://www.webmd.com/diabetes/symptoms"},
    )
    assert resp.status_code == 422  # Pydantic validation error


def test_validate_submit_missing_url(client):
    resp = client.post("/api/validate", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# State retrieval
# ---------------------------------------------------------------------------

def test_get_validation_not_found(client):
    resp = client.get("/api/validate/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_get_validation_exists(client):
    # Submit first
    submit_resp = client.post(
        "/api/validate",
        json={"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444"},
    )
    vid = submit_resp.json()["validation_id"]

    # Retrieve it
    resp = client.get(f"/api/validate/{vid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["validation_id"] == vid
    assert body["url"] == "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444"
    assert body["status"] in ("pending", "scraping", "running", "awaiting_human")


# ---------------------------------------------------------------------------
# Human decision
# ---------------------------------------------------------------------------

def test_decide_on_nonexistent_validation(client):
    resp = client.post(
        "/api/validate/00000000-0000-0000-0000-000000000000/decide",
        json={"decision": "approve", "feedback": "", "reviewer_id": "test"},
    )
    assert resp.status_code == 404


def test_decide_invalid_status(client):
    # Submit but don't wait for HITL state — status is "pending"
    submit_resp = client.post(
        "/api/validate",
        json={"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444"},
    )
    vid = submit_resp.json()["validation_id"]

    resp = client.post(
        f"/api/validate/{vid}/decide",
        json={"decision": "approve", "feedback": "", "reviewer_id": "test"},
    )
    # Should reject because status != "awaiting_human"
    assert resp.status_code == 400


def test_decide_invalid_decision_value(client):
    # Submit first
    submit_resp = client.post(
        "/api/validate",
        json={"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444"},
    )
    vid = submit_resp.json()["validation_id"]

    resp = client.post(
        f"/api/validate/{vid}/decide",
        json={"decision": "maybe", "feedback": "", "reviewer_id": "test"},
    )
    assert resp.status_code == 422  # Pydantic rejects "maybe"


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def test_list_validations_empty(client):
    resp = client.get("/api/validations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_validations_after_submit(client):
    client.post(
        "/api/validate",
        json={"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444"},
    )
    resp = client.get("/api/validations")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert "validation_id" in items[0]
    assert "url" in items[0]
    assert "status" in items[0]


# ---------------------------------------------------------------------------
# SSE stream endpoint
# ---------------------------------------------------------------------------

def test_stream_nonexistent_validation(client):
    resp = client.get("/api/validate/00000000-0000-0000-0000-000000000000/stream")
    assert resp.status_code == 404


def test_stream_valid_validation_opens(client):
    submit_resp = client.post(
        "/api/validate",
        json={"url": "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444"},
    )
    vid = submit_resp.json()["validation_id"]

    # Open SSE — just check it returns 200 (we won't consume the full stream)
    with client.stream("GET", f"/api/validate/{vid}/stream") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

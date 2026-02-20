"""
Web scraper unit tests.

Tests the HTML parsing logic with real HTML fixtures rather than
making live network calls, so tests run offline and fast.
"""

import pytest
from bs4 import BeautifulSoup

from tools.web_scraper import (
    _extract_title,
    _extract_meta,
    _extract_canonical,
    _extract_og_tags,
    _extract_json_ld,
    _extract_body,
    _extract_last_reviewed,
    _extract_headings,
    _extract_links,
)

# Minimal Mayo Clinic-like HTML fixture
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Diabetes - Symptoms and causes | Mayo Clinic</title>
  <meta name="description" content="Diabetes is a disease that occurs when blood glucose is too high.">
  <link rel="canonical" href="https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444">
  <meta property="og:title" content="Diabetes — Symptoms and causes - Mayo Clinic">
  <meta property="og:description" content="Diabetes is a disease that occurs when blood glucose is too high.">
  <meta property="og:type" content="article">
  <script type="application/ld+json">{"@type": "MedicalWebPage", "name": "Diabetes"}</script>
</head>
<body>
  <h1>Diabetes — Symptoms and causes</h1>
  <div id="main-content">
    <h1>Diabetes — Symptoms and causes</h1>
    <h2>Overview</h2>
    <p>Diabetes mellitus is a group of metabolic diseases.</p>
    <h2>Symptoms</h2>
    <p>Common symptoms include increased thirst and frequent urination.</p>
    <h2>Causes</h2>
    <p>Type 1 results from the pancreas failing to produce enough insulin.</p>
    <p>Updated by Mayo Clinic Staff — June 14, 2024</p>
    <a href="/diseases-conditions/diabetes/diagnosis-treatment/drc-20371451">Diagnosis</a>
    <a href="https://www.nih.gov/diabetes">NIH Diabetes Info</a>
  </div>
</body>
</html>
"""


@pytest.fixture
def soup():
    return BeautifulSoup(SAMPLE_HTML, "lxml")


class TestExtractTitle:
    def test_extracts_h1(self, soup):
        assert _extract_title(soup) == "Diabetes — Symptoms and causes"

    def test_falls_back_to_title_tag(self):
        html = "<html><head><title>Diabetes | Mayo Clinic</title></head><body></body></html>"
        s = BeautifulSoup(html, "lxml")
        title = _extract_title(s)
        assert "Diabetes" in title

    def test_empty_when_no_title(self):
        s = BeautifulSoup("<html><body></body></html>", "lxml")
        assert _extract_title(s) == ""


class TestExtractMeta:
    def test_extracts_description(self, soup):
        desc = _extract_meta(soup, "description")
        assert "blood glucose" in desc

    def test_returns_empty_when_missing(self, soup):
        assert _extract_meta(soup, "keywords") == ""


class TestExtractCanonical:
    def test_extracts_canonical(self, soup):
        canonical = _extract_canonical(soup)
        assert canonical == "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444"

    def test_returns_none_when_missing(self):
        s = BeautifulSoup("<html><head></head><body></body></html>", "lxml")
        assert _extract_canonical(s) is None


class TestExtractOgTags:
    def test_extracts_og_title(self, soup):
        og = _extract_og_tags(soup)
        assert og.get("og:title") == "Diabetes — Symptoms and causes - Mayo Clinic"
        assert og.get("og:type") == "article"

    def test_returns_empty_dict_when_none(self):
        s = BeautifulSoup("<html><head></head><body></body></html>", "lxml")
        assert _extract_og_tags(s) == {}


class TestExtractJsonLd:
    def test_parses_single_json_ld(self, soup):
        data = _extract_json_ld(soup)
        assert len(data) == 1
        assert data[0]["@type"] == "MedicalWebPage"

    def test_returns_empty_on_no_ld(self):
        s = BeautifulSoup("<html><body></body></html>", "lxml")
        assert _extract_json_ld(s) == []

    def test_skips_invalid_json(self):
        html = '<html><head><script type="application/ld+json">not valid json</script></head></html>'
        s = BeautifulSoup(html, "lxml")
        assert _extract_json_ld(s) == []


class TestExtractBody:
    def test_extracts_main_content(self, soup):
        body = _extract_body(soup)
        assert "Diabetes mellitus" in body
        assert "increased thirst" in body

    def test_truncates_to_8000_chars(self):
        long_content = "x " * 10000
        html = f"<html><body><div id='main-content'>{long_content}</div></body></html>"
        s = BeautifulSoup(html, "lxml")
        assert len(_extract_body(s)) <= 8000


class TestExtractLastReviewed:
    def test_finds_date_in_updated_by_text(self, soup):
        date = _extract_last_reviewed(soup)
        assert date == "June 14, 2024"

    def test_returns_none_when_no_date(self):
        s = BeautifulSoup("<html><body><p>No date here</p></body></html>", "lxml")
        assert _extract_last_reviewed(s) is None


class TestExtractHeadings:
    def test_extracts_all_heading_levels(self, soup):
        headings = _extract_headings(soup)
        levels = [h["level"] for h in headings]
        texts = [h["text"] for h in headings]
        assert 1 in levels
        assert 2 in levels
        assert "Diabetes — Symptoms and causes" in texts
        assert "Overview" in texts
        assert "Symptoms" in texts

    def test_returns_empty_on_no_headings(self):
        s = BeautifulSoup("<html><body><p>text</p></body></html>", "lxml")
        assert _extract_headings(s) == []


class TestExtractLinks:
    def test_extracts_internal_links(self, soup):
        internal = _extract_links(soup, internal=True)
        assert any("diseases-conditions" in link for link in internal)

    def test_extracts_external_links(self, soup):
        external = _extract_links(soup, internal=False)
        assert any("nih.gov" in link for link in external)

    def test_does_not_mix_internal_external(self, soup):
        internal = _extract_links(soup, internal=True)
        external = _extract_links(soup, internal=False)
        for link in internal:
            assert "mayoclinic.org" in link or link.startswith("/")
        for link in external:
            assert "mayoclinic.org" not in link

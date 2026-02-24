"""
Empty Tag Agent — scans raw HTML for self-closing or empty tags that should have content.

Deterministic agent (no LLM call). Checks the raw HTML before BeautifulSoup parsing,
since parsers silently fix malformed tags like <title/> into <title></title>.

Only dispatched for HIL (Health Information Library) pages via the triage node.

Checks for:
- Self-closing tags: <title/>, <h1/>, <h2/>, <p/>, etc.
- Empty tags: <title></title>, <h1></h1>, <h1>  </h1>, etc.
"""

import re
from typing import List, Tuple

from pipeline.state import ValidationState, AgentFinding

# Tags that should always have content — self-closing or empty versions are issues
CONTENT_TAGS = ["title", "h1", "h2", "h3", "h4", "p", "a", "li", "td", "th", "label", "button"]

# Self-closing pattern: <title/> or <title /> or <h1  />
SELF_CLOSING_RE = re.compile(
    r"<(" + "|".join(CONTENT_TAGS) + r")(\s[^>]*)?\s*/>",
    re.IGNORECASE,
)

# Empty tag pattern: <title></title> or <h1>   </h1> (whitespace-only content)
EMPTY_TAG_RE = re.compile(
    r"<(" + "|".join(CONTENT_TAGS) + r")(\s[^>]*)?>\s*</\1>",
    re.IGNORECASE,
)

# Score deduction per issue found
DEDUCTION_PER_ISSUE = 0.05
PASS_THRESHOLD = 0.8


def _scan_html(raw_html: str) -> List[Tuple[str, int, str]]:
    """
    Scan raw HTML for self-closing and empty content tags.
    Returns list of (tag_name, line_number, issue_type) tuples.
    """
    issues = []
    lines = raw_html.split("\n")

    for line_num, line in enumerate(lines, start=1):
        for match in SELF_CLOSING_RE.finditer(line):
            tag = match.group(1).lower()
            issues.append((tag, line_num, "self-closing"))

        for match in EMPTY_TAG_RE.finditer(line):
            tag = match.group(1).lower()
            issues.append((tag, line_num, "empty"))

    return issues


async def run_empty_tag_agent(state: ValidationState) -> dict:
    """
    Scans raw HTML for self-closing and empty tags that should have content.
    Returns an AgentFinding with issues found.
    """
    content = state.get("scraped_content")
    if not content:
        finding = AgentFinding(
            agent="empty_tag",
            passed=False,
            score=0.0,
            issues=["Content could not be scraped"],
            recommendations=["Ensure the URL is accessible and returns HTML"],
        )
        return {
            "findings": [finding],
            "agent_statuses": {"empty_tag": "done"},
        }

    raw_html = content.get("raw_html", "")
    if not raw_html:
        finding = AgentFinding(
            agent="empty_tag",
            passed=True,
            score=1.0,
            passed_checks=["Raw HTML not available — skipping empty tag scan"],
        )
        return {
            "findings": [finding],
            "agent_statuses": {"empty_tag": "done"},
        }

    tag_issues = _scan_html(raw_html)

    if not tag_issues:
        finding = AgentFinding(
            agent="empty_tag",
            passed=True,
            score=1.0,
            passed_checks=["No self-closing or empty content tags found"],
        )
    else:
        issue_descriptions = []
        for tag, line_num, issue_type in tag_issues:
            if issue_type == "self-closing":
                issue_descriptions.append(
                    f"Self-closing <{tag}/> at line {line_num} — should have content"
                )
            else:
                issue_descriptions.append(
                    f"Empty <{tag}></{tag}> at line {line_num} — tag exists but has no content"
                )

        score = max(0.0, 1.0 - len(tag_issues) * DEDUCTION_PER_ISSUE)
        score = round(score, 2)

        finding = AgentFinding(
            agent="empty_tag",
            passed=score >= PASS_THRESHOLD,
            score=score,
            passed_checks=[],
            issues=issue_descriptions,
            recommendations=[
                f"Fix {len(tag_issues)} empty/self-closing tag(s) that should contain content"
            ],
        )

    return {
        "findings": [finding],
        "agent_statuses": {"empty_tag": "done"},
    }

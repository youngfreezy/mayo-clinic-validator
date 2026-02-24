"""
Tests for _run_pipeline's astream consumption — verifies the generator
is fully consumed (no GeneratorExit) and events are emitted correctly.

The bug: returning/breaking inside `async for chunk in astream()` causes
Python to throw GeneratorExit into the generator. LangSmith captures
that as an error, producing a 100% error rate on all traces.

The fix: let astream() finish naturally after interrupt() fires.
"""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from pipeline.state import AgentFinding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(agent: str, score: float = 0.9) -> AgentFinding:
    return AgentFinding(
        agent=agent,
        passed=True,
        score=score,
        passed_checks=["check1"],
        issues=[],
        recommendations=[],
    )


def _make_chunks(vid: str):
    """
    Simulates the sequence of ValidationState chunks that astream(stream_mode="values")
    yields during a normal pipeline run ending at interrupt().
    """
    base = {
        "validation_id": vid,
        "url": "https://www.mayoclinic.org/test",
        "status": "running",
        "findings": [],
        "agent_statuses": {},
        "errors": [],
        "routing_decision": None,
        "judge_recommendation": None,
        "overall_score": None,
        "overall_passed": None,
        "skipped_agents": [],
    }

    # 1. After fetch_content
    yield {**base, "status": "running", "scraped_content": {"title": "Test"}}

    # 2. After triage
    yield {
        **base,
        "status": "running",
        "routing_decision": {
            "agents_to_run": ["metadata", "editorial"],
            "agents_skipped": [],
            "content_type": "standard",
            "routing_method": "triage",
        },
    }

    meta_finding = _make_finding("metadata")
    editorial_finding = _make_finding("editorial")

    # 3. After metadata agent
    yield {
        **base,
        "status": "running",
        "findings": [meta_finding],
        "agent_statuses": {"metadata": "done"},
    }

    # 4. After editorial agent
    yield {
        **base,
        "status": "running",
        "findings": [meta_finding, editorial_finding],
        "agent_statuses": {"metadata": "done", "editorial": "done"},
    }

    # 5. After aggregate
    yield {
        **base,
        "status": "running",
        "findings": [meta_finding, editorial_finding],
        "agent_statuses": {"metadata": "done", "editorial": "done"},
        "overall_score": 0.9,
        "overall_passed": True,
    }

    # 6. After judge — sets status to awaiting_human
    yield {
        **base,
        "status": "awaiting_human",
        "findings": [meta_finding, editorial_finding],
        "agent_statuses": {"metadata": "done", "editorial": "done"},
        "overall_score": 0.9,
        "overall_passed": True,
        "judge_recommendation": {
            "recommendation": "approve",
            "confidence": "high",
            "reasoning": "All checks passed",
        },
    }

    # 7. After human_gate_node (interrupt yields state one more time)
    # This is the critical chunk — the old code would have already
    # returned before this was yielded, causing GeneratorExit.
    yield {
        **base,
        "status": "awaiting_human",
        "findings": [meta_finding, editorial_finding],
        "agent_statuses": {"metadata": "done", "editorial": "done"},
        "overall_score": 0.9,
        "overall_passed": True,
        "judge_recommendation": {
            "recommendation": "approve",
            "confidence": "high",
            "reasoning": "All checks passed",
        },
    }


class MockAsyncStream:
    """
    Wraps a sync generator to simulate astream(). Tracks whether
    GeneratorExit was thrown (the bug we're testing against).
    """

    def __init__(self, chunks_gen):
        self._chunks = list(chunks_gen)
        self._index = 0
        self.generator_exit_thrown = False
        self.fully_consumed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._chunks):
            self.fully_consumed = True
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk

    async def aclose(self):
        if not self.fully_consumed:
            self.generator_exit_thrown = True

    async def athrow(self, *args):
        self.generator_exit_thrown = True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_pipeline_no_generator_exit():
    """
    _run_pipeline must consume the entire astream() generator without
    causing GeneratorExit. This is what fixes the 100% LangSmith error rate.
    """
    vid = "11111111-1111-1111-1111-111111111111"
    mock_stream = MockAsyncStream(_make_chunks(vid))
    q = asyncio.Queue()

    initial_state = {
        "validation_id": vid,
        "url": "https://www.mayoclinic.org/test",
        "requested_by": "test-user",
    }

    mock_graph = MagicMock()
    mock_graph.astream = MagicMock(return_value=mock_stream)

    with (
        patch("main.validation_graph", mock_graph),
        patch("main.db") as mock_db,
        patch("main._build_trace_url", return_value=None),
    ):
        mock_db.upsert_validation = AsyncMock()

        from main import _run_pipeline, validation_store, sse_queues, emitted_agents
        sse_queues[vid] = q

        await _run_pipeline(vid, initial_state, q)

    # The generator must be fully consumed — no GeneratorExit
    assert mock_stream.fully_consumed, "astream() generator was not fully consumed"
    assert not mock_stream.generator_exit_thrown, (
        "GeneratorExit was thrown into astream() — this causes 100% LangSmith error rate"
    )


@pytest.mark.asyncio
async def test_run_pipeline_hitl_emitted_once():
    """
    The HITL event must be emitted exactly once, even when multiple chunks
    have status='awaiting_human'.
    """
    vid = "22222222-2222-2222-2222-222222222222"
    mock_stream = MockAsyncStream(_make_chunks(vid))
    q = asyncio.Queue()

    initial_state = {
        "validation_id": vid,
        "url": "https://www.mayoclinic.org/test",
        "requested_by": "test-user",
    }

    mock_graph = MagicMock()
    mock_graph.astream = MagicMock(return_value=mock_stream)

    with (
        patch("main.validation_graph", mock_graph),
        patch("main.db") as mock_db,
        patch("main._build_trace_url", return_value=None),
    ):
        mock_db.upsert_validation = AsyncMock()

        from main import _run_pipeline, sse_queues, emitted_agents
        sse_queues[vid] = q

        await _run_pipeline(vid, initial_state, q)

    # Drain the queue and count HITL events
    events = []
    while not q.empty():
        events.append(await q.get())

    hitl_events = [e for e in events if e["type"] == "hitl"]
    assert len(hitl_events) == 1, f"Expected exactly 1 HITL event, got {len(hitl_events)}"

    # Verify HITL event contains expected data
    hitl = hitl_events[0]
    assert hitl["data"]["validation_id"] == vid
    assert hitl["data"]["overall_score"] == 0.9
    assert hitl["data"]["overall_passed"] is True
    assert hitl["data"]["judge_recommendation"]["recommendation"] == "approve"


@pytest.mark.asyncio
async def test_run_pipeline_agent_events_emitted():
    """All agent_complete events should be emitted."""
    vid = "33333333-3333-3333-3333-333333333333"
    mock_stream = MockAsyncStream(_make_chunks(vid))
    q = asyncio.Queue()

    initial_state = {
        "validation_id": vid,
        "url": "https://www.mayoclinic.org/test",
        "requested_by": "test-user",
    }

    mock_graph = MagicMock()
    mock_graph.astream = MagicMock(return_value=mock_stream)

    with (
        patch("main.validation_graph", mock_graph),
        patch("main.db") as mock_db,
        patch("main._build_trace_url", return_value=None),
    ):
        mock_db.upsert_validation = AsyncMock()

        from main import _run_pipeline, sse_queues, emitted_agents
        sse_queues[vid] = q

        await _run_pipeline(vid, initial_state, q)

    events = []
    while not q.empty():
        events.append(await q.get())

    agent_events = [e for e in events if e["type"] == "agent_complete"]
    agent_names = {e["data"]["agent"] for e in agent_events}
    assert "metadata" in agent_names
    assert "editorial" in agent_names


@pytest.mark.asyncio
async def test_run_pipeline_handles_graph_interrupt():
    """
    If astream() raises GraphInterrupt instead of ending cleanly,
    _run_pipeline should handle it gracefully and still emit HITL.
    """
    from langgraph.errors import GraphInterrupt

    vid = "44444444-4444-4444-4444-444444444444"
    q = asyncio.Queue()

    initial_state = {
        "validation_id": vid,
        "url": "https://www.mayoclinic.org/test",
        "requested_by": "test-user",
    }

    # Simulate astream that yields judge chunk then raises GraphInterrupt
    judge_chunk = {
        "validation_id": vid,
        "url": "https://www.mayoclinic.org/test",
        "status": "awaiting_human",
        "findings": [_make_finding("metadata")],
        "agent_statuses": {"metadata": "done"},
        "errors": [],
        "routing_decision": None,
        "overall_score": 0.85,
        "overall_passed": True,
        "skipped_agents": [],
        "judge_recommendation": {
            "recommendation": "approve",
            "confidence": "high",
            "reasoning": "Looks good",
        },
    }

    async def interrupted_stream(*args, **kwargs):
        yield judge_chunk
        raise GraphInterrupt("Interrupted at human_gate_node")

    mock_graph = MagicMock()
    mock_graph.astream = interrupted_stream

    with (
        patch("main.validation_graph", mock_graph),
        patch("main.db") as mock_db,
        patch("main._build_trace_url", return_value=None),
    ):
        mock_db.upsert_validation = AsyncMock()

        from main import _run_pipeline, validation_store, sse_queues, emitted_agents
        sse_queues[vid] = q
        validation_store[vid] = judge_chunk

        await _run_pipeline(vid, initial_state, q)

    # Should NOT have emitted an error event
    events = []
    while not q.empty():
        events.append(await q.get())

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 0, f"GraphInterrupt should not produce error events: {error_events}"

    # Should have emitted HITL event
    hitl_events = [e for e in events if e["type"] == "hitl"]
    assert len(hitl_events) == 1, "HITL event should be emitted even when GraphInterrupt is raised"


@pytest.mark.asyncio
async def test_run_pipeline_no_done_on_hitl():
    """
    When pipeline pauses for HITL, no 'done' event should be emitted.
    The SSE stream must stay open for the resume.
    """
    vid = "55555555-5555-5555-5555-555555555555"
    mock_stream = MockAsyncStream(_make_chunks(vid))
    q = asyncio.Queue()

    initial_state = {
        "validation_id": vid,
        "url": "https://www.mayoclinic.org/test",
        "requested_by": "test-user",
    }

    mock_graph = MagicMock()
    mock_graph.astream = MagicMock(return_value=mock_stream)

    with (
        patch("main.validation_graph", mock_graph),
        patch("main.db") as mock_db,
        patch("main._build_trace_url", return_value=None),
    ):
        mock_db.upsert_validation = AsyncMock()

        from main import _run_pipeline, sse_queues, emitted_agents
        sse_queues[vid] = q

        await _run_pipeline(vid, initial_state, q)

    events = []
    while not q.empty():
        events.append(await q.get())

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 0, (
        f"No 'done' event should be emitted when awaiting HITL, got: {done_events}"
    )

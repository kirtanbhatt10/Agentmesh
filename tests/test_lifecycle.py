"""Tests for task states, transitions and payload helpers."""

from datetime import datetime, timezone

import pytest

from agentmesh import lifecycle as lc
from agentmesh import load_schema, validate_task

TERMINAL = ["rejected", "completed", "failed", "timed_out"]


def test_states_match_the_task_schema():
    assert set(lc.STATES) == set(load_schema("task")["properties"]["status"]["enum"])
    assert set(lc.TRANSITIONS) == set(lc.STATES)


@pytest.mark.parametrize(
    "current,new",
    [
        ("submitted", "accepted"),
        ("submitted", "rejected"),
        ("accepted", "executing"),
        ("accepted", "timed_out"),
        ("executing", "executing"),
        ("executing", "completed"),
        ("executing", "failed"),
        ("executing", "timed_out"),
    ],
)
def test_allowed_transitions(current, new):
    assert lc.can_transition(current, new)


@pytest.mark.parametrize(
    "current,new",
    [
        ("submitted", "executing"),
        ("submitted", "completed"),
        ("accepted", "completed"),
        ("accepted", "rejected"),
        ("executing", "accepted"),
    ],
)
def test_forbidden_transitions(current, new):
    assert not lc.can_transition(current, new)


@pytest.mark.parametrize("state", TERMINAL)
def test_terminal_states_have_no_exits(state):
    assert lc.is_terminal(state)
    assert not any(lc.can_transition(state, other) for other in lc.STATES)


@pytest.mark.parametrize("state", ["submitted", "accepted", "executing"])
def test_non_terminal_states(state):
    assert not lc.is_terminal(state)


def test_unknown_status_raises():
    with pytest.raises(ValueError):
        lc.can_transition("done", "completed")
    with pytest.raises(ValueError):
        lc.can_transition("submitted", "done")


def test_new_task_generates_ids_and_is_valid():
    task = lc.new_task("web-research", {"query": "x"}, constraints={"timeout_seconds": 5})
    assert task["task_id"].startswith("task-")
    assert task["conversation_id"].startswith("conv-")
    assert task["status"] == "submitted"
    assert validate_task(task) == []
    other = lc.new_task("web-research")
    assert other["task_id"] != task["task_id"]
    assert other["context"] == {}


def test_new_task_keeps_given_ids():
    task = lc.new_task("x", task_id="t-1", conversation_id="c-1")
    assert (task["task_id"], task["conversation_id"]) == ("t-1", "c-1")


def test_new_task_rejects_invalid_input():
    with pytest.raises(lc.InvalidTaskPayload) as exc:
        lc.new_task("")
    assert exc.value.problems[0].path == "$.capability"


def test_transition_walks_the_happy_path_without_mutating_input():
    task = lc.new_task("x", {"a": 1})
    accepted = lc.transition(task, "accepted")
    executing = lc.transition(accepted, "executing")
    done = lc.transition(
        executing, "completed", result={"data": {"ok": True}}, usage={"model": "m"}
    )
    assert task["status"] == "submitted"
    assert done["status"] == "completed"
    assert done["result"] == {"data": {"ok": True}}
    assert done["usage"] == {"model": "m"}
    assert validate_task(done) == []


def test_transition_without_status_counts_as_submitted():
    task = {"task_id": "t", "conversation_id": "c", "capability": "x", "context": {}}
    assert lc.transition(task, "accepted")["status"] == "accepted"


def test_invalid_transition_raises():
    task = lc.new_task("x")
    with pytest.raises(lc.InvalidTransition):
        lc.transition(task, "completed", result={"data": {}})


def test_transition_enforces_schema_rules():
    executing = lc.transition(lc.transition(lc.new_task("x"), "accepted"), "executing")
    with pytest.raises(lc.InvalidTaskPayload):
        lc.transition(executing, "completed")
    with pytest.raises(lc.InvalidTaskPayload):
        lc.transition(executing, "failed")
    failed = lc.transition(executing, "failed", error=lc.make_error("boom", "it broke"))
    assert failed["error"] == {"code": "boom", "message": "it broke"}


def test_make_error_includes_retryable_only_when_given():
    assert lc.make_error("c", "m") == {"code": "c", "message": "m"}
    assert lc.make_error("c", "m", retryable=True)["retryable"] is True


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2026-11-01T12:00:00Z", datetime(2026, 11, 1, 12, tzinfo=timezone.utc)),
        ("2026-11-01T12:00:00z", datetime(2026, 11, 1, 12, tzinfo=timezone.utc)),
        ("2026-11-01T17:30:00+05:30", datetime(2026, 11, 1, 12, tzinfo=timezone.utc)),
        ("2026-11-01T12:00:00", datetime(2026, 11, 1, 12, tzinfo=timezone.utc)),
    ],
)
def test_parse_deadline(text, expected):
    assert lc.parse_deadline(text) == expected


@pytest.mark.parametrize("text", ["", "tomorrow", "2026-13-01T00:00:00Z", None])
def test_parse_deadline_rejects_garbage(text):
    with pytest.raises(ValueError):
        lc.parse_deadline(text)

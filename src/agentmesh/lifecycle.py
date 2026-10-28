"""Task lifecycle: states, allowed transitions and helpers for building task payloads.

The states and transitions follow the proposed lifecycle in ``docs/task-lifecycle.md``::

    submitted -> accepted | rejected
    accepted  -> executing | timed_out (deadline passed while queued)
    executing -> executing (retry) | completed | failed | timed_out

``rejected``, ``completed``, ``failed`` and ``timed_out`` are terminal.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from agentmesh.validation import SchemaError, validate_task

SUBMITTED = "submitted"
ACCEPTED = "accepted"
REJECTED = "rejected"
EXECUTING = "executing"
COMPLETED = "completed"
FAILED = "failed"
TIMED_OUT = "timed_out"

STATES = (SUBMITTED, ACCEPTED, REJECTED, EXECUTING, COMPLETED, FAILED, TIMED_OUT)
TERMINAL_STATES = frozenset({REJECTED, COMPLETED, FAILED, TIMED_OUT})

TRANSITIONS: dict[str, frozenset[str]] = {
    SUBMITTED: frozenset({ACCEPTED, REJECTED}),
    ACCEPTED: frozenset({EXECUTING, TIMED_OUT}),
    EXECUTING: frozenset({EXECUTING, COMPLETED, FAILED, TIMED_OUT}),
    REJECTED: frozenset(),
    COMPLETED: frozenset(),
    FAILED: frozenset(),
    TIMED_OUT: frozenset(),
}


class ErrorCode:
    """Error codes used by the reference implementation.

    The protocol's error-code taxonomy is still an open Phase 1 question; these codes are
    what the bundled agent, registry and client emit today.
    """

    INVALID_PAYLOAD = "invalid_payload"
    UNKNOWN_CAPABILITY = "unknown_capability"
    UNSUPPORTED_CONSTRAINT = "unsupported_constraint"
    DUPLICATE_TASK = "duplicate_task"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    RESULT_TOO_LARGE = "result_too_large"
    INVALID_RESULT = "invalid_result"
    HANDLER_ERROR = "handler_error"
    NOT_FOUND = "not_found"


class InvalidTransition(ValueError):
    """Raised when a task is moved to a state its current state does not allow."""


class InvalidTaskPayload(ValueError):
    """Raised when a task payload does not match the task schema."""

    def __init__(self, problems: list[SchemaError]):
        self.problems = problems
        super().__init__("; ".join(str(p) for p in problems))


def is_terminal(status: str) -> bool:
    """Return True if ``status`` is a terminal task state."""
    return status in TERMINAL_STATES


def can_transition(current: str, new: str) -> bool:
    """Return True if a task may move from ``current`` to ``new``."""
    if current not in TRANSITIONS:
        raise ValueError(f"unknown task status {current!r}")
    if new not in TRANSITIONS:
        raise ValueError(f"unknown task status {new!r}")
    return new in TRANSITIONS[current]


def new_id(prefix: str) -> str:
    """Return a random identifier such as ``task-3f2a...``."""
    return f"{prefix}-{uuid.uuid4().hex}"


def new_task(
    capability: str,
    context: dict[str, Any] | None = None,
    *,
    conversation_id: str | None = None,
    task_id: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a validated task payload in the ``submitted`` state.

    ``task_id`` and ``conversation_id`` are generated when omitted. Reuse the same
    ``conversation_id`` for every task that belongs to one workflow.
    """
    task: dict[str, Any] = {
        "task_id": task_id or new_id("task"),
        "conversation_id": conversation_id or new_id("conv"),
        "capability": capability,
        "context": dict(context or {}),
        "status": SUBMITTED,
    }
    if constraints:
        task["constraints"] = dict(constraints)
    ensure_valid_task(task)
    return task


def ensure_valid_task(task: Any) -> None:
    """Raise :class:`InvalidTaskPayload` if ``task`` does not match the task schema."""
    problems = validate_task(task)
    if problems:
        raise InvalidTaskPayload(problems)


def transition(
    task: dict[str, Any],
    status: str,
    *,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a copy of ``task`` moved to ``status``; the input is not modified.

    A task without a ``status`` is treated as ``submitted``. Raises
    :class:`InvalidTransition` if the move is not allowed and :class:`InvalidTaskPayload`
    if the resulting payload is not schema-valid (for example ``completed`` without a
    ``result``).
    """
    current = task.get("status", SUBMITTED)
    if not can_transition(current, status):
        raise InvalidTransition(f"cannot move task from {current!r} to {status!r}")
    updated = copy.deepcopy(task)
    updated["status"] = status
    if result is not None:
        updated["result"] = copy.deepcopy(result)
    if error is not None:
        updated["error"] = copy.deepcopy(error)
    if usage is not None:
        updated["usage"] = copy.deepcopy(usage)
    ensure_valid_task(updated)
    return updated


def make_error(code: str, message: str, *, retryable: bool | None = None) -> dict[str, Any]:
    """Build a task ``error`` object."""
    error: dict[str, Any] = {"code": code, "message": message}
    if retryable is not None:
        error["retryable"] = retryable
    return error


def parse_deadline(value: str) -> datetime:
    """Parse an ISO 8601 ``deadline`` constraint into an aware UTC datetime.

    A trailing ``Z`` is accepted on every supported Python version; a timestamp without
    an offset is interpreted as UTC. Raises ``ValueError`` for anything else.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("deadline must be a non-empty ISO 8601 string")
    text = value[:-1] + "+00:00" if value[-1] in "Zz" else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

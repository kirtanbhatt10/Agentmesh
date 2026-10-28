"""Reference AgentMesh agent: serves a manifest and runs delegated tasks asynchronously.

Example::

    from agentmesh import Agent

    agent = Agent("echo", description="Repeats what it is given.")

    @agent.capability("echo", description="Return the context unchanged.")
    def echo(context, info):
        return {"echo": context}

    server = agent.serve(port=8001)   # GET /manifest, POST /tasks, GET /tasks/{task_id}
"""

from __future__ import annotations

import copy
import inspect
import json
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

from agentmesh import lifecycle as lc
from agentmesh._http import HTTPError, Request, Response, Router, RunningServer
from agentmesh.validation import validate_manifest, validate_task

logger = logging.getLogger("agentmesh.agent")

_SUBMISSION_ONLY_FIELDS = ("result", "error", "usage")


@dataclass
class TaskResult:
    """What a capability handler returns: result ``data`` plus optional summary and usage."""

    data: dict[str, Any]
    summary: str | None = None
    usage: dict[str, Any] | None = None


class TaskFailure(Exception):
    """Raise from a handler to fail a task with a structured protocol error.

    Set ``retryable=True`` for transient problems: the agent retries the task within its
    ``max_retries`` budget before reporting the failure.
    """

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class TaskInfo:
    """Read-only facts about the task a handler is executing."""

    task_id: str
    conversation_id: str
    capability: str
    constraints: dict[str, Any]
    deadline: datetime | None
    attempt: int


Handler = Callable[..., Any]


@dataclass
class Capability:
    capability_id: str
    handler: Handler
    description: str | None = None
    input_hint: str | None = None
    output_hint: str | None = None
    output_formats: frozenset[str] = field(default_factory=lambda: frozenset({"json"}))
    _wants_info: bool = True

    def to_manifest(self) -> dict[str, Any]:
        entry: dict[str, Any] = {"capability_id": self.capability_id}
        for key in ("description", "input_hint", "output_hint"):
            value = getattr(self, key)
            if value is not None:
                entry[key] = value
        return entry


@dataclass
class _Record:
    task: dict[str, Any]
    submitted: dict[str, Any]
    deadline: datetime | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _accepts_info(func: Handler) -> bool:
    try:
        params = list(inspect.signature(func).parameters.values())
    except (TypeError, ValueError):
        return True
    positional = [
        p
        for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params)
    return has_varargs or len(positional) >= 2


class Agent:
    """An AgentMesh agent with capabilities, an in-memory task store and an HTTP API.

    Handlers are called as ``handler(context, info)`` (or ``handler(context)``) on a worker
    thread and return a ``dict`` (the result data) or a :class:`TaskResult`. Raise
    :class:`TaskFailure` for a structured failure; any other exception fails the task with
    code ``handler_error``.
    """

    def __init__(
        self,
        name: str,
        *,
        version: str = "0.1.0",
        description: str | None = None,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        max_retries: int = 0,
        retry_delay: float = 0.0,
        max_workers: int = 4,
        max_tasks: int = 10_000,
    ):
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if max_tasks < 1:
            raise ValueError("max_tasks must be >= 1")
        self.name = name
        self.version = version
        self.description = description
        self.agent_id = agent_id or f"urn:agentmesh:{name}"
        self.metadata = metadata
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_tasks = max_tasks
        self.base_url: str | None = None
        self._capabilities: dict[str, Capability] = {}
        self._tasks: OrderedDict[str, _Record] = OrderedDict()
        self._lock = threading.RLock()
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None

    # -- capabilities and manifest -------------------------------------------------------

    def capability(
        self,
        capability_id: str,
        *,
        description: str | None = None,
        input_hint: str | None = None,
        output_hint: str | None = None,
        output_formats: tuple[str, ...] | list[str] = ("json",),
    ) -> Callable[[Handler], Handler]:
        """Decorator registering ``handler`` for ``capability_id``."""

        def register(handler: Handler) -> Handler:
            self.add_capability(
                capability_id,
                handler,
                description=description,
                input_hint=input_hint,
                output_hint=output_hint,
                output_formats=output_formats,
            )
            return handler

        return register

    def add_capability(
        self,
        capability_id: str,
        handler: Handler,
        *,
        description: str | None = None,
        input_hint: str | None = None,
        output_hint: str | None = None,
        output_formats: tuple[str, ...] | list[str] = ("json",),
    ) -> None:
        """Register ``handler`` for ``capability_id`` (see :meth:`capability`)."""
        if not capability_id:
            raise ValueError("capability_id must be a non-empty string")
        if capability_id in self._capabilities:
            raise ValueError(f"capability {capability_id!r} is already registered")
        if not callable(handler):
            raise TypeError("handler must be callable")
        self._capabilities[capability_id] = Capability(
            capability_id=capability_id,
            handler=handler,
            description=description,
            input_hint=input_hint,
            output_hint=output_hint,
            output_formats=frozenset(output_formats),
            _wants_info=_accepts_info(handler),
        )

    @property
    def capabilities(self) -> list[str]:
        return list(self._capabilities)

    def manifest(self, base_url: str | None = None) -> dict[str, Any]:
        """Return this agent's manifest, validated against the manifest schema."""
        url = (base_url or self.base_url or "").rstrip("/")
        if not url:
            raise ValueError("base_url is unknown until the agent is served; pass one explicitly")
        if not self._capabilities:
            raise ValueError("an agent needs at least one capability")
        manifest: dict[str, Any] = {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "capabilities": [c.to_manifest() for c in self._capabilities.values()],
            "endpoints": {
                "base_url": url,
                "manifest": f"{url}/manifest",
                "tasks": f"{url}/tasks",
            },
        }
        if self.description is not None:
            manifest["description"] = self.description
        if self.metadata is not None:
            manifest["metadata"] = copy.deepcopy(self.metadata)
        problems = validate_manifest(manifest)
        if problems:
            raise ValueError("invalid manifest: " + "; ".join(str(p) for p in problems))
        return manifest

    # -- task API (transport independent) -----------------------------------------------

    def submit(self, payload: Any) -> tuple[int, dict[str, Any]]:
        """Accept or reject a task submission; return ``(http_status, task)``.

        Raises :class:`agentmesh._http.HTTPError` for malformed submissions and duplicate
        task IDs with a different payload.
        """
        problems = validate_task(payload)
        if problems:
            raise HTTPError(
                HTTPStatus.BAD_REQUEST,
                lc.ErrorCode.INVALID_PAYLOAD,
                "task payload does not match the task schema",
                [str(p) for p in problems],
            )
        status = payload.get("status", lc.SUBMITTED)
        if status != lc.SUBMITTED:
            raise HTTPError(
                HTTPStatus.BAD_REQUEST,
                lc.ErrorCode.INVALID_PAYLOAD,
                f"new tasks must have status 'submitted' (or none), not {status!r}",
            )
        present = [k for k in _SUBMISSION_ONLY_FIELDS if k in payload]
        if present:
            raise HTTPError(
                HTTPStatus.BAD_REQUEST,
                lc.ErrorCode.INVALID_PAYLOAD,
                f"a submitted task must not include {', '.join(present)}",
            )

        submitted = copy.deepcopy(payload)
        submitted["status"] = lc.SUBMITTED
        task_id = submitted["task_id"]

        with self._lock:
            existing = self._tasks.get(task_id)
            if existing is not None:
                if existing.submitted == submitted:
                    return HTTPStatus.OK, self._refresh(existing)
                raise HTTPError(
                    HTTPStatus.CONFLICT,
                    lc.ErrorCode.DUPLICATE_TASK,
                    f"task {task_id!r} was already submitted with a different payload",
                )

            rejection = self._check_acceptance(submitted)
            if rejection is not None:
                task = lc.transition(submitted, lc.REJECTED, error=rejection)
                self._store(_Record(task=task, submitted=submitted))
                return HTTPStatus.OK, copy.deepcopy(task)

            deadline = self._deadline_for(submitted)
            task = lc.transition(submitted, lc.ACCEPTED)
            self._store(_Record(task=task, submitted=submitted, deadline=deadline))
            self._ensure_executor().submit(self._run, task_id)
            return HTTPStatus.ACCEPTED, copy.deepcopy(task)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Return the current state of ``task_id`` (``None`` if unknown)."""
        with self._lock:
            record = self._tasks.get(task_id)
            return None if record is None else self._refresh(record)

    def list_tasks(self, conversation_id: str | None = None) -> list[dict[str, Any]]:
        """Return all known tasks, optionally only those in one conversation."""
        with self._lock:
            return [
                self._refresh(r)
                for r in list(self._tasks.values())
                if conversation_id is None or r.task["conversation_id"] == conversation_id
            ]

    # -- HTTP ------------------------------------------------------------------------------

    def router(self) -> Router:
        router = Router()
        router.add("GET", "/manifest", lambda req: Response(HTTPStatus.OK, self.manifest()))
        router.add("GET", "/healthz", lambda req: Response(HTTPStatus.OK, self._health()))
        router.add("POST", "/tasks", self._post_task)
        router.add("GET", "/tasks", self._list_tasks_route)
        router.add("GET", "/tasks/{task_id}", self._get_task_route)
        return router

    def serve(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        *,
        public_url: str | None = None,
        registry_url: str | None = None,
        registry_interval: float | None = 30.0,
    ) -> RunningServer:
        """Start the HTTP API in a background thread and return the running server.

        ``port=0`` picks a free port. ``public_url`` overrides the base URL advertised in
        the manifest (useful behind a proxy or in a container network).

        With ``registry_url`` the manifest is registered on start, re-registered every
        ``registry_interval`` seconds (so a restarted registry repopulates itself; ``None``
        disables this) and removed when the server closes. If the first registration
        fails the server is closed and the error is raised.
        """
        if not self._capabilities:
            raise ValueError("an agent needs at least one capability before it can serve")
        if registry_interval is not None and registry_interval <= 0:
            raise ValueError("registry_interval must be positive or None")
        server = RunningServer(self.router(), host, port)
        self.base_url = (public_url or server.url).rstrip("/")
        server.on_close(self.close)
        server.start()
        if registry_url:
            try:
                self._join_registry(server, registry_url, registry_interval)
            except BaseException:
                server.close()
                raise
        logger.info("agent %s serving at %s", self.name, self.base_url)
        return server

    def _join_registry(
        self, server: RunningServer, registry_url: str, interval: float | None
    ) -> None:
        from agentmesh.client import RegistryClient

        registry = RegistryClient(registry_url)
        registry.register(self.manifest())
        stop = threading.Event()
        membership = threading.Lock()  # a late heartbeat must not undo leave()

        def heartbeat() -> None:
            while not stop.wait(interval):
                with membership:
                    if stop.is_set():
                        return
                    try:
                        registry.register(self.manifest())
                    except Exception as exc:  # the registry is advisory; keep serving
                        logger.warning("re-registering with %s failed: %s", registry_url, exc)

        if interval is not None:
            threading.Thread(
                target=heartbeat, name=f"agentmesh-{self.name}-heartbeat", daemon=True
            ).start()

        def leave() -> None:
            with membership:
                stop.set()
                try:
                    registry.unregister(self.agent_id)
                except Exception:  # best effort: the registry is advisory
                    logger.warning("could not unregister %s from %s", self.agent_id, registry_url)

        server.on_close(leave)

    def close(self) -> None:
        """Stop the worker pool. Tasks still running finish in the background."""
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    # -- internals -------------------------------------------------------------------------

    def _health(self) -> dict[str, Any]:
        with self._lock:
            active = sum(1 for r in self._tasks.values() if not lc.is_terminal(r.task["status"]))
        return {"status": "ok", "agent_id": self.agent_id, "active_tasks": active}

    def _post_task(self, req: Request) -> Response:
        status, task = self.submit(req.body)
        return Response(status, task)

    def _get_task_route(self, req: Request) -> Response:
        task = self.get_task(req.params["task_id"])
        if task is None:
            raise HTTPError(HTTPStatus.NOT_FOUND, lc.ErrorCode.NOT_FOUND, "unknown task_id")
        return Response(HTTPStatus.OK, task)

    def _list_tasks_route(self, req: Request) -> Response:
        tasks = self.list_tasks(req.query.get("conversation_id"))
        return Response(HTTPStatus.OK, {"tasks": tasks})

    def _ensure_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers, thread_name_prefix=f"agentmesh-{self.name}"
            )
        return self._executor

    def _store(self, record: _Record) -> None:
        self._tasks[record.task["task_id"]] = record
        if len(self._tasks) > self.max_tasks:
            for task_id in list(self._tasks):
                if len(self._tasks) <= self.max_tasks:
                    break
                if lc.is_terminal(self._tasks[task_id].task["status"]):
                    del self._tasks[task_id]

    def _check_acceptance(self, task: dict[str, Any]) -> dict[str, Any] | None:
        capability = self._capabilities.get(task["capability"])
        if capability is None:
            return lc.make_error(
                lc.ErrorCode.UNKNOWN_CAPABILITY,
                f"this agent does not offer capability {task['capability']!r}; "
                f"available: {', '.join(self._capabilities)}",
                retryable=False,
            )
        constraints = task.get("constraints", {})
        fmt = constraints.get("output_format")
        if fmt is not None and fmt not in capability.output_formats:
            return lc.make_error(
                lc.ErrorCode.UNSUPPORTED_CONSTRAINT,
                f"output_format {fmt!r} is not supported; "
                f"supported: {', '.join(sorted(capability.output_formats))}",
                retryable=False,
            )
        if "deadline" in constraints:
            try:
                deadline = lc.parse_deadline(constraints["deadline"])
            except ValueError:
                return lc.make_error(
                    lc.ErrorCode.UNSUPPORTED_CONSTRAINT,
                    "deadline is not a valid ISO 8601 date-time",
                    retryable=False,
                )
            if deadline <= _now():
                return lc.make_error(
                    lc.ErrorCode.DEADLINE_EXCEEDED,
                    "the deadline had already passed when the task was submitted",
                    retryable=False,
                )
        return None

    def _deadline_for(self, task: dict[str, Any]) -> datetime | None:
        constraints = task.get("constraints", {})
        candidates = []
        if "deadline" in constraints:
            candidates.append(lc.parse_deadline(constraints["deadline"]))
        if "timeout_seconds" in constraints:
            candidates.append(_now() + timedelta(seconds=constraints["timeout_seconds"]))
        return min(candidates) if candidates else None

    def _refresh(self, record: _Record) -> dict[str, Any]:
        """Apply a lazily detected timeout, then return a copy of the task. Lock held."""
        status = record.task["status"]
        if (
            record.deadline is not None
            and status in (lc.ACCEPTED, lc.EXECUTING)
            and _now() >= record.deadline
        ):
            record.task = lc.transition(record.task, lc.TIMED_OUT, error=_timeout_error())
        return copy.deepcopy(record.task)

    def _update(self, task_id: str, status: str, **fields: Any) -> bool:
        """Move a task to ``status`` unless it already reached a terminal state."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return False
            self._refresh(record)
            if lc.is_terminal(record.task["status"]):
                return False
            record.task = lc.transition(record.task, status, **fields)
            return True

    def _deadline_passed(self, task_id: str) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
            return bool(record and record.deadline and _now() >= record.deadline)

    def _run(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            submitted = copy.deepcopy(record.submitted)
            deadline = record.deadline
        if not self._update(task_id, lc.EXECUTING):
            return
        capability = self._capabilities[submitted["capability"]]
        constraints = submitted.get("constraints", {})

        attempt = 0
        while True:
            attempt += 1
            if self._deadline_passed(task_id):
                self._update(task_id, lc.TIMED_OUT, error=_timeout_error())
                return
            info = TaskInfo(
                task_id=task_id,
                conversation_id=submitted["conversation_id"],
                capability=submitted["capability"],
                constraints=copy.deepcopy(constraints),
                deadline=deadline,
                attempt=attempt,
            )
            context = copy.deepcopy(submitted["context"])
            started = time.monotonic()
            try:
                if capability._wants_info:
                    outcome = capability.handler(context, info)
                else:
                    outcome = capability.handler(context)
            except TaskFailure as failure:
                if failure.retryable and attempt <= self.max_retries:
                    logger.info("task %s attempt %d failed, retrying", task_id, attempt)
                    if not self._update(task_id, lc.EXECUTING):
                        return
                    if self.retry_delay:
                        time.sleep(self.retry_delay)
                    continue
                error = lc.make_error(failure.code, failure.message, retryable=failure.retryable)
                self._update(task_id, lc.FAILED, error=error)
                return
            except Exception as exc:
                logger.exception("handler for %s raised", submitted["capability"])
                error = lc.make_error(
                    lc.ErrorCode.HANDLER_ERROR,
                    f"{type(exc).__name__}: {exc}",
                    retryable=False,
                )
                self._update(task_id, lc.FAILED, error=error)
                return
            break

        if self._deadline_passed(task_id):
            self._update(task_id, lc.TIMED_OUT, error=_timeout_error())
            return
        self._finish(task_id, outcome, constraints, int((time.monotonic() - started) * 1000))

    def _finish(
        self, task_id: str, outcome: Any, constraints: dict[str, Any], duration_ms: int
    ) -> None:
        if isinstance(outcome, TaskResult):
            data, summary, usage = outcome.data, outcome.summary, outcome.usage
        else:
            data, summary, usage = outcome, None, None
        if not isinstance(data, dict):
            error = lc.make_error(
                lc.ErrorCode.INVALID_RESULT,
                f"handler returned {type(data).__name__}; result data must be a JSON object",
                retryable=False,
            )
            self._update(task_id, lc.FAILED, error=error)
            return
        result: dict[str, Any] = {"data": data}
        if summary is not None:
            result["summary"] = summary
        usage = dict(usage or {})
        usage.setdefault("duration_ms", duration_ms)

        try:
            size = len(json.dumps(result).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            error = lc.make_error(
                lc.ErrorCode.INVALID_RESULT,
                f"result is not JSON-serialisable: {exc}",
                retryable=False,
            )
            self._update(task_id, lc.FAILED, error=error)
            return
        limit = constraints.get("max_result_bytes")
        if limit is not None and size > limit:
            error = lc.make_error(
                lc.ErrorCode.RESULT_TOO_LARGE,
                f"result is {size} bytes; max_result_bytes is {limit}",
                retryable=False,
            )
            self._update(task_id, lc.FAILED, error=error)
            return
        try:
            self._update(task_id, lc.COMPLETED, result=result, usage=usage)
        except lc.InvalidTaskPayload as exc:
            error = lc.make_error(
                lc.ErrorCode.INVALID_RESULT,
                f"result does not match the task schema: {exc}",
                retryable=False,
            )
            self._update(task_id, lc.FAILED, error=error)


def _timeout_error() -> dict[str, Any]:
    return lc.make_error(
        lc.ErrorCode.DEADLINE_EXCEEDED,
        "the task did not finish before its deadline",
        retryable=True,
    )

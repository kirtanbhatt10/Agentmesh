"""HTTP clients for AgentMesh agents and registries (standard library only)."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote, urlencode

from agentmesh import lifecycle as lc
from agentmesh._http import AgentMeshHTTPError, request_json
from agentmesh.validation import validate_manifest, validate_task

__all__ = ["AgentClient", "AgentMeshHTTPError", "ProtocolError", "RegistryClient", "TaskTimeout"]


class ProtocolError(Exception):
    """A service answered with a payload that does not match the AgentMesh schemas."""


class TaskTimeout(TimeoutError):
    """Waiting for a task to reach a terminal state took longer than allowed."""

    def __init__(self, task: dict[str, Any], waited: float):
        self.task = task
        super().__init__(
            f"task {task.get('task_id')!r} still {task.get('status')!r} after {waited:.1f}s"
        )


def _check_task(task: Any, url: str) -> dict[str, Any]:
    problems = validate_task(task)
    if problems:
        raise ProtocolError(f"{url} returned an invalid task: " + "; ".join(map(str, problems)))
    return task


def _check_manifest(manifest: Any, url: str) -> dict[str, Any]:
    problems = validate_manifest(manifest)
    if problems:
        raise ProtocolError(f"{url} returned an invalid manifest: " + "; ".join(map(str, problems)))
    return manifest


class AgentClient:
    """Talks to one agent: fetch its manifest, submit tasks and poll for outcomes."""

    def __init__(self, base_url: str, *, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any], *, timeout: float = 10.0) -> AgentClient:
        """Build a client for the agent described by ``manifest``."""
        return cls(manifest["endpoints"]["base_url"], timeout=timeout)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def manifest(self) -> dict[str, Any]:
        """``GET /manifest``, validated against the manifest schema."""
        url = self._url("/manifest")
        _, body = request_json("GET", url, timeout=self.timeout)
        return _check_manifest(body, url)

    def health(self) -> dict[str, Any]:
        _, body = request_json("GET", self._url("/healthz"), timeout=self.timeout)
        return body

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        """``POST /tasks``; return the task as accepted or rejected by the agent."""
        url = self._url("/tasks")
        _, body = request_json("POST", url, task, timeout=self.timeout)
        return _check_task(body, url)

    def get_task(self, task_id: str) -> dict[str, Any]:
        """``GET /tasks/{task_id}``."""
        url = self._url(f"/tasks/{quote(task_id, safe='')}")
        _, body = request_json("GET", url, timeout=self.timeout)
        return _check_task(body, url)

    def list_tasks(self, conversation_id: str | None = None) -> list[dict[str, Any]]:
        """``GET /tasks``, optionally filtered by conversation."""
        query = f"?{urlencode({'conversation_id': conversation_id})}" if conversation_id else ""
        url = self._url(f"/tasks{query}")
        _, body = request_json("GET", url, timeout=self.timeout)
        return [_check_task(t, url) for t in body["tasks"]]

    def wait(
        self, task_id: str, *, timeout: float = 60.0, poll_interval: float = 0.1
    ) -> dict[str, Any]:
        """Poll until ``task_id`` reaches a terminal state; return the final task.

        Raises :class:`TaskTimeout` if that takes longer than ``timeout`` seconds.
        """
        start = time.monotonic()
        interval = poll_interval
        while True:
            task = self.get_task(task_id)
            if lc.is_terminal(task["status"]):
                return task
            waited = time.monotonic() - start
            if waited >= timeout:
                raise TaskTimeout(task, waited)
            time.sleep(min(interval, max(0.0, timeout - waited)))
            interval = min(interval * 1.5, 2.0)

    def delegate(
        self,
        capability: str,
        context: dict[str, Any] | None = None,
        *,
        conversation_id: str | None = None,
        constraints: dict[str, Any] | None = None,
        task_id: str | None = None,
        timeout: float = 60.0,
        poll_interval: float = 0.1,
    ) -> dict[str, Any]:
        """Submit a new task and wait for its outcome (completed, failed, rejected, timed out)."""
        task = lc.new_task(
            capability,
            context,
            conversation_id=conversation_id,
            task_id=task_id,
            constraints=constraints,
        )
        accepted = self.submit(task)
        if lc.is_terminal(accepted["status"]):
            return accepted
        return self.wait(accepted["task_id"], timeout=timeout, poll_interval=poll_interval)


class RegistryClient:
    """Talks to a registry: register manifests and look agents up by capability."""

    def __init__(self, base_url: str, *, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _agent_url(self, agent_id: str) -> str:
        return f"{self.base_url}/agents/{quote(agent_id, safe='')}"

    def health(self) -> dict[str, Any]:
        _, body = request_json("GET", f"{self.base_url}/healthz", timeout=self.timeout)
        return body

    def register(self, manifest: dict[str, Any]) -> bool:
        """Register or update a manifest; return True if it was newly created."""
        status, _ = request_json("POST", f"{self.base_url}/agents", manifest, timeout=self.timeout)
        return status == 201

    def unregister(self, agent_id: str) -> None:
        request_json("DELETE", self._agent_url(agent_id), timeout=self.timeout)

    def get(self, agent_id: str) -> dict[str, Any]:
        url = self._agent_url(agent_id)
        _, body = request_json("GET", url, timeout=self.timeout)
        return _check_manifest(body, url)

    def find(self, capability: str | None = None) -> list[dict[str, Any]]:
        """Return registered manifests, optionally only agents offering ``capability``."""
        query = f"?{urlencode({'capability': capability})}" if capability else ""
        url = f"{self.base_url}/agents{query}"
        _, body = request_json("GET", url, timeout=self.timeout)
        return [_check_manifest(m, url) for m in body["agents"]]

    def find_one(self, capability: str) -> dict[str, Any]:
        """Return the first agent offering ``capability``; raise ``LookupError`` if none."""
        agents = self.find(capability)
        if not agents:
            raise LookupError(f"no registered agent offers capability {capability!r}")
        return agents[0]

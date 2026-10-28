"""Reference AgentMesh registry: an advisory index of agent manifests.

The registry is a discovery index, not a broker: task traffic never flows through it.

HTTP API::

    POST   /agents                    register or update a manifest (201 created, 200 updated)
    GET    /agents[?capability=ID]    list manifests, optionally only agents offering ID
    GET    /agents/{agent_id}         one manifest
    DELETE /agents/{agent_id}         remove a manifest (204)
    GET    /healthz                   liveness and agent count
"""

from __future__ import annotations

import copy
import threading
from http import HTTPStatus
from typing import Any

from agentmesh._http import HTTPError, Request, Response, Router, RunningServer
from agentmesh.lifecycle import ErrorCode
from agentmesh.validation import validate_manifest


class Registry:
    """A thread-safe, in-memory manifest index keyed by ``agent_id``."""

    def __init__(self, max_agents: int = 10_000):
        if max_agents < 1:
            raise ValueError("max_agents must be >= 1")
        self.max_agents = max_agents
        self._agents: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register(self, manifest: Any) -> bool:
        """Add or replace a manifest; return True if the agent was not registered before.

        Raises :class:`agentmesh._http.HTTPError` (400) for an invalid manifest and (507)
        when the registry is full.
        """
        problems = validate_manifest(manifest)
        if problems:
            raise HTTPError(
                HTTPStatus.BAD_REQUEST,
                ErrorCode.INVALID_PAYLOAD,
                "manifest does not match the manifest schema",
                [str(p) for p in problems],
            )
        agent_id = manifest["agent_id"]
        with self._lock:
            created = agent_id not in self._agents
            if created and len(self._agents) >= self.max_agents:
                raise HTTPError(
                    HTTPStatus.INSUFFICIENT_STORAGE, "registry_full", "the registry is full"
                )
            self._agents[agent_id] = copy.deepcopy(manifest)
        return created

    def unregister(self, agent_id: str) -> bool:
        """Remove an agent; return True if it was registered."""
        with self._lock:
            return self._agents.pop(agent_id, None) is not None

    def get(self, agent_id: str) -> dict[str, Any] | None:
        with self._lock:
            manifest = self._agents.get(agent_id)
            return None if manifest is None else copy.deepcopy(manifest)

    def find(self, capability: str | None = None) -> list[dict[str, Any]]:
        """Return manifests sorted by agent_id, optionally only agents offering ``capability``."""
        with self._lock:
            manifests = [copy.deepcopy(m) for _, m in sorted(self._agents.items())]
        if capability is None:
            return manifests
        return [
            m for m in manifests if any(c["capability_id"] == capability for c in m["capabilities"])
        ]

    def __len__(self) -> int:
        with self._lock:
            return len(self._agents)

    # -- HTTP ------------------------------------------------------------------------------

    def router(self) -> Router:
        router = Router()
        router.add("GET", "/healthz", lambda req: Response(HTTPStatus.OK, self._health()))
        router.add("POST", "/agents", self._post)
        router.add("GET", "/agents", self._list)
        router.add("GET", "/agents/{agent_id}", self._get)
        router.add("DELETE", "/agents/{agent_id}", self._delete)
        return router

    def serve(self, host: str = "127.0.0.1", port: int = 0) -> RunningServer:
        """Start the registry HTTP API in a background thread (``port=0`` picks a free port)."""
        return RunningServer(self.router(), host, port).start()

    def _health(self) -> dict[str, Any]:
        return {"status": "ok", "agents": len(self)}

    def _post(self, req: Request) -> Response:
        created = self.register(req.body)
        status = HTTPStatus.CREATED if created else HTTPStatus.OK
        return Response(status, copy.deepcopy(req.body))

    def _list(self, req: Request) -> Response:
        return Response(HTTPStatus.OK, {"agents": self.find(req.query.get("capability"))})

    def _get(self, req: Request) -> Response:
        manifest = self.get(req.params["agent_id"])
        if manifest is None:
            raise HTTPError(HTTPStatus.NOT_FOUND, ErrorCode.NOT_FOUND, "unknown agent_id")
        return Response(HTTPStatus.OK, manifest)

    def _delete(self, req: Request) -> Response:
        if not self.unregister(req.params["agent_id"]):
            raise HTTPError(HTTPStatus.NOT_FOUND, ErrorCode.NOT_FOUND, "unknown agent_id")
        return Response(HTTPStatus.NO_CONTENT)

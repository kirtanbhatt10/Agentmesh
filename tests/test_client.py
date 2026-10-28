"""Tests for AgentClient behaviour against misbehaving or unreachable services."""

from __future__ import annotations

import socket
import threading
from http import HTTPStatus

import pytest

from agentmesh import AgentClient, ProtocolError, RegistryClient, TaskTimeout, new_task
from agentmesh._http import Response, Router, RunningServer


@pytest.fixture
def fake_service():
    """A server whose routes return whatever the test puts in ``responses``."""
    responses = {}
    router = Router()
    for method, path in [
        ("GET", "/manifest"),
        ("POST", "/tasks"),
        ("GET", "/tasks/{task_id}"),
        ("GET", "/agents"),
    ]:
        router.add(method, path, lambda req, key=(method, path): responses[key])
    server = RunningServer(router, "127.0.0.1", 0).start()
    yield server.url, responses
    server.close()


def test_invalid_manifest_raises_protocol_error(fake_service):
    url, responses = fake_service
    responses[("GET", "/manifest")] = Response(HTTPStatus.OK, {"name": "half a manifest"})
    with pytest.raises(ProtocolError, match="invalid manifest"):
        AgentClient(url).manifest()


def test_invalid_task_raises_protocol_error(fake_service):
    url, responses = fake_service
    responses[("POST", "/tasks")] = Response(HTTPStatus.ACCEPTED, {"task_id": "t"})
    with pytest.raises(ProtocolError, match="invalid task"):
        AgentClient(url).submit(new_task("x"))


def test_registry_listing_is_validated(fake_service):
    url, responses = fake_service
    responses[("GET", "/agents")] = Response(HTTPStatus.OK, {"agents": [{"agent_id": "x"}]})
    with pytest.raises(ProtocolError):
        RegistryClient(url).find()


def test_wait_times_out_on_a_stuck_task(fake_service):
    url, responses = fake_service
    stuck = dict(new_task("x", task_id="t-1"), status="executing")
    responses[("GET", "/tasks/{task_id}")] = Response(HTTPStatus.OK, stuck)
    with pytest.raises(TaskTimeout) as exc:
        AgentClient(url).wait("t-1", timeout=0.3, poll_interval=0.05)
    assert exc.value.task["status"] == "executing"
    assert isinstance(exc.value, TimeoutError)


def test_delegate_returns_rejections_without_polling(fake_service):
    url, responses = fake_service
    rejected = dict(
        new_task("x"), status="rejected", error={"code": "unknown_capability", "message": "no"}
    )
    responses[("POST", "/tasks")] = Response(HTTPStatus.OK, rejected)
    assert AgentClient(url).delegate("x")["status"] == "rejected"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_unreachable_agent_raises_oserror():
    with pytest.raises(OSError):
        AgentClient(f"http://127.0.0.1:{_free_port()}", timeout=2).manifest()


def test_concurrent_delegations(serve, echo_agent):
    client = AgentClient(serve(echo_agent).url)
    results = []

    def run(i):
        results.append(client.delegate("echo", {"i": i}, conversation_id="conv-many"))

    threads = [threading.Thread(target=run, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert len(results) == 20
    assert all(t["status"] == "completed" for t in results)
    assert sorted(t["result"]["data"]["echo"]["i"] for t in results) == list(range(20))
    assert len(client.list_tasks("conv-many")) == 20

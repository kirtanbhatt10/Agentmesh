"""Tests for the reference agent: manifest, HTTP API, lifecycle, constraints and retries."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from agentmesh import (
    Agent,
    AgentClient,
    AgentMeshHTTPError,
    TaskFailure,
    TaskResult,
    new_task,
    validate_manifest,
    validate_task,
)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _agent_with(handler, *, capability="work", **agent_kwargs) -> Agent:
    agent = Agent("worker", **agent_kwargs)
    agent.add_capability(capability, handler)
    return agent


# -- manifest ------------------------------------------------------------------------------


def test_manifest_is_valid_and_points_at_the_server(serve, echo_agent):
    server = serve(echo_agent)
    manifest = AgentClient(server.url).manifest()
    assert validate_manifest(manifest) == []
    assert manifest["agent_id"] == "urn:agentmesh:echo"
    assert manifest["description"] == "Echoes its context."
    assert manifest["endpoints"] == {
        "base_url": server.url,
        "manifest": f"{server.url}/manifest",
        "tasks": f"{server.url}/tasks",
    }
    assert [c["capability_id"] for c in manifest["capabilities"]] == ["echo"]


def test_manifest_uses_public_url_and_metadata(serve):
    agent = Agent("pub", version="1.2.3", metadata={"team": "x"}, agent_id="urn:x:pub")
    agent.add_capability("c", lambda ctx: {}, description="d", input_hint="i", output_hint="o")
    serve(agent, public_url="https://agents.example.com/pub/")
    manifest = agent.manifest()
    assert manifest["endpoints"]["base_url"] == "https://agents.example.com/pub"
    assert manifest["metadata"] == {"team": "x"}
    assert manifest["capabilities"] == [
        {"capability_id": "c", "description": "d", "input_hint": "i", "output_hint": "o"}
    ]


def test_manifest_needs_a_base_url_and_a_capability():
    agent = Agent("a")
    with pytest.raises(ValueError):
        agent.serve()
    agent.add_capability("c", lambda ctx: {})
    with pytest.raises(ValueError):
        agent.manifest()
    assert agent.manifest("http://localhost:9")["endpoints"]["base_url"] == "http://localhost:9"


def test_invalid_agent_settings_are_rejected():
    agent = Agent("a")
    agent.add_capability("c", lambda ctx: {})
    with pytest.raises(ValueError):
        agent.add_capability("c", lambda ctx: {})
    with pytest.raises(ValueError):
        agent.add_capability("", lambda ctx: {})
    with pytest.raises(TypeError):
        agent.add_capability("d", "not callable")
    for kwargs in ({"max_retries": -1}, {"max_workers": 0}, {"max_tasks": 0}):
        with pytest.raises(ValueError):
            Agent("a", **kwargs)


def test_invalid_version_makes_the_manifest_invalid():
    agent = Agent("bad", version="v1")
    agent.add_capability("c", lambda ctx: {})
    with pytest.raises(ValueError, match="invalid manifest"):
        agent.manifest("http://localhost")


# -- happy path ----------------------------------------------------------------------------


def test_delegate_completes_with_result_and_usage(echo_client):
    task = echo_client.delegate("echo", {"hello": "world"}, conversation_id="conv-1")
    assert task["status"] == "completed"
    assert task["conversation_id"] == "conv-1"
    assert task["result"] == {"data": {"echo": {"hello": "world"}, "attempt": 1}}
    assert isinstance(task["usage"]["duration_ms"], int)
    assert validate_task(task) == []


def test_submit_returns_accepted_then_get_shows_progress(serve):
    release = threading.Event()

    def slow(context):
        release.wait(5)
        return {"done": True}

    client = AgentClient(serve(_agent_with(slow)).url)
    accepted = client.submit(new_task("work", task_id="t-1"))
    assert accepted["status"] == "accepted"
    assert client.get_task("t-1")["status"] in ("accepted", "executing")
    release.set()
    assert client.wait("t-1", timeout=5)["status"] == "completed"


def test_handler_can_return_task_result_with_summary_and_usage(serve):
    def handler(context):
        return TaskResult(data={"n": 1}, summary="one", usage={"model": "m", "duration_ms": 7})

    task = AgentClient(serve(_agent_with(handler)).url).delegate("work")
    assert task["result"] == {"data": {"n": 1}, "summary": "one"}
    assert task["usage"] == {"model": "m", "duration_ms": 7}


def test_handler_gets_a_copy_of_the_context(serve):
    seen = []

    def handler(context, info):
        context["mutated"] = True
        seen.append(info)
        return {}

    agent = _agent_with(handler)
    client = AgentClient(serve(agent).url)
    task = client.delegate("work", {"a": 1}, constraints={"output_format": "json"})
    assert task["context"] == {"a": 1}
    assert seen[0].task_id == task["task_id"]
    assert seen[0].constraints == {"output_format": "json"}
    assert seen[0].deadline is None


def test_list_tasks_filters_by_conversation(echo_client):
    a = echo_client.delegate("echo", conversation_id="conv-a")
    echo_client.delegate("echo", conversation_id="conv-b")
    listed = echo_client.list_tasks("conv-a")
    assert [t["task_id"] for t in listed] == [a["task_id"]]
    assert len(echo_client.list_tasks()) == 2


def test_health(echo_client):
    assert echo_client.health() == {
        "status": "ok",
        "agent_id": "urn:agentmesh:echo",
        "active_tasks": 0,
    }


# -- rejection and bad requests ------------------------------------------------------------


def test_unknown_capability_is_rejected(echo_client):
    task = echo_client.submit(new_task("translate", task_id="t-x"))
    assert task["status"] == "rejected"
    assert task["error"]["code"] == "unknown_capability"
    assert task["error"]["retryable"] is False
    assert echo_client.get_task("t-x")["status"] == "rejected"


def test_unsupported_output_format_is_rejected(echo_client):
    task = echo_client.delegate("echo", constraints={"output_format": "pdf"})
    assert task["status"] == "rejected"
    assert task["error"]["code"] == "unsupported_constraint"
    ok = echo_client.delegate("echo", constraints={"output_format": "markdown"})
    assert ok["status"] == "completed"


def test_past_deadline_is_rejected(echo_client):
    past = _iso(datetime.now(timezone.utc) - timedelta(minutes=1))
    task = echo_client.delegate("echo", constraints={"deadline": past})
    assert task["status"] == "rejected"
    assert task["error"]["code"] == "deadline_exceeded"


def test_unparseable_deadline_is_rejected(echo_client):
    task = echo_client.delegate("echo", constraints={"deadline": "next tuesday"})
    assert task["status"] == "rejected"
    assert task["error"]["code"] == "unsupported_constraint"


def test_future_deadline_is_accepted(echo_client):
    future = _iso(datetime.now(timezone.utc) + timedelta(minutes=5))
    assert echo_client.delegate("echo", constraints={"deadline": future})["status"] == "completed"


def test_schema_invalid_submission_is_a_400_with_details(echo_client):
    with pytest.raises(AgentMeshHTTPError) as exc:
        echo_client.submit({"task_id": "t"})
    assert exc.value.status == 400
    assert exc.value.code == "invalid_payload"
    assert any("conversation_id" in d for d in exc.value.body["error"]["details"])


@pytest.mark.parametrize(
    "extra",
    [
        {"status": "completed", "result": {"data": {}}},
        {"status": "accepted"},
        {"result": {"data": {}}},
        {"usage": {"model": "m"}},
    ],
)
def test_submission_must_be_a_fresh_task(echo_client, extra):
    with pytest.raises(AgentMeshHTTPError) as exc:
        echo_client.submit({**new_task("echo"), **extra})
    assert exc.value.status == 400


def test_submission_without_status_is_accepted(echo_client):
    task = new_task("echo")
    del task["status"]
    assert echo_client.submit(task)["status"] == "accepted"


def test_resubmitting_the_same_task_is_idempotent(echo_client):
    task = new_task("echo", {"x": 1}, task_id="t-dup")
    echo_client.submit(task)
    echo_client.wait("t-dup")
    again = echo_client.submit(task)
    assert again["status"] == "completed"
    with pytest.raises(AgentMeshHTTPError) as exc:
        echo_client.submit({**task, "context": {"x": 2}})
    assert exc.value.status == 409
    assert exc.value.code == "duplicate_task"


def test_unknown_task_and_routes(echo_client):
    with pytest.raises(AgentMeshHTTPError) as exc:
        echo_client.get_task("nope")
    assert exc.value.status == 404
    with pytest.raises(AgentMeshHTTPError) as exc:
        AgentClient(echo_client.base_url + "/nothing").manifest()
    assert exc.value.status == 404


def _raw(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


def test_wrong_method_is_405(echo_client):
    status, body = _raw("DELETE", f"{echo_client.base_url}/manifest")
    assert status == 405
    assert body["error"]["code"] == "method_not_allowed"


def test_non_json_body_is_400(echo_client):
    status, body = _raw("POST", f"{echo_client.base_url}/tasks", data=b"{nope")
    assert status == 400
    assert body["error"]["code"] == "invalid_json"


def test_oversized_body_is_413(echo_client):
    big = json.dumps({"blob": "x" * (1024 * 1024 + 10)}).encode()
    try:
        status, body = _raw("POST", f"{echo_client.base_url}/tasks", data=big)
    except (ConnectionError, urllib.error.URLError):
        return  # the server may close the socket before the client finishes sending
    assert status == 413
    assert body["error"]["code"] == "payload_too_large"


# -- failures, retries and timeouts --------------------------------------------------------


def test_task_failure_becomes_a_structured_error(serve):
    def handler(context):
        raise TaskFailure("bad_input", "context.query is required")

    task = AgentClient(serve(_agent_with(handler)).url).delegate("work")
    assert task["status"] == "failed"
    assert task["error"] == {
        "code": "bad_input",
        "message": "context.query is required",
        "retryable": False,
    }


def test_unexpected_exception_is_a_handler_error(serve):
    def handler(context):
        raise KeyError("missing")

    task = AgentClient(serve(_agent_with(handler)).url).delegate("work")
    assert task["status"] == "failed"
    assert task["error"]["code"] == "handler_error"
    assert "KeyError" in task["error"]["message"]


def test_retryable_failures_are_retried_within_budget(serve):
    def flaky(context, info):
        if info.attempt < 3:
            raise TaskFailure("upstream_unavailable", "try again", retryable=True)
        return {"attempt": info.attempt}

    client = AgentClient(serve(_agent_with(flaky, max_retries=2, retry_delay=0.01)).url)
    task = client.delegate("work")
    assert task["status"] == "completed"
    assert task["result"]["data"] == {"attempt": 3}


def test_retry_budget_exhausted_reports_retryable_failure(serve):
    calls = []

    def always_down(context):
        calls.append(1)
        raise TaskFailure("upstream_unavailable", "down", retryable=True)

    client = AgentClient(serve(_agent_with(always_down, max_retries=1)).url)
    task = client.delegate("work")
    assert task["status"] == "failed"
    assert task["error"]["retryable"] is True
    assert len(calls) == 2


@pytest.mark.parametrize(
    "outcome,code",
    [
        (["not", "a", "dict"], "invalid_result"),
        ({"bad": object()}, "invalid_result"),
        (TaskResult(data={}, usage={"cost_usd": 1}), "invalid_result"),
        ({"blob": "x" * 200}, "result_too_large"),
    ],
)
def test_bad_results_fail_the_task(serve, outcome, code):
    client = AgentClient(serve(_agent_with(lambda ctx: outcome)).url)
    task = client.delegate("work", constraints={"max_result_bytes": 100})
    assert task["status"] == "failed"
    assert task["error"]["code"] == code


def test_timeout_seconds_times_out_a_slow_task(serve):
    release = threading.Event()

    def slow(context):
        release.wait(5)
        return {"late": True}

    client = AgentClient(serve(_agent_with(slow)).url)
    started = time.monotonic()
    task = client.delegate("work", constraints={"timeout_seconds": 1}, timeout=5)
    assert task["status"] == "timed_out"
    assert task["error"]["code"] == "deadline_exceeded"
    assert 0.9 <= time.monotonic() - started < 4
    release.set()
    time.sleep(0.2)
    assert client.get_task(task["task_id"])["status"] == "timed_out"


def test_queued_task_times_out_from_accepted(serve):
    release = threading.Event()

    def blocking(context):
        release.wait(5)
        return {}

    client = AgentClient(serve(_agent_with(blocking, max_workers=1)).url)
    first = client.submit(new_task("work"))
    queued = client.submit(new_task("work", constraints={"timeout_seconds": 1}))
    time.sleep(1.2)
    assert client.get_task(queued["task_id"])["status"] == "timed_out"
    release.set()
    assert client.wait(first["task_id"], timeout=5)["status"] == "completed"
    time.sleep(0.2)
    assert client.get_task(queued["task_id"])["status"] == "timed_out"


def test_old_finished_tasks_are_evicted(serve):
    agent = _agent_with(lambda ctx: {}, max_tasks=2)
    client = AgentClient(serve(agent).url)
    ids = [client.delegate("work")["task_id"] for _ in range(3)]
    assert [t["task_id"] for t in client.list_tasks()] == ids[1:]


def test_agent_can_be_used_without_http():
    agent = _agent_with(lambda ctx: {"ok": True})
    try:
        status, task = agent.submit(new_task("work", task_id="local"))
        assert status == 202
        for _ in range(100):
            if agent.get_task("local")["status"] == "completed":
                break
            time.sleep(0.01)
        assert agent.get_task("local")["result"] == {"data": {"ok": True}}
        assert agent.get_task("missing") is None
    finally:
        agent.close()


def test_keep_alive_connection_survives_error_responses(echo_client):
    """Errors must consume the request body so the next request on the socket parses."""
    import http.client
    from urllib.parse import urlsplit

    parts = urlsplit(echo_client.base_url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=5)
    try:
        conn.request("POST", "/nowhere", body=b'{"x": 1}')
        first = conn.getresponse()
        first.read()
        assert first.status == 404
        conn.request("POST", "/tasks", body=b"{broken")
        second = conn.getresponse()
        second.read()
        assert second.status == 400
        conn.request("GET", "/healthz")
        third = conn.getresponse()
        assert third.status == 200
        assert json.loads(third.read())["status"] == "ok"
    finally:
        conn.close()


def test_bad_content_length_is_400(echo_client):
    import http.client
    from urllib.parse import urlsplit

    parts = urlsplit(echo_client.base_url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=5)
    try:
        conn.putrequest("POST", "/tasks")
        conn.putheader("Content-Length", "abc")
        conn.endheaders()
        response = conn.getresponse()
        assert response.status == 400
        assert json.loads(response.read())["error"]["code"] == "bad_request"
    finally:
        conn.close()

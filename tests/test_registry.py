"""Tests for the reference registry and RegistryClient."""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import pytest

from agentmesh import Agent, AgentMeshHTTPError, Registry, RegistryClient

PAYLOADS = Path(__file__).resolve().parent.parent / "examples" / "payloads"


def _manifest(name: str) -> dict:
    return json.loads((PAYLOADS / f"{name}.manifest.json").read_text(encoding="utf-8"))


def test_register_find_get_and_delete(registry_url):
    client = RegistryClient(registry_url)
    researcher, writer = _manifest("researcher"), _manifest("writer")
    assert client.register(researcher) is True
    assert client.register(writer) is True
    assert client.health() == {"status": "ok", "agents": 2}

    assert [m["name"] for m in client.find()] == ["researcher", "writer"]
    assert [m["name"] for m in client.find("document-writing")] == ["writer"]
    assert client.find("nothing") == []
    assert client.find_one("web-research") == researcher
    with pytest.raises(LookupError):
        client.find_one("nothing")

    assert client.get(researcher["agent_id"]) == researcher

    client.unregister(researcher["agent_id"])
    with pytest.raises(AgentMeshHTTPError) as exc:
        client.get(researcher["agent_id"])
    assert exc.value.status == 404
    with pytest.raises(AgentMeshHTTPError) as exc:
        client.unregister(researcher["agent_id"])
    assert exc.value.status == 404


def test_reregistering_updates_the_manifest(registry_url):
    client = RegistryClient(registry_url)
    manifest = _manifest("writer")
    client.register(manifest)
    updated = copy.deepcopy(manifest)
    updated["version"] = "0.2.0"
    assert client.register(updated) is False
    assert client.get(manifest["agent_id"])["version"] == "0.2.0"
    assert len(client.find()) == 1


def test_agent_ids_with_slashes_round_trip(registry_url):
    client = RegistryClient(registry_url)
    manifest = dict(_manifest("writer"), agent_id="https://agents.example.com/writer")
    client.register(manifest)
    assert client.get("https://agents.example.com/writer")["agent_id"] == manifest["agent_id"]


def test_invalid_manifest_is_rejected_with_details(registry_url):
    with pytest.raises(AgentMeshHTTPError) as exc:
        RegistryClient(registry_url).register({"agent_id": "x"})
    assert exc.value.status == 400
    assert exc.value.code == "invalid_payload"
    assert exc.value.body["error"]["details"]


def test_registry_capacity(serve):
    url = serve(Registry(max_agents=1)).url
    client = RegistryClient(url)
    client.register(_manifest("writer"))
    client.register(_manifest("writer"))  # updating an existing agent is still allowed
    with pytest.raises(AgentMeshHTTPError) as exc:
        client.register(_manifest("researcher"))
    assert exc.value.status == 507
    with pytest.raises(ValueError):
        Registry(max_agents=0)


def test_in_process_api():
    registry = Registry()
    assert registry.register(_manifest("writer")) is True
    assert len(registry) == 1
    assert registry.get("missing") is None
    assert registry.unregister("missing") is False


def test_agent_registers_on_serve_and_unregisters_on_close(serve, registry_url):
    agent = Agent("helper")
    agent.add_capability("help", lambda ctx: {})
    client = RegistryClient(registry_url)
    server = agent.serve(registry_url=registry_url)
    try:
        assert client.find_one("help")["endpoints"]["base_url"] == server.url
    finally:
        server.close()
    assert client.find("help") == []


def test_agent_close_survives_a_vanished_registry(serve):
    registry_server = Registry().serve()
    agent = Agent("helper")
    agent.add_capability("help", lambda ctx: {})
    server = agent.serve(registry_url=registry_server.url)
    registry_server.close()
    server.close()  # unregister fails, but closing must not raise


def test_agent_re_registers_after_registry_loses_it(serve):
    registry = Registry()
    url = serve(registry).url
    agent = Agent("helper")
    agent.add_capability("help", lambda ctx: {})
    serve(agent, registry_url=url, registry_interval=0.05)
    assert registry.unregister("urn:agentmesh:helper")  # e.g. the registry restarted
    for _ in range(100):
        if registry.get("urn:agentmesh:helper") is not None:
            break
        time.sleep(0.02)
    assert registry.get("urn:agentmesh:helper") is not None


def test_failed_first_registration_closes_the_server():
    agent = Agent("helper")
    agent.add_capability("help", lambda ctx: {})
    with pytest.raises(OSError):
        agent.serve(registry_url="http://127.0.0.1:9", registry_interval=None)
    with pytest.raises(ValueError):
        agent.serve(registry_url="http://127.0.0.1:9", registry_interval=0)

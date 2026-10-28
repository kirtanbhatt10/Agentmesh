"""Tests for the three-agent demo and the network-facing CLI commands."""

from __future__ import annotations

import json

import pytest

from agentmesh import AgentClient, Registry, RegistryClient, cli, demo, validate_task
from agentmesh._http import RunningServer
from agentmesh.cli import main


def test_run_demo_produces_a_report_through_two_delegations():
    lines = []
    task = demo.run_demo("How do agents discover each other?", log=lines.append)
    assert validate_task(task) == []
    assert task["status"] == "completed"
    data = task["result"]["data"]
    assert data["report"].startswith("# How do agents discover each other?")
    assert "## Sources" in data["report"]
    assert [s["capability"] for s in data["trace"]] == ["research", "document-writing"]
    assert all(s["status"] == "completed" for s in data["trace"])
    assert any(line.startswith("registry") for line in lines)


def test_research_and_writing_handlers():
    found = demo.research({"query": "registry capability discovery", "max_sources": 2})
    assert len(found.data["findings"]) == 2
    assert "registry" in found.data["findings"][0]["claim"].lower()
    assert demo.research({"query": "zzz qqq"}).data["findings"] == []
    for bad in (
        {},
        {"query": " "},
        {"query": "x", "max_sources": 0},
        {"query": "x", "max_sources": True},
    ):
        with pytest.raises(demo.TaskFailure):
            demo.research(bad)

    report = demo.write_report({"title": "T", "findings": found.data["findings"]})
    assert report.data["report"].count("[1]") == 2
    empty = demo.write_report({"findings": []})
    assert "No findings" in empty.data["report"]
    with pytest.raises(demo.TaskFailure):
        demo.write_report({"findings": "nope"})


def test_orchestrator_fails_cleanly_without_capable_agents(serve, registry_url):
    orchestrator = serve(demo.make_orchestrator(registry_url))
    task = AgentClient(orchestrator.url).delegate("report", {"topic": "anything"})
    assert task["status"] == "failed"
    assert task["error"]["code"] == "no_capable_agent"
    assert task["error"]["retryable"] is True


def test_orchestrator_reports_subtask_failures(serve, registry_url):
    serve(demo.make_researcher(), registry_url=registry_url)
    serve(demo.make_writer(), registry_url=registry_url)
    orchestrator = serve(demo.make_orchestrator(registry_url))
    client = AgentClient(orchestrator.url)
    bad = client.delegate("report", {"topic": "agents", "max_sources": "lots"})
    assert bad["status"] == "failed"
    assert bad["error"]["code"] == "delegation_failed"
    assert "invalid_context" in bad["error"]["message"]
    assert client.delegate("report", {})["error"]["code"] == "invalid_context"


def test_orchestrator_propagates_its_deadline(serve, registry_url):
    researcher = demo.make_researcher()
    serve(researcher, registry_url=registry_url)
    serve(demo.make_writer(), registry_url=registry_url)
    orchestrator = serve(demo.make_orchestrator(registry_url))
    task = AgentClient(orchestrator.url).delegate(
        "report", {"topic": "task lifecycle"}, constraints={"timeout_seconds": 30}
    )
    assert task["status"] == "completed"
    subtask = researcher.get_task(task["result"]["data"]["trace"][0]["task_id"])
    assert "deadline" in subtask["constraints"]
    assert subtask["conversation_id"] == task["conversation_id"]


# -- CLI -----------------------------------------------------------------------------------


def test_cli_demo(capsys):
    assert main(["demo", "what is a manifest"]) == 0
    out = capsys.readouterr().out
    assert "# what is a manifest" in out
    assert "research" in out and "document-writing" in out


def test_cli_demo_json(capsys):
    assert main(["demo", "--json", "--max-sources", "1"]) == 0
    captured = capsys.readouterr()
    task = json.loads(captured.out)
    assert task["status"] == "completed"
    assert "registry" in captured.err


def test_cli_demo_rejects_bad_max_sources(capsys):
    assert main(["demo", "--max-sources", "0"]) == 2


def test_cli_discover_find_and_submit(serve, registry_url, echo_agent, tmp_path, capsys):
    agent_url = serve(echo_agent, registry_url=registry_url).url

    assert main(["discover", agent_url]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "echo"

    assert main(["find", registry_url]) == 0
    assert "urn:agentmesh:echo" in capsys.readouterr().out
    assert main(["find", registry_url, "--capability", "echo", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["name"] == "echo"
    assert main(["find", registry_url, "--capability", "nothing"]) == 1
    capsys.readouterr()

    task_file = tmp_path / "task.json"
    task_file.write_text(
        json.dumps(
            {"task_id": "t-cli", "conversation_id": "c", "capability": "echo", "context": {}}
        )
    )
    assert main(["submit", agent_url, str(task_file), "--wait"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"

    rejected = tmp_path / "rejected.json"
    rejected.write_text(
        json.dumps({"task_id": "t-r", "conversation_id": "c", "capability": "nope", "context": {}})
    )
    assert main(["submit", agent_url, str(rejected)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"


def test_cli_reports_http_and_connection_errors(serve, echo_agent, tmp_path, capsys):
    agent_url = serve(echo_agent).url
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"task_id": "t"}))
    assert main(["submit", agent_url, str(invalid)]) == 1
    err = capsys.readouterr().err
    assert "HTTP 400" in err and "conversation_id" in err

    assert main(["submit", agent_url, str(tmp_path / "missing.json")]) == 1
    assert "cannot read JSON" in capsys.readouterr().err

    assert main(["discover", "http://127.0.0.1:9"]) == 1
    assert "error:" in capsys.readouterr().err


def test_cli_registry_serves_until_interrupted(monkeypatch, capsys):
    def interrupt(self):
        raise KeyboardInterrupt

    monkeypatch.setattr(RunningServer, "serve_forever", interrupt)
    assert main(["registry", "--port", "0"]) == 0
    assert "AgentMesh registry listening on http://127.0.0.1:" in capsys.readouterr().out


def test_cli_demo_agent_registers_and_cleans_up(monkeypatch, serve, capsys):
    registry = Registry()
    url = serve(registry).url
    seen = []

    def interrupt():
        seen.extend(m["name"] for m in RegistryClient(url).find())
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_wait_forever", interrupt)
    assert main(["demo-agent", "writer", "--registry", url]) == 0
    assert seen == ["writer"]
    assert len(registry) == 0
    assert "registered urn:agentmesh:writer" in capsys.readouterr().out


def test_custom_agent_example_runs():
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in [str(root / "src"), env.get("PYTHONPATH", "")] if p
    )
    out = subprocess.run(
        [sys.executable, str(root / "examples" / "custom_agent.py")],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=True,
    ).stdout
    assert "completed {'data': {'words': 4, 'sentences': 2, 'characters': 28}" in out
    assert "failed {'code': 'invalid_context'" in out
    assert "rejected unknown_capability" in out

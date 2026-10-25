"""Tests for the agentmesh Python package: API, examples and CLI."""

import json
from pathlib import Path

import pytest

import agentmesh
from agentmesh import load_schema, validate, validate_manifest, validate_task
from agentmesh.cli import main

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "examples" / "payloads").glob("*.json"))


BASE_TASK = {"task_id": "t", "conversation_id": "c", "capability": "x", "context": {}}


def _schema_for(path: Path) -> str:
    return "manifest" if path.name.endswith(".manifest.json") else "task"


def test_version_is_exposed():
    assert agentmesh.__version__ == "0.1.0"


@pytest.mark.parametrize("name", ["manifest", "task"])
def test_packaged_schema_matches_specs(name):
    spec = json.loads((ROOT / "specs" / f"{name}.schema.json").read_text(encoding="utf-8"))
    assert load_schema(name) == spec


def test_unknown_schema_name_raises():
    with pytest.raises(ValueError):
        load_schema("nope")


def test_examples_exist():
    assert len(EXAMPLES) >= 5


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_payloads_are_valid(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert validate(_schema_for(path), payload) == []


def test_completed_task_requires_result():
    errors = validate_task(dict(BASE_TASK, status="completed"))
    assert any("'result' is a required property" in e.message for e in errors)


@pytest.mark.parametrize("status", ["rejected", "failed", "timed_out"])
def test_unsuccessful_task_requires_error(status):
    errors = validate_task(dict(BASE_TASK, status=status))
    assert any("'error' is a required property" in e.message for e in errors)


def test_in_progress_task_needs_neither_result_nor_error():
    for status in ["submitted", "accepted", "executing"]:
        assert validate_task(dict(BASE_TASK, status=status)) == []


def test_error_paths_point_into_the_payload():
    errors = validate_manifest(
        {
            "agent_id": "a",
            "name": "n",
            "version": "1.0.0",
            "capabilities": [{"capability_id": ""}],
            "endpoints": {"base_url": "http://localhost"},
        }
    )
    assert [e.path for e in errors] == ["$.capabilities[0].capability_id"]
    assert str(errors[0]).startswith("$.capabilities[0].capability_id: ")


def test_cli_accepts_valid_files(capsys):
    manifests = [str(p) for p in EXAMPLES if _schema_for(p) == "manifest"]
    assert main(["validate", "manifest", *manifests]) == 0
    assert "valid manifest" in capsys.readouterr().out


def test_cli_rejects_invalid_file(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"task_id": "t"}), encoding="utf-8")
    assert main(["validate", "task", str(bad)]) == 1
    assert "INVALID" in capsys.readouterr().out


def test_cli_reports_unreadable_json(tmp_path, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert main(["validate", "task", str(broken)]) == 1
    assert "cannot read JSON" in capsys.readouterr().err


def test_cli_prints_schema(capsys):
    assert main(["schema", "task"]) == 0
    assert json.loads(capsys.readouterr().out)["title"].startswith("AgentMesh Task")

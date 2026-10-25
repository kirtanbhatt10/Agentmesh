"""Conformance tests for the draft AgentMesh JSON Schemas in specs/."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

SPECS = Path(__file__).resolve().parent.parent / "specs"


def load(name):
    with open(SPECS / name, encoding="utf-8") as f:
        return json.load(f)


def validator(name):
    return Draft202012Validator(load(name), format_checker=FormatChecker())


@pytest.mark.parametrize("name", ["manifest.schema.json", "task.schema.json"])
def test_schema_is_valid_draft_2020_12(name):
    Draft202012Validator.check_schema(load(name))


VALID_MANIFEST = {
    "agent_id": "urn:agentmesh:researcher",
    "name": "researcher",
    "version": "0.1.0",
    "capabilities": [{"capability_id": "web-research"}],
    "endpoints": {"base_url": "http://localhost:8000"},
}

VALID_TASK = {
    "task_id": "t-1",
    "conversation_id": "c-1",
    "capability": "web-research",
    "context": {"query": "agent protocols"},
}


def test_valid_manifest_passes():
    assert not list(validator("manifest.schema.json").iter_errors(VALID_MANIFEST))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.pop("agent_id"),
        lambda m: m.update(version="v1"),
        lambda m: m.update(capabilities=[]),
        lambda m: m.update(unknown_field=True),
    ],
)
def test_invalid_manifest_fails(mutate):
    m = json.loads(json.dumps(VALID_MANIFEST))
    mutate(m)
    assert list(validator("manifest.schema.json").iter_errors(m))


def test_valid_task_passes():
    task = dict(VALID_TASK, status="completed", result={"data": {}, "summary": "ok"})
    assert not list(validator("task.schema.json").iter_errors(task))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t.pop("context"),
        lambda t: t.update(status="done"),
        lambda t: t.update(constraints={"timeout_seconds": 0}),
        lambda t: t.update(error={"code": "x"}),
    ],
)
def test_invalid_task_fails(mutate):
    t = json.loads(json.dumps(VALID_TASK))
    mutate(t)
    assert list(validator("task.schema.json").iter_errors(t))

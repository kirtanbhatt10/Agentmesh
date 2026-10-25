# tests/

This directory will contain the **test suite** for AgentMesh — protocol conformance tests, agent behavior tests, and integration tests for the reference implementations.

> **Status:** The tests cover the draft JSON Schemas in [`specs/`](../specs/README.md) (`test_schemas.py`) and the `agentmesh` package — validation API, conditional rules, example payloads and CLI (`test_package.py`). CI runs them on Python 3.10–3.13 on every push and pull request (`.github/workflows/tests.yml`).

## Running the tests

```bash
pip install -e ".[dev]"
pytest -v
```

Expected future contents (proposal):

- Protocol conformance tests validating payloads against the schemas in [`specs/`](../specs/README.md).
- Unit and integration tests for the reference agents in [`agents/`](../agents/README.md).

No fake or placeholder test results will be published here.

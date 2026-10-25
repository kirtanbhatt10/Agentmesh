# tests/

This directory will contain the **test suite** for AgentMesh — protocol conformance tests, agent behavior tests, and integration tests for the reference implementations.

> **Status:** The first tests check the draft JSON Schemas in [`specs/`](../specs/README.md): each schema is valid JSON Schema 2020-12, accepts a valid example payload and rejects invalid ones. They run on every push and pull request through GitHub Actions (`.github/workflows/tests.yml`).

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

Expected future contents (proposal):

- Protocol conformance tests validating payloads against the schemas in [`specs/`](../specs/README.md).
- Unit and integration tests for the reference agents in [`agents/`](../agents/README.md).
- A note in this README stating how to run the suite (added once the suite exists).

No fake or placeholder test results will be published here.

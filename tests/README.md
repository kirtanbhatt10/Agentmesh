# tests/

The test suite for AgentMesh. CI runs it on Python 3.10–3.13 on every push and pull request (`.github/workflows/tests.yml`).

| File | Covers |
| --- | --- |
| `test_schemas.py` | The draft JSON Schemas in [`specs/`](../specs/README.md) are valid Draft 2020-12 and accept/reject the right payloads. |
| `test_package.py` | Validation API, conditional rules, example payloads and the `validate`/`schema` CLI commands. |
| `test_lifecycle.py` | Task states, allowed transitions and payload helpers. |
| `test_agent.py` | The reference agent over real HTTP: manifest, submission, rejection reasons, idempotency, deadlines, retries, result checks and HTTP error handling. |
| `test_registry.py` | The registry and `RegistryClient`, including agent registration, heartbeat and clean-up. |
| `test_client.py` | Client behaviour against misbehaving or unreachable services, and concurrent delegations. |
| `test_demo_and_cli.py` | The three-agent demo, the example agent and the network CLI commands. |

Tests start servers on free `127.0.0.1` ports and need no network access, API keys or external services.

## Running the tests

```bash
pip install -e ".[dev]"
pytest -v
```

No fake or placeholder test results will be published here.

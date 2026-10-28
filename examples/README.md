# examples/

## Build your own agent

[`custom_agent.py`](custom_agent.py) defines a small agent with one capability, serves it on a free local port, delegates tasks to it over HTTP and prints the outcomes (completed, failed and rejected):

```bash
pip install -e .
python examples/custom_agent.py
```

## Three-agent demo

The Orchestrator → Researcher → Writer demo ships with the package (`agentmesh.demo`):

```bash
agentmesh demo "How do agents discover each other?"   # one process, four HTTP services
bash scripts/demo-cluster.sh                            # four separate processes
docker compose up --build --wait                        # four containers
```

## Payloads

[`payloads/`](payloads) holds example AgentMesh messages that validate against the draft schemas in [`specs/`](../specs/README.md):

- `researcher.manifest.json`, `writer.manifest.json` — agent manifests.
- `research.task.submitted.json` → `research.task.completed.json` — one task at submission and on completion.
- `writing.task.failed.json` — a failed task with a structured, retryable error.

Check them with the CLI:

```bash
agentmesh validate manifest examples/payloads/*.manifest.json
agentmesh validate task examples/payloads/*.task.*.json
```

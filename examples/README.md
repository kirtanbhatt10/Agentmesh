# examples/

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

## Planned

Runnable agents arrive from Phase 2 onward ([roadmap](../docs/roadmap.md)) and are **not implemented** today:

- A minimal agent exposing a manifest and one task endpoint.
- The three-agent MVP demo (Orchestrator → Researcher → Writer).
- Per-example setup instructions that work without hard-coded credentials.

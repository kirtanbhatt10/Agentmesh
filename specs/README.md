# specs/

This directory contains the **AgentMesh protocol specification**: formal, versioned documents and machine-readable JSON Schemas describing agent manifests and task payloads.

> ⚠️ **Status:** The schemas below are **Phase 1 drafts** for design discussion ([roadmap](../docs/roadmap.md)). They are proposed, not finalized. The `agentmesh` Python package bundles them and validates payloads against them (`agentmesh validate ...`). The conceptual groundwork lives in [docs/protocol-overview.md](../docs/protocol-overview.md).

## Current contents (drafts)

- [`manifest.schema.json`](manifest.schema.json) — proposed agent manifest schema (identity, capabilities, endpoints).
- [`task.schema.json`](task.schema.json) — proposed task payload schema (task/conversation IDs, context, constraints, status, result, error, usage). A `completed` task must include `result`; a `rejected`, `failed` or `timed_out` task must include `error`.

## Planned future contents

- `result.schema.json` / `error.schema.json` — split-out outcome payload schemas.
- A versioned overview spec document with a change log.
- Resolutions for open questions: task ID assignment and idempotency, capability matching semantics, error-code taxonomy.

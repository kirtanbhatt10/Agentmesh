# specs/

This directory contains the **AgentMesh protocol specification**: formal, versioned documents and machine-readable JSON Schemas describing agent manifests and task payloads.

> ⚠️ **Status:** The schemas below are **initial Phase 1 drafts** for design discussion ([Phase 0 → 1 transition](../docs/roadmap.md)). They are proposed, not finalized, and nothing implements them yet. The conceptual groundwork lives in [docs/protocol-overview.md](../docs/protocol-overview.md).

## Current contents (drafts)

- [`manifest.schema.json`](manifest.schema.json) — proposed agent manifest schema (identity, capabilities, endpoints).
- [`task.schema.json`](task.schema.json) — proposed task payload schema (task/conversation IDs, context, constraints, status, result, error, usage).

## Planned future contents

- `result.schema.json` / `error.schema.json` — split-out outcome payload schemas.
- A versioned overview spec document with a change log.
- Formal conditional constraints (e.g., "status `completed` ⇒ `result` present").
- Resolutions for open questions: task ID assignment and idempotency, capability matching semantics, error-code taxonomy.

# agents/

This directory is reserved for **production-oriented reference agents** for AgentMesh — for example LLM-backed Orchestrator, Researcher and Writer services.

> **Status:** The runnable reference agents currently ship inside the `agentmesh` Python package rather than here:
>
> - `agentmesh.Agent` — the agent server (manifest, task endpoints, deadlines, retries). See [docs/http-api.md](../docs/http-api.md).
> - `agentmesh.demo` — offline, deterministic Orchestrator, Researcher and Writer. Run them with `agentmesh demo`, as separate processes with `agentmesh demo-agent NAME --registry URL` or [`scripts/demo-cluster.sh`](../scripts/demo-cluster.sh), or in containers with `docker compose up`.

Expected future contents (proposal):

- `orchestrator/`, `researcher/`, `writer/` — LLM-backed agents (LiteLLM or Ollama) built on `agentmesh.Agent`, each with its own configuration and setup instructions.
- Shared deployment configuration for those services.

What belongs here vs. `examples/`: `agents/` holds maintained, deployable implementations; `examples/` holds small, self-contained demos.

# agents/

This directory will contain the **reference agent implementations** for AgentMesh — the Orchestrator, Researcher, and Writer agents, plus any shared agent runtime/scaffolding code.

> ⚠️ **Status:** There are no agent implementations yet. AgentMesh is in early design ([Phase 0](../docs/roadmap.md)). The planned initial implementation direction (Python + FastAPI, Redis, LiteLLM/Ollama) is described in the [README](../README.md) and [docs/architecture.md](../docs/architecture.md), and is **subject to confirmation**.

Expected future contents (proposal):

- `orchestrator/` — plans goals, discovers capable agents, delegates and assembles tasks.
- `researcher/` — performs research tasks.
- `writer/` — produces written outputs from research context.
- Shared code for manifest serving and task handling, built against the schemas in [`specs/`](../specs/README.md).

What belongs here vs. `examples/`: `agents/` holds maintained reference implementations; `examples/` holds small, self-contained demos.

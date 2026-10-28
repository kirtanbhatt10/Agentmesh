# Roadmap

> ⚠️ **Status:** AgentMesh is **alpha** (v0.2.0). Phase 0 is done; Phases 1–3 are in progress with a working reference implementation; later phases are plans and may change.

## Phase 0 — Repository scaffolding and architecture documentation *(done)*

- ✅ Repository structure and governance files (README, LICENSE, contribution, conduct, security policy).
- ✅ Architecture and concept documents (`docs/`).
- **Outcome:** a clear, honest starting point for design discussion.

## Phase 1 — Protocol specification and JSON schema *(in progress)*

- ✅ **Initial draft schemas published:** [`specs/manifest.schema.json`](../specs/manifest.schema.json) and [`specs/task.schema.json`](../specs/task.schema.json) (marked as drafts; open questions still to resolve).
- ✅ Conditional constraints in the task schema (`completed` ⇒ `result`; `rejected`/`failed`/`timed_out` ⇒ `error`).
- ✅ `agentmesh` Python package with a validation API, CLI and example payloads (v0.1.0).
- ✅ Task lifecycle state machine in code (`agentmesh.lifecycle`, v0.2.0).
- ⬜ Finalize the manifest, task, result, and error schemas; resolve open design questions from [protocol-overview.md](protocol-overview.md) and [task-lifecycle.md](task-lifecycle.md) (task ID assignment, retry semantics, error taxonomy). The reference implementation's current choices are documented in [task-lifecycle.md](task-lifecycle.md#reference-implementation).
- **Outcome:** a specification others can review and implement against.

## Phase 2 — Minimal agent API and manifest discovery *(reference implementation done in v0.2.0)*

- ✅ Reference agent service exposing `GET /manifest`, `POST /tasks` and `GET /tasks/{task_id}` (`agentmesh.Agent`; see [http-api.md](http-api.md)).
- ✅ A simple registry service that indexes manifests and answers capability queries (`agentmesh.Registry`, `agentmesh registry`).
- ✅ Python clients for agents and registries (`AgentClient`, `RegistryClient`) and CLI commands (`discover`, `find`, `submit`).
- ✅ First runnable example: [`examples/custom_agent.py`](../examples/custom_agent.py).
- ⬜ A FastAPI-based variant for production-oriented deployments (the initially proposed stack).
- **Outcome:** two agents can find each other and exchange one task. ✅

## Phase 3 — Three-agent MVP: Orchestrator, Researcher, Writer *(demo done in v0.2.0)*

- ✅ Orchestrator (discovery, delegation, result assembly), Researcher and Writer as independent services (`agentmesh demo`, `agentmesh demo-agent`, `docker compose up`).
- ✅ End-to-end user request → research → report flow over HTTP, with shared `conversation_id` and deadline propagation.
- ⬜ LLM-backed Researcher and Writer (the demo agents are deterministic and offline by design).
- **Outcome:** a working multi-agent demo that validates the protocol shape in practice.

## Phase 4 — Redis-backed task tracking and asynchronous communication *(in progress)*

- ✅ Asynchronous execution with polling; timeout handling per the [task lifecycle](task-lifecycle.md); retries within a budget.
- ⬜ Integrate Redis for transient task state and conversation correlation across processes.
- ⬜ Asynchronous outcome reporting via webhooks.
- **Outcome:** tasks survive across processes and report state asynchronously.

## Phase 5 — Authentication, authorization, observability, testing, security hardening *(planned)*

- A concrete authentication/authorization story for agent-to-agent traffic.
- Rate limiting, input validation, and abuse-prevention review (request size limits and bounded stores exist today).
- Observability: structured logging, tracing, usage metadata reporting.
- Test suite covering the protocol contract; security review of the hardened API surfaces.
- **Outcome:** the MVP becomes a system that can be deployed with reasonable confidence.

## Phase 6 — Multi-agent interoperability and external developer adoption *(planned)*

- Interoperability testing with agents built outside the reference stack (other languages, frameworks).
- Developer experience: documentation, quickstarts, example libraries in `examples/`.
- Community governance, versioned spec releases, and feedback channels.
- **Outcome:** AgentMesh usable and adopted beyond its reference implementation.

## Tracking

Detailed, granular issue tracking will be introduced as phases begin; this roadmap is the stable top-level view. Phase numbering may be adjusted by consensus — see [CONTRIBUTING.md](../CONTRIBUTING.md) to participate.

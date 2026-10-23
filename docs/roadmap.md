# Roadmap

> ⚠️ **Status:** AgentMesh is in **Phase 0**. Only the current phase reflects what exists in this repository; all later phases are plans, subject to change.

## Phase 0 — Repository scaffolding and architecture documentation *(in progress)*

- Repository structure and governance files (README, LICENSE, contribution, conduct, security policy).
- Architecture and concept documents (`docs/`).
- Placeholder directories with intent statements (`specs/`, `examples/`, `agents/`, `tests/`, `scripts/`).
- **Outcome:** a clear, honest starting point for design discussion.
- **Deliverables today:** documentation only — no protocol or code.

## Phase 1 — Protocol specification and JSON schema *(in progress)*

- ✅ **Initial draft schemas published:** [`specs/manifest.schema.json`](../specs/manifest.schema.json) and [`specs/task.schema.json`](../specs/task.schema.json) (marked as drafts; open questions still to resolve).
- ⬜ Finalize the manifest, task, result, and error schemas; resolve open design questions from [protocol-overview.md](protocol-overview.md) and [task-lifecycle.md](task-lifecycle.md) (task ID assignment, retry semantics, error taxonomy).
- ⬜ Formalize conditional constraints (e.g., `completed` ⇒ result present) in the schemas.
- **Outcome:** a specification others can review and implement against.

## Phase 2 — Minimal agent API and manifest discovery *(planned)*

- Reference implementation of a minimal agent service exposing `/manifest` and a basic task endpoint (initial direction: Python + FastAPI).
- A simple registry service able to index manifests and answer capability queries.
- First runnable examples in `examples/`.
- **Outcome:** two agents can find each other and exchange one task.

## Phase 3 — Three-agent MVP: Orchestrator, Researcher, Writer *(planned)*

- Implement the Orchestrator (delegation, result assembly), Researcher, and Writer as independent services.
- Demonstrate an end-to-end user request → research → report flow.
- **Outcome:** a working multi-agent demo that validates the protocol shape in practice.

## Phase 4 — Redis-backed task tracking and asynchronous communication *(planned)*

- Integrate Redis for transient task state and conversation correlation.
- Add asynchronous outcome reporting via webhooks and/or polling.
- Timeout handling per the [task lifecycle draft](task-lifecycle.md).
- **Outcome:** tasks survive across processes and report state asynchronously.

## Phase 5 — Authentication, authorization, observability, testing, security hardening *(planned)*

- A concrete authentication/authorization story for agent-to-agent traffic.
- Rate limiting, input validation, and abuse-prevention review.
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

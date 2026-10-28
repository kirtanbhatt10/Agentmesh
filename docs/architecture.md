# Architecture

> ⚠️ **Status:** design document with a partial reference implementation. Since v0.2.0 the `agentmesh` package implements independent agent services, a registry and polling-based task delegation (see [Reference implementation](#reference-implementation)). Redis-backed state, webhooks and authentication are still planned.

## High-level architecture

AgentMesh proposes a network of **independent agent services** that cooperate over network APIs:

- Each agent (for example, an **Orchestrator**, **Researcher**, or **Writer**) is a separately deployed service with its own lifecycle, owned API, and LLM runtime of its choosing.
- Agents do not share processes, memory, or application state. Coordination happens exclusively through protocol messages.
- A **registry** indexes agent **manifests** so that any agent can discover which other agents exist and what capabilities they advertise.
- **Redis** is the planned backing store for *transient* task state and conversation correlation — not a system of record.

```mermaid
flowchart LR
    subgraph Agents
        O[Orchestrator]
        R[Researcher]
        W[Writer]
    end
    Reg[(Registry)]
    Rd[(Redis - planned)]
    User[Human user]
    User --> O
    O -->|discover by capability| Reg
    O -->|delegate tasks| R
    O -->|delegate tasks| W
    R & W -.->|task state / correlation| Rd
    O -.->|task state / correlation| Rd
```

## Independent agent services

Every participating agent exposes, at minimum:

1. A **manifest endpoint** (`GET /manifest`) describing identity and capabilities. See [agent-discovery.md](agent-discovery.md).
2. A **task interface** for accepting task submissions and reporting results (`POST /tasks`, `GET /tasks/{task_id}`), following the payload conventions in [protocol-overview.md](protocol-overview.md) and the binding in [http-api.md](http-api.md).
3. Its own execution runtime (LLM or otherwise). AgentMesh is model-agnostic: the protocol does not care whether an agent runs LiteLLM, Ollama, or something else.

Agents are peers. The Orchestrator is distinguished by *role* (it plans and delegates), not by special protocol privileges: the Researcher could, in principle, delegate sub-tasks the same way.

## The registry

The registry is a discovery index, not a message broker:

- Agents **publish** manifests describing capabilities.
- Consumers (typically the Orchestrator) **query** the registry by capability to find candidate agents.
- The registry is *advisory*: if an agent's manifest is stale, task delegation may still fail, and that failure is a normal protocol outcome (see [task-lifecycle.md](task-lifecycle.md)).

A registry-less mode — direct manifest fetching by URL — is also part of the design space; decentralized discovery is a possible later evolution. See [agent-discovery.md](agent-discovery.md).

## The Orchestrator

The **Orchestrator** receives a goal from a human user, decomposes it into tasks, discovers capable agents, delegates each task, and assembles the results (for example, passing the Researcher's output to the Writer, and returning the final report to the user). It tracks task and conversation state so that asynchronous results can be correlated back to the originating request.

## Task communication

Task communication is **asynchronous by default**:

1. The delegator submits a task payload containing a **task ID**, a **conversation ID**, context, and constraints.
2. The receiving agent accepts the task (or rejects it) and processes it independently.
3. The delegator learns the outcome via **polling** (implemented) or **webhooks** (planned) over REST.
4. **Redis** (planned) backs the transient state that makes this correlation work across processes: task status, conversation threads, and pending callbacks.

Redis's role is intentionally narrow: it is for short-lived, coordination-related state. Durable storage of results is out of scope for the initial design.

## Reference implementation

What the `agentmesh` package (v0.2.0) provides, using only the Python standard library plus `jsonschema`:

| Component | Module | Notes |
| --- | --- | --- |
| Schemas and validation | `agentmesh.validation` | Draft JSON Schemas bundled in the package. |
| Task lifecycle | `agentmesh.lifecycle` | States, allowed transitions, payload helpers. |
| Agent server | `agentmesh.Agent` | Manifest, task endpoints, worker pool, deadlines, retries, in-memory task store. |
| Registry | `agentmesh.Registry` | In-memory manifest index with capability lookup. |
| Clients | `agentmesh.AgentClient`, `agentmesh.RegistryClient` | Submit, poll, delegate, discover. |
| Demo agents | `agentmesh.demo` | Offline Orchestrator, Researcher and Writer used by `agentmesh demo`. |

The initially proposed stack (FastAPI, Redis, LiteLLM/Ollama) is still the intended direction for production-oriented services; the dependency-light reference keeps the protocol easy to run, test and embed while the specification settles.

## Protocol vs. implementation

AgentMesh deliberately separates:

- **The protocol** — the vocabulary of manifests, task payloads, conversations, results, and errors; expressed in `specs/` and the documents in `docs/`. It is language- and model-agnostic.
- **The implementation** — a concrete reference stack. The implementation must conform to the protocol; the protocol must not depend on the implementation.

This separation is what should eventually let an agent written in any language, with any model, join a mesh without changing how the rest of the mesh works.

## Related documents

- [protocol-overview.md](protocol-overview.md) — payload concepts.
- [http-api.md](http-api.md) — the reference HTTP binding.
- [agent-discovery.md](agent-discovery.md) — manifests and registry discovery.
- [task-lifecycle.md](task-lifecycle.md) — task lifecycle.
- [roadmap.md](roadmap.md) — phased plan.

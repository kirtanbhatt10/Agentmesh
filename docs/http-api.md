# HTTP API (reference implementation)

> **Status:** implemented in the `agentmesh` package (v0.2.0) by `agentmesh.Agent` and `agentmesh.Registry`. This is the HTTP binding the reference services use today; it is a proposal for the protocol's transport, not a finalized standard. Payload shapes come from the draft schemas in [`specs/`](../specs/README.md).

All bodies are JSON (`Content-Type: application/json`). Request bodies must send `Content-Length` and are limited to 1 MiB.

## Agent endpoints

| Method and path | Purpose | Success |
| --- | --- | --- |
| `GET /manifest` | The agent's manifest (validates against `manifest.schema.json`). | `200` manifest |
| `POST /tasks` | Submit a task payload (validates against `task.schema.json`). | `202` accepted task, or `200` rejected task |
| `GET /tasks/{task_id}` | Current state of one task (poll this until it is terminal). | `200` task |
| `GET /tasks?conversation_id=ID` | All tasks, optionally only one conversation. | `200` `{"tasks": [...]}` |
| `GET /healthz` | Liveness and number of non-terminal tasks. | `200` `{"status": "ok", "agent_id": ..., "active_tasks": n}` |

### Submitting a task

A submission is a task payload with `status` either `"submitted"` or absent, and without `result`, `error` or `usage`. The agent answers immediately:

- **`202 Accepted`** with the task in state `accepted`. Execution continues in the background; poll `GET /tasks/{task_id}`.
- **`200 OK`** with the task in state `rejected` and a structured `error` when the agent declines it. Rejection is a protocol outcome, not a transport failure.

Rejection reasons in the reference agent:

| `error.code` | When |
| --- | --- |
| `unknown_capability` | The agent's manifest does not list the requested `capability`. |
| `unsupported_constraint` | `constraints.output_format` is not one the capability produces, or `constraints.deadline` is not an ISO 8601 date-time. |
| `deadline_exceeded` | `constraints.deadline` had already passed at submission. |

**Idempotency.** Re-submitting the same `task_id` with an identical payload returns the task's current state (`200`). Re-using a `task_id` with a different payload is a `409 duplicate_task`.

### Execution outcomes

| Final `status` | `error.code` | When |
| --- | --- | --- |
| `completed` | — | The handler returned a JSON object; it is stored as `result.data` (plus optional `summary` and `usage`; `usage.duration_ms` is filled in). |
| `failed` | handler-defined | The handler raised `TaskFailure(code, message, retryable=...)`. Retryable failures are retried first, within the agent's `max_retries` budget, keeping the same `task_id`. |
| `failed` | `handler_error` | The handler raised any other exception. |
| `failed` | `invalid_result` | The result was not a JSON object, was not serialisable, or had `usage` fields outside the schema. |
| `failed` | `result_too_large` | The serialised result exceeded `constraints.max_result_bytes`. |
| `timed_out` | `deadline_exceeded` | The earlier of `constraints.deadline` and acceptance time + `constraints.timeout_seconds` passed before a result was stored. A late result is discarded. |

## Registry endpoints

The registry is an advisory index, never a broker: task traffic goes directly to agents.

| Method and path | Purpose | Success |
| --- | --- | --- |
| `POST /agents` | Register or replace a manifest (keyed by `agent_id`). | `201` created or `200` updated, with the manifest |
| `GET /agents?capability=ID` | List manifests, optionally only agents offering a capability. | `200` `{"agents": [...]}` |
| `GET /agents/{agent_id}` | One manifest (percent-encode the ID). | `200` manifest |
| `DELETE /agents/{agent_id}` | Remove a manifest. | `204` |
| `GET /healthz` | Liveness and number of registered agents. | `200` `{"status": "ok", "agents": n}` |

Agents started with `Agent.serve(registry_url=...)` (or `agentmesh demo-agent`) register on start, re-register every 30 seconds so a restarted registry repopulates itself, and unregister on shutdown.

## Error responses

Transport-level errors use one shape:

```json
{"error": {"code": "invalid_payload", "message": "task payload does not match the task schema", "details": ["$: 'context' is a required property"]}}
```

| HTTP status | `error.code` | Meaning |
| --- | --- | --- |
| `400` | `invalid_payload` | Body does not match the schema, or a submission carries a status other than `submitted`, or `result`/`error`/`usage`. `details` lists each problem with its JSON path. |
| `400` | `invalid_json` / `bad_request` | Body is not JSON, or `Content-Length` is invalid. |
| `404` | `not_found` | Unknown route, `task_id` or `agent_id`. |
| `405` | `method_not_allowed` | The path exists but not for this method. |
| `409` | `duplicate_task` | `task_id` reused with a different payload. |
| `411` | `length_required` | Chunked request bodies are not supported. |
| `413` | `payload_too_large` | Body larger than 1 MiB. |
| `507` | `registry_full` | The registry reached its `max_agents` limit. |

The error-code taxonomy is still an open Phase 1 question; these are the codes the reference implementation emits today and are collected in `agentmesh.ErrorCode`.

## Security

The reference services have **no authentication, authorization or TLS** (planned for Phase 5). They bind to `127.0.0.1` by default; only expose them on a trusted network, or put them behind a reverse proxy that adds TLS and authentication. See [SECURITY.md](../SECURITY.md).

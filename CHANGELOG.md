# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-28

### Added

- Reference agent server, `agentmesh.Agent`: register capabilities with a decorator and
  serve `GET /manifest`, `POST /tasks`, `GET /tasks/{task_id}`, `GET /tasks` and
  `GET /healthz`. Tasks run asynchronously on a worker pool with an in-memory task store.
  - Explicit rejection of unknown capabilities, unsupported `output_format`, invalid or
    already-passed `deadline`.
  - Deadlines from `constraints.deadline` and `constraints.timeout_seconds`, retries of
    retryable failures within a `max_retries` budget, `max_result_bytes` enforcement and
    result validation.
  - Idempotent re-submission of an identical task; `409 duplicate_task` for a reused
    `task_id` with a different payload.
  - Optional registry membership: register on start, periodic re-registration and
    unregister on shutdown.
- Reference registry, `agentmesh.Registry`: register, list, look up by capability and
  remove manifests over HTTP.
- Clients: `AgentClient` (manifest, submit, poll, `delegate`) and `RegistryClient`
  (register, find, find_one), validating every payload they receive.
- Task lifecycle module, `agentmesh.lifecycle`: states, allowed transitions,
  `new_task()`, `transition()`, `ErrorCode`.
- Three-agent demo (Orchestrator → Researcher → Writer), offline and deterministic:
  `agentmesh demo`, `agentmesh demo-agent`, `scripts/demo-cluster.sh`,
  `Dockerfile` and `docker-compose.yml`.
- CLI commands: `demo`, `registry`, `demo-agent`, `discover`, `find`, `submit`, and a
  global `--verbose` flag. Long-running commands shut down cleanly on SIGTERM.
- `examples/custom_agent.py`, a runnable example of building an agent.
- Documentation: `docs/http-api.md` (HTTP binding and error codes); updated architecture,
  discovery, lifecycle and roadmap documents; security policy for the new services.
- Tests for the lifecycle, agent, registry, clients, demo and CLI; CI now also runs the
  demo, smoke-tests the built wheel with it and builds and runs the Docker image and the
  compose stack.

### Changed

- Task lifecycle: an `accepted` task may move to `timed_out` when its deadline passes
  before execution starts.
- Package metadata: development status Alpha, broader description and keywords.

## [0.1.0] - 2026-10-26

### Added

- `agentmesh` Python package (Python 3.10+) bundling the draft protocol schemas.
- Validation API: `validate_manifest`, `validate_task`, `validate` and `load_schema`,
  returning readable errors with JSON paths such as `$.capabilities[0].capability_id`.
- `agentmesh` command-line tool: `agentmesh validate {manifest,task} FILE...` and
  `agentmesh schema {manifest,task}`.
- Example manifests and task payloads in `examples/payloads/`.
- Conditional rules in the task schema: a `completed` task must include `result`;
  a `rejected`, `failed` or `timed_out` task must include `error`.
- Test suite, CI on Python 3.10–3.13 with linting and package build checks, and a
  tag-triggered release workflow publishing to PyPI.

[Unreleased]: https://github.com/kirtanbhatt10/Agentmesh/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kirtanbhatt10/Agentmesh/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/kirtanbhatt10/Agentmesh/releases/tag/v0.1.0

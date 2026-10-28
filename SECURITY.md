# Security Policy

## Scope

AgentMesh is **alpha software**. The repository contains a draft protocol specification and the `agentmesh` Python package, which includes reference HTTP services (an agent server and a registry). Security-relevant surface today:

- The `agentmesh` package: payload validation, the reference agent and registry HTTP servers, the HTTP clients and the CLI.
- The proposed protocol design (e.g., flaws in the task lifecycle, discovery or payload schemas that could lead to insecure systems if adopted as written).
- Repository configuration, workflow files and the container setup (`Dockerfile`, `docker-compose.yml`).

## Known limitations (by design, for now)

The reference services are meant for development, demos and trusted networks:

- **No authentication, authorization or TLS.** Any client that can reach an agent can submit tasks to it, and any client that can reach a registry can register or remove manifests. Agent-to-agent authentication is planned for Phase 5 of the [roadmap](docs/roadmap.md).
- Services bind to `127.0.0.1` by default. If you bind to `0.0.0.0` or publish container ports, put them behind a reverse proxy that adds TLS and authentication, or keep them on a private network.
- Task state and registry entries are kept **in memory** and are lost on restart.
- Request bodies are capped at 1 MiB and the task and registry stores are bounded, but there is no rate limiting.
- The registry is advisory: a manifest only says what an agent *claims*. Do not trust manifest contents (such as endpoint URLs) more than you trust whoever can write to the registry.

Reports about these documented limitations are welcome as design input, but are not treated as vulnerabilities.

## Reporting a vulnerability

There is no dedicated private security inbox for this project yet; we do not want to publish an email address before it exists and is monitored.

**Preferred method:** open a private vulnerability report using GitHub's private vulnerability reporting feature on this repository (available from the repository's *Security* tab). This keeps the report confidential until a fix or clarification is published.

If private reporting is unavailable for any reason, please open a regular GitHub issue and mark it clearly as a **security concern** without exploit details, so maintainers can triage it quickly and move sensitive details into a private thread.

Please do **not** publicly post exploit details or step-by-step instructions for a flaw before maintainers have acknowledged the report.

## What to include

- A clear description of the issue and its impact.
- The affected version (`agentmesh --version`), module, endpoint or document section.
- Steps or a minimal payload to reproduce, and any relevant threat-model assumptions (deployment topology, trust boundaries).

## Response expectations

This is a volunteer-maintained, early-stage project, so we cannot commit to fixed response times. Maintainers will acknowledge reports as soon as practicable, discuss the concern publicly or privately as appropriate, and ship a fix or documentation update.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.2.x | Yes |
| < 0.2 | No |

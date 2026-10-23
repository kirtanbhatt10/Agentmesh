# Security Policy

## Scope

AgentMesh is currently in an **early design and scaffolding phase**. There is no runnable implementation, no deployed service, and no runtime to attack yet — so today's security-relevant surface is limited to:

- The documentation and proposed protocol design in this repository (e.g., flaws in the proposed task lifecycle, discovery, or payload schema that could lead to insecure designs if adopted as written).
- Repository configuration and workflow files.

## Reporting a vulnerability

There is no dedicated private security inbox for this project yet; we do not want to publish an email address before it exists and is monitored.

**Preferred method:** open a private vulnerability report using GitHub's private vulnerability reporting feature on this repository (available from the repository's *Security* tab). This keeps the report confidential until a fix or clarification is published.

If private reporting is unavailable for any reason, please open a regular GitHub issue and mark it clearly as a **security design concern** so maintainers can triage it quickly and move sensitive details into a private thread.

Please do **not** publicly post exploit details or step-by-step instructions for a flaw before maintainers have acknowledged the report.

## What to include

- A clear description of the issue and its impact on the proposed design or documentation.
- The affected document(s) and section(s).
- Any relevant threat-model assumptions (deployment topology, trust boundaries).

## Response expectations

This is a volunteer-maintained, early-stage project, so we cannot commit to fixed response times. Maintainers will acknowledge reports as soon as practicable, discuss the concern publicly or privately as appropriate, and update the affected documentation.

Once authentication, authorization, and hardening work begins (planned for Phase 5 of the [roadmap](docs/roadmap.md)), this policy will be expanded with concrete contacts, supported versions, and disclosure timelines.

## Supported versions

Not applicable yet — no versions have been released.

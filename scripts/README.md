# scripts/

This directory will contain **developer and maintenance scripts** for the AgentMesh repository — for example, environment bootstrap, lint/format runners, or demo launchers once implementations exist.

> ⚠️ **Status:** There are no scripts yet. AgentMesh is in early design ([Phase 0](../docs/roadmap.md)); setup and build tooling will be added alongside the first implementation (planned Phase 2).

Conventions (proposal): scripts stay small, documented by a header comment, and avoid hard-coded machine-specific paths or credentials. Anything needed to run the project locally will also be documented in the main [README](../README.md).

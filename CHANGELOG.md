# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/kirtanbhatt10/Agentmesh/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kirtanbhatt10/Agentmesh/releases/tag/v0.1.0

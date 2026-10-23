# Contributing to AgentMesh

First off, thank you for considering contributing. AgentMesh is in its **early design and scaffolding phase**: the most valuable contributions right now are to the **specification, documentation, and design discussions**, not to implementation (which has not started yet).

## Where contributions help most today

- Reviewing and critiquing the protocol concepts in [`docs/protocol-overview.md`](docs/protocol-overview.md).
- Improving the architecture documents in [`docs/`](docs/).
- Identifying gaps, ambiguities, or missing lifecycle/error-handling concerns.
- Drafting (proposed) JSON schema sketches in `specs/` — clearly labeled as drafts.

## Reporting issues

1. Search [existing issues](../../issues) first to avoid duplicates.
2. Open an issue and choose the closest matching template if available.
3. For design discussions, describe the problem and the scenario before proposing a solution.
4. For documentation bugs, link the exact section and quote the incorrect text.

## Pull requests

1. Fork the repository and create a branch from `master` with a short, descriptive name (e.g., `docs/task-lifecycle-timeouts`).
2. Keep changes focused: one topic per pull request.
3. Reference the related issue (e.g., `Fixes #12`).
4. Update any documentation affected by your change; documentation and specification changes should stay consistent with each other.
5. Once tests and CI exist (planned for later phases), ensure they pass before requesting review.

## Coding standards

- **Documentation:** clear, concise Markdown; GitHub-compatible syntax; define terminology on first use. Use consistent terms: *AgentMesh*, *Orchestrator*, *Researcher*, *Writer*, *manifest*, *registry*, *task*, *conversation*.
- **Code (future):** the planned reference implementation is Python (FastAPI). When implementation begins, we will adopt linting/formatting standards (e.g., formatters and linters configured in-repo) and document them here.
- **Proposals over claims:** label anything unimplemented as *proposed* or *draft*. Do not describe features as working, tested, or production-ready.

## Commit messages

Write short, imperative commit subjects (e.g., `Add timeout semantics to task lifecycle doc`) with optional body text explaining *why*.

## Documentation expectations

- Every user-facing claim should be verifiable in the repository.
- Mermaid diagrams must render correctly on GitHub.
- No fabricated results, benchmarks, badges, or version numbers.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see [LICENSE](LICENSE)).

# Contributing to AgentMesh

First off, thank you for considering contributing. AgentMesh is **alpha**: the protocol specification is still a draft, and the `agentmesh` Python package provides validators plus a dependency-light reference agent, registry, client and demo. Contributions to the **specification, schemas, documentation and design discussions** are especially valuable, and improvements to the package are welcome too.

## Where contributions help most today

- Reviewing and critiquing the protocol concepts in [`docs/protocol-overview.md`](docs/protocol-overview.md) and the HTTP binding in [`docs/http-api.md`](docs/http-api.md).
- Improving the architecture documents in [`docs/`](docs/).
- Identifying gaps, ambiguities, or missing lifecycle/error-handling concerns.
- Drafting (proposed) JSON schema changes in `specs/` — clearly labeled as drafts.
- Building agents on `agentmesh.Agent` (for example LLM-backed Researcher/Writer agents) and reporting what the protocol makes hard.

## Reporting issues

1. Search [existing issues](../../issues) first to avoid duplicates.
2. Open an issue and choose the closest matching template if available.
3. For design discussions, describe the problem and the scenario before proposing a solution.
4. For documentation bugs, link the exact section and quote the incorrect text.

## Development setup

```bash
git clone https://github.com/kirtanbhatt10/Agentmesh.git
cd Agentmesh
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
ruff check . && ruff format --check .
agentmesh demo
```

## Pull requests

1. Fork the repository and create a branch from `main` with a short, descriptive name (e.g., `docs/task-lifecycle-timeouts`).
2. Keep changes focused: one topic per pull request.
3. Reference the related issue (e.g., `Fixes #12`).
4. Update any documentation affected by your change; documentation, specification and code should stay consistent with each other.
5. Make sure `pytest`, `ruff check .` and `ruff format --check .` pass; CI runs them on every pull request, along with a package build and a Docker build.
6. Add a line to the "Unreleased" section of [CHANGELOG.md](CHANGELOG.md) for user-visible changes.

## Coding standards

- **Documentation:** clear, concise Markdown; GitHub-compatible syntax; define terminology on first use. Use consistent terms: *AgentMesh*, *Orchestrator*, *Researcher*, *Writer*, *manifest*, *registry*, *task*, *conversation*.
- **Code:** Python 3.10+, formatted and linted with [Ruff](https://docs.astral.sh/ruff/) (settings in `pyproject.toml`). The core package depends only on the standard library and `jsonschema`; please discuss before adding runtime dependencies (optional extras are fine).
- **Tests:** new behaviour comes with tests. Tests must not need network access beyond `127.0.0.1`, API keys or external services.
- **Proposals over claims:** label anything unimplemented as *proposed* or *draft*. Do not describe features as working, tested, or production-ready unless they are.

## Commit messages

Write short, imperative commit subjects (e.g., `Add timeout semantics to task lifecycle doc`) with optional body text explaining *why*.

## Documentation expectations

- Every user-facing claim should be verifiable in the repository.
- Mermaid diagrams must render correctly on GitHub.
- No fabricated results, benchmarks, badges, or version numbers.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see [LICENSE](LICENSE)).

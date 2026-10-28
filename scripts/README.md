# scripts/

Developer and demo scripts for the AgentMesh repository.

| Script | What it does |
| --- | --- |
| [`demo-cluster.sh`](demo-cluster.sh) | Starts a registry and the demo Orchestrator, Researcher and Writer as **four separate processes** on ports 8500–8503 (override with `AGENTMESH_PORT`), submits one report task through the CLI, prints the result and shuts everything down. Usage: `bash scripts/demo-cluster.sh ["topic"]`. Requires `pip install -e .`. |

Conventions: scripts stay small, are documented by a header comment, and avoid hard-coded machine-specific paths or credentials. Anything needed to run the project locally is also documented in the main [README](../README.md).

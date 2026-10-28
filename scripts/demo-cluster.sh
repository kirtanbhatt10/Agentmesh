#!/usr/bin/env bash
# Run the AgentMesh demo as four separate processes: a registry plus the Orchestrator,
# Researcher and Writer agents, each on its own port. Submits one report task through
# the CLI, prints the result, then shuts everything down (agents unregister on exit).
#
# Usage: bash scripts/demo-cluster.sh ["topic to report on"]
# Needs: the agentmesh package installed (pip install -e .). Ports: AGENTMESH_PORT..+3
# (default 8500-8503).
set -euo pipefail

TOPIC="${1:-How do agents discover each other and delegate tasks?}"
BASE_PORT="${AGENTMESH_PORT:-8500}"
REGISTRY="http://127.0.0.1:${BASE_PORT}"
WORKDIR="$(mktemp -d)"
PIDS=()

if command -v agentmesh >/dev/null 2>&1; then
  AM=(agentmesh)
else
  AM=(python3 -m agentmesh)
fi

cleanup() {
  for pid in "${PIDS[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

wait_for() {
  for _ in $(seq 1 50); do
    if "${AM[@]}" discover "$1" >/dev/null 2>&1 || "${AM[@]}" find "$1" --json >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.1
  done
  echo "timed out waiting for $1" >&2
  return 1
}

"${AM[@]}" registry --port "$BASE_PORT" >"$WORKDIR/registry.log" 2>&1 &
PIDS+=($!)
wait_for "$REGISTRY"

port=$((BASE_PORT + 1))
for name in researcher writer orchestrator; do
  "${AM[@]}" demo-agent "$name" --registry "$REGISTRY" --port "$port" >"$WORKDIR/$name.log" 2>&1 &
  PIDS+=($!)
  wait_for "http://127.0.0.1:${port}"
  port=$((port + 1))
done

echo "Registered agents:"
"${AM[@]}" find "$REGISTRY"
echo

python3 - "$TOPIC" >"$WORKDIR/task.json" <<'PY'
import json, sys
print(json.dumps({
    "task_id": "report-1",
    "conversation_id": "conv-demo-cluster",
    "capability": "report",
    "context": {"topic": sys.argv[1]},
    "constraints": {"timeout_seconds": 30},
}))
PY

ORCHESTRATOR="http://127.0.0.1:$((BASE_PORT + 3))"
"${AM[@]}" submit "$ORCHESTRATOR" "$WORKDIR/task.json" --wait >"$WORKDIR/result.json"
python3 - "$WORKDIR/result.json" <<'PY'
import json, sys
task = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"Task {task['task_id']}: {task['status']}")
for step in task["result"]["data"]["trace"]:
    print(f"  {step['capability']:<17} -> {step['agent_id']}  [{step['status']}]")
print()
print(task["result"]["data"]["report"], end="")
PY

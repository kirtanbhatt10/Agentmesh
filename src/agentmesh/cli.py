"""Command-line interface for AgentMesh.

Commands::

    agentmesh validate {manifest,task} FILE...    validate JSON files against a schema
    agentmesh schema {manifest,task}              print a JSON Schema
    agentmesh demo [TOPIC]                        run the three-agent demo locally
    agentmesh registry [--host H] [--port P]      serve a registry
    agentmesh demo-agent NAME --registry URL      serve one demo agent and register it
    agentmesh discover AGENT_URL                  fetch and validate an agent's manifest
    agentmesh find REGISTRY_URL [--capability C]  list agents in a registry
    agentmesh submit AGENT_URL FILE [--wait]      submit a task payload to an agent
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import signal
import sys
import threading
from collections.abc import Iterator, Sequence
from typing import Any

from agentmesh import __version__
from agentmesh._http import AgentMeshHTTPError
from agentmesh.validation import SCHEMA_NAMES, load_schema, validate

DEFAULT_TOPIC = "How do AgentMesh agents discover each other and delegate tasks?"
DEMO_AGENTS = ("researcher", "writer", "orchestrator")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentmesh", description="Tools for the AgentMesh agent-to-agent protocol."
    )
    parser.add_argument("--version", action="version", version=f"agentmesh {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="log debug output")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("validate", help="validate JSON files against an AgentMesh schema")
    check.add_argument("schema", choices=SCHEMA_NAMES, help="which schema to validate against")
    check.add_argument("files", nargs="+", help="JSON files to check ('-' reads stdin)")

    show = sub.add_parser("schema", help="print an AgentMesh JSON Schema")
    show.add_argument("schema", choices=SCHEMA_NAMES)

    demo = sub.add_parser("demo", help="run the Orchestrator -> Researcher -> Writer demo")
    demo.add_argument("topic", nargs="?", default=DEFAULT_TOPIC, help="what to report on")
    demo.add_argument("--max-sources", type=int, default=3, help="findings to include")
    demo.add_argument("--json", action="store_true", help="print the final task as JSON")

    reg = sub.add_parser("registry", help="serve an AgentMesh registry")
    reg.add_argument("--host", default="127.0.0.1", help="interface to bind (default 127.0.0.1)")
    reg.add_argument("--port", type=int, default=8500, help="port to bind (default 8500)")

    one = sub.add_parser("demo-agent", help="serve one demo agent and register it")
    one.add_argument("name", choices=DEMO_AGENTS)
    one.add_argument("--registry", required=True, help="registry base URL")
    one.add_argument("--host", default="127.0.0.1", help="interface to bind (default 127.0.0.1)")
    one.add_argument("--port", type=int, default=0, help="port to bind (default: any free)")
    one.add_argument("--public-url", help="base URL to advertise in the manifest")

    disc = sub.add_parser("discover", help="fetch and validate an agent's manifest")
    disc.add_argument("agent_url", help="agent base URL, e.g. http://127.0.0.1:8001")

    find = sub.add_parser("find", help="list agents registered in a registry")
    find.add_argument("registry_url", help="registry base URL, e.g. http://127.0.0.1:8500")
    find.add_argument("--capability", help="only agents offering this capability")
    find.add_argument("--json", action="store_true", help="print manifests as JSON")

    submit = sub.add_parser("submit", help="submit a task payload to an agent")
    submit.add_argument("agent_url", help="agent base URL")
    submit.add_argument("file", help="task JSON file ('-' reads stdin)")
    submit.add_argument("--wait", action="store_true", help="poll until the task finishes")
    submit.add_argument("--timeout", type=float, default=60.0, help="seconds to wait (60)")
    return parser


def _load(path: str):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _validate_files(schema: str, files: Sequence[str]) -> int:
    failed = False
    for path in files:
        try:
            payload = _load(path)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{path}: cannot read JSON: {exc}", file=sys.stderr)
            failed = True
            continue
        problems = validate(schema, payload)
        if problems:
            failed = True
            print(f"{path}: INVALID ({len(problems)} problem(s))")
            for problem in problems:
                print(f"  {problem}")
        else:
            print(f"{path}: valid {schema}")
    return 1 if failed else 0


def _demo(args: argparse.Namespace) -> int:
    from agentmesh.demo import run_demo

    if args.max_sources < 1:
        print("--max-sources must be at least 1", file=sys.stderr)
        return 2
    log = (lambda message: print(message, file=sys.stderr)) if args.json else print
    task = run_demo(args.topic, max_sources=args.max_sources, log=log)
    if args.json:
        _print_json(task)
    elif task["status"] == "completed":
        data = task["result"]["data"]
        print()
        for step in data["trace"]:
            print(f"  {step['capability']:<17} -> {step['agent_id']}  [{step['status']}]")
        print()
        print(data["report"], end="")
    else:
        print(f"\ndemo {task['status']}: {task['error']['code']}: {task['error']['message']}")
    return 0 if task["status"] == "completed" else 1


@contextlib.contextmanager
def _sigterm_as_interrupt() -> Iterator[None]:
    """Treat SIGTERM (``docker stop``, systemd, ``kill``) like Ctrl+C so shutdown is clean."""

    def interrupt(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt

    try:
        previous = signal.signal(signal.SIGTERM, interrupt)
    except ValueError:  # signal handlers can only be installed from the main thread
        yield
        return
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _serve_forever(server: Any, label: str) -> int:
    print(f"{label} listening on {server.url} (Ctrl+C to stop)", flush=True)
    with _sigterm_as_interrupt():
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopping", file=sys.stderr)
    return 0


def _registry(args: argparse.Namespace) -> int:
    from agentmesh._http import RunningServer
    from agentmesh.registry import Registry

    server = RunningServer(Registry().router(), args.host, args.port)
    return _serve_forever(server, "AgentMesh registry")


def _wait_forever() -> None:
    threading.Event().wait()


def _demo_agent(args: argparse.Namespace) -> int:
    from agentmesh import demo

    factories = {
        "researcher": demo.make_researcher,
        "writer": demo.make_writer,
        "orchestrator": lambda: demo.make_orchestrator(args.registry),
    }
    agent = factories[args.name]()
    server = agent.serve(
        args.host, args.port, public_url=args.public_url, registry_url=args.registry
    )
    print(f"registered {agent.agent_id} with {args.registry}", flush=True)
    with _sigterm_as_interrupt():
        try:
            _wait_forever()
        except KeyboardInterrupt:
            print("\nstopping", file=sys.stderr)
        finally:
            server.close()
    return 0


def _discover(args: argparse.Namespace) -> int:
    from agentmesh.client import AgentClient

    _print_json(AgentClient(args.agent_url).manifest())
    return 0


def _find(args: argparse.Namespace) -> int:
    from agentmesh.client import RegistryClient

    agents = RegistryClient(args.registry_url).find(args.capability)
    if args.json:
        _print_json(agents)
        return 0
    if not agents:
        print("no matching agents", file=sys.stderr)
        return 1
    for manifest in agents:
        caps = ", ".join(c["capability_id"] for c in manifest["capabilities"])
        print(f"{manifest['agent_id']}  {manifest['endpoints']['base_url']}  [{caps}]")
    return 0


def _submit(args: argparse.Namespace) -> int:
    from agentmesh.client import AgentClient
    from agentmesh.lifecycle import is_terminal

    try:
        payload = _load(args.file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{args.file}: cannot read JSON: {exc}", file=sys.stderr)
        return 1
    client = AgentClient(args.agent_url)
    task = client.submit(payload)
    if args.wait and not is_terminal(task["status"]):
        task = client.wait(task["task_id"], timeout=args.timeout)
    _print_json(task)
    return 1 if task["status"] in ("rejected", "failed", "timed_out") else 0


_COMMANDS = {
    "demo": _demo,
    "registry": _registry,
    "demo-agent": _demo_agent,
    "discover": _discover,
    "find": _find,
    "submit": _submit,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "schema":
        _print_json(load_schema(args.schema))
        return 0
    if args.command == "validate":
        return _validate_files(args.schema, args.files)

    from agentmesh.client import ProtocolError

    try:
        return _COMMANDS[args.command](args)
    except AgentMeshHTTPError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if isinstance(exc.body, dict) and "error" in exc.body:
            details = exc.body["error"].get("details")
            for detail in details or []:
                print(f"  {detail}", file=sys.stderr)
        return 1
    except (OSError, ProtocolError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

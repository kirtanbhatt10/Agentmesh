"""Command-line interface: ``agentmesh validate {manifest,task} FILE...``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from agentmesh import __version__
from agentmesh.validation import SCHEMA_NAMES, load_schema, validate


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentmesh", description="Tools for the AgentMesh agent-to-agent protocol."
    )
    parser.add_argument("--version", action="version", version=f"agentmesh {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("validate", help="validate JSON files against an AgentMesh schema")
    check.add_argument("schema", choices=SCHEMA_NAMES, help="which schema to validate against")
    check.add_argument("files", nargs="+", help="JSON files to check ('-' reads stdin)")

    show = sub.add_parser("schema", help="print an AgentMesh JSON Schema")
    show.add_argument("schema", choices=SCHEMA_NAMES)
    return parser


def _load(path: str):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "schema":
        print(json.dumps(load_schema(args.schema), indent=2, ensure_ascii=False))
        return 0

    failed = False
    for path in args.files:
        try:
            payload = _load(path)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{path}: cannot read JSON: {exc}", file=sys.stderr)
            failed = True
            continue
        problems = validate(args.schema, payload)
        if problems:
            failed = True
            print(f"{path}: INVALID ({len(problems)} problem(s))")
            for problem in problems:
                print(f"  {problem}")
        else:
            print(f"{path}: valid {args.schema}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

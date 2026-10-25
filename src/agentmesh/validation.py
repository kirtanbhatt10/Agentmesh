"""Load the AgentMesh JSON Schemas and validate payloads against them."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_NAMES = ("manifest", "task")

# In a source checkout or editable install the schemas live in the repo's specs/
# directory; in a built wheel they are bundled inside the package.
_REPO_SPECS = Path(__file__).resolve().parents[2] / "specs"


@dataclass(frozen=True)
class SchemaError:
    """One validation problem: where it is in the payload and what is wrong."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _read_schema_text(name: str) -> str:
    filename = f"{name}.schema.json"
    bundled = resources.files("agentmesh").joinpath("schemas", filename)
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8")
    return (_REPO_SPECS / filename).read_text(encoding="utf-8")


@cache
def load_schema(name: str) -> dict[str, Any]:
    """Return the parsed JSON Schema called ``name`` ("manifest" or "task")."""
    if name not in SCHEMA_NAMES:
        raise ValueError(f"unknown schema {name!r}; expected one of {', '.join(SCHEMA_NAMES)}")
    return json.loads(_read_schema_text(name))


@cache
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name), format_checker=FormatChecker())


def validate(name: str, payload: Any) -> list[SchemaError]:
    """Validate ``payload`` against schema ``name``; return the problems found (empty if valid)."""
    errors = sorted(_validator(name).iter_errors(payload), key=lambda e: list(e.absolute_path))
    return [
        SchemaError(path="$" + "".join(_format_part(p) for p in e.absolute_path), message=e.message)
        for e in errors
    ]


def validate_manifest(payload: Any) -> list[SchemaError]:
    """Validate an agent manifest."""
    return validate("manifest", payload)


def validate_task(payload: Any) -> list[SchemaError]:
    """Validate a task payload."""
    return validate("task", payload)


def _format_part(part: str | int) -> str:
    return f"[{part}]" if isinstance(part, int) else f".{part}"

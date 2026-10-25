"""AgentMesh: reference schemas and validators for the AgentMesh agent-to-agent protocol."""

from agentmesh.validation import (
    SCHEMA_NAMES,
    SchemaError,
    load_schema,
    validate,
    validate_manifest,
    validate_task,
)

__version__ = "0.1.0"

__all__ = [
    "SCHEMA_NAMES",
    "SchemaError",
    "__version__",
    "load_schema",
    "validate",
    "validate_manifest",
    "validate_task",
]

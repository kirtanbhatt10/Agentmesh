"""AgentMesh: schemas, validators and a reference implementation of the AgentMesh protocol."""

from agentmesh.validation import (
    SCHEMA_NAMES,
    SchemaError,
    load_schema,
    validate,
    validate_manifest,
    validate_task,
)

# isort: split
from agentmesh.lifecycle import (
    ErrorCode,
    InvalidTaskPayload,
    InvalidTransition,
    can_transition,
    is_terminal,
    new_task,
    transition,
)

# isort: split
from agentmesh._http import AgentMeshHTTPError
from agentmesh.agent import Agent, TaskFailure, TaskInfo, TaskResult
from agentmesh.client import AgentClient, ProtocolError, RegistryClient, TaskTimeout
from agentmesh.registry import Registry

__version__ = "0.2.0"

__all__ = [
    "SCHEMA_NAMES",
    "Agent",
    "AgentClient",
    "AgentMeshHTTPError",
    "ErrorCode",
    "InvalidTaskPayload",
    "InvalidTransition",
    "ProtocolError",
    "Registry",
    "RegistryClient",
    "SchemaError",
    "TaskFailure",
    "TaskInfo",
    "TaskResult",
    "TaskTimeout",
    "__version__",
    "can_transition",
    "is_terminal",
    "load_schema",
    "new_task",
    "transition",
    "validate",
    "validate_manifest",
    "validate_task",
]

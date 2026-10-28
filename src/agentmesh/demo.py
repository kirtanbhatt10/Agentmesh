"""Three-agent demo: an Orchestrator delegates to a Researcher and a Writer over HTTP.

Everything runs locally and offline: the Researcher looks topics up in a small built-in
set of notes about AgentMesh itself and the Writer formats them as Markdown. No LLM, API
key or network access beyond ``127.0.0.1`` is needed. Swap the handlers for real model
calls to turn this into a working pipeline.

Run it with ``agentmesh demo "how do agents discover each other?"``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from agentmesh.agent import Agent, TaskFailure, TaskInfo, TaskResult
from agentmesh.client import AgentClient, RegistryClient
from agentmesh.lifecycle import COMPLETED, new_id
from agentmesh.registry import Registry

_DOCS = "https://github.com/kirtanbhatt10/Agentmesh/blob/main/docs"

NOTES: list[dict[str, str]] = [
    {
        "claim": "Each agent serves a self-describing manifest at GET /manifest listing its "
        "identity, version, capabilities and endpoints.",
        "source": f"{_DOCS}/agent-discovery.md",
    },
    {
        "claim": "A registry indexes manifests so an orchestrator can find agents by "
        "capability; it is an advisory index, never a message broker.",
        "source": f"{_DOCS}/agent-discovery.md",
    },
    {
        "claim": "Tasks are delegated asynchronously: the delegator submits a task, then polls "
        "or receives webhooks until it reaches a terminal state.",
        "source": f"{_DOCS}/task-lifecycle.md",
    },
    {
        "claim": "A task moves from submitted to accepted or rejected, then executing, and "
        "ends completed, failed or timed out.",
        "source": f"{_DOCS}/task-lifecycle.md",
    },
    {
        "claim": "Every task in one workflow shares a conversation_id while each delegated "
        "unit of work has its own task_id, so out-of-order results can be correlated.",
        "source": f"{_DOCS}/protocol-overview.md",
    },
    {
        "claim": "Errors are structured protocol payloads with a machine-readable code, a "
        "message and a retryable hint, not just HTTP status codes.",
        "source": f"{_DOCS}/protocol-overview.md",
    },
    {
        "claim": "Constraints such as deadlines, output formats and result size limits must "
        "be honored or the task rejected explicitly.",
        "source": f"{_DOCS}/protocol-overview.md",
    },
    {
        "claim": "AgentMesh targets agent-to-agent coordination, while MCP targets "
        "application-to-tool integration; the two can coexist.",
        "source": "https://github.com/kirtanbhatt10/Agentmesh#readme",
    },
    {
        "claim": "The protocol is model- and language-agnostic: agents may run any LLM "
        "runtime and be written in any language that speaks HTTP and JSON.",
        "source": f"{_DOCS}/architecture.md",
    },
]

_STOPWORDS = frozenset(
    "a an and are as at be by can do does each for from how in is it its of on or the "
    "their them they this to what when where which who why with agentmesh".split()
)


def _normalise(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return {_normalise(w) for w in words if w not in _STOPWORDS}


def _related(a: str, b: str) -> bool:
    """Crude prefix stemming: "discover" ~ "discovery", "delegate" ~ "delegated"."""
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    return len(shorter) >= 4 and longer.startswith(shorter)


def _score(query_terms: set[str], text: str) -> int:
    note_terms = _terms(text)
    return sum(1 for q in query_terms if any(_related(q, n) for n in note_terms))


def research(context: dict[str, Any]) -> TaskResult:
    """Return the notes that best match ``context['query']``."""
    query = context.get("query")
    if not isinstance(query, str) or not query.strip():
        raise TaskFailure("invalid_context", "context.query must be a non-empty string")
    max_sources = context.get("max_sources", 3)
    if not isinstance(max_sources, int) or isinstance(max_sources, bool) or max_sources < 1:
        raise TaskFailure("invalid_context", "context.max_sources must be a positive integer")
    wanted = _terms(query)
    scored = []
    for index, note in enumerate(NOTES):
        score = _score(wanted, note["claim"])
        if score:
            scored.append((-score, index, note))
    findings = [dict(note) for _, _, note in sorted(scored)[:max_sources]]
    summary = f"{len(findings)} note(s) matched {query!r}."
    return TaskResult(data={"query": query, "findings": findings}, summary=summary)


def write_report(context: dict[str, Any]) -> TaskResult:
    """Turn ``context['findings']`` into a short Markdown report."""
    title = context.get("title") or "Report"
    findings = context.get("findings")
    if not isinstance(findings, list):
        raise TaskFailure("invalid_context", "context.findings must be a list")
    lines = [f"# {title}", ""]
    if findings:
        lines.append("## Key points")
        lines.append("")
        for number, finding in enumerate(findings, start=1):
            lines.append(f"{number}. {finding.get('claim', '')} [{number}]")
        lines += ["", "## Sources", ""]
        for number, finding in enumerate(findings, start=1):
            lines.append(f"[{number}] {finding.get('source', 'unknown')}")
    else:
        lines.append("No findings were available for this topic.")
    report = "\n".join(lines) + "\n"
    return TaskResult(data={"report": report}, summary=f"Report with {len(findings)} point(s).")


def make_researcher() -> Agent:
    agent = Agent(
        "researcher",
        version="0.2.0",
        description="Demo researcher: looks topics up in built-in notes about AgentMesh.",
    )
    agent.add_capability(
        "research",
        research,
        description="Return notes matching a query, with sources (offline demo data).",
        input_hint='{ "query": string, "max_sources": integer }',
        output_hint='{ "query": string, "findings": [ { "claim": string, "source": url } ] }',
    )
    return agent


def make_writer() -> Agent:
    agent = Agent(
        "writer",
        version="0.2.0",
        description="Demo writer: turns findings into a Markdown report.",
    )
    agent.add_capability(
        "document-writing",
        write_report,
        description="Write a Markdown report from a title and a list of findings.",
        input_hint='{ "title": string, "findings": [ { "claim": string, "source": url } ] }',
        output_hint='{ "report": markdown string }',
        output_formats=("json", "markdown"),
    )
    return agent


def make_orchestrator(registry_url: str, *, subtask_timeout: float = 30.0) -> Agent:
    """An orchestrator that discovers agents through the registry and chains them."""
    agent = Agent(
        "orchestrator",
        version="0.2.0",
        description="Demo orchestrator: researches a topic, then has it written up.",
    )
    registry = RegistryClient(registry_url)

    def delegate(capability: str, context: dict[str, Any], info: TaskInfo) -> dict[str, Any]:
        try:
            manifest = registry.find_one(capability)
        except LookupError as exc:
            raise TaskFailure("no_capable_agent", str(exc), retryable=True) from None
        constraints = {}
        if info.deadline is not None:
            constraints["deadline"] = info.deadline.isoformat().replace("+00:00", "Z")
        task = AgentClient.from_manifest(manifest).delegate(
            capability,
            context,
            conversation_id=info.conversation_id,
            constraints=constraints or None,
            timeout=subtask_timeout,
        )
        step = {
            "agent_id": manifest["agent_id"],
            "capability": capability,
            "task_id": task["task_id"],
            "status": task["status"],
        }
        if task["status"] != COMPLETED:
            error = task["error"]
            raise TaskFailure(
                "delegation_failed",
                f"{capability} task {task['task_id']} {task['status']}: "
                f"{error['code']}: {error['message']}",
                retryable=bool(error.get("retryable", False)),
            )
        return {"step": step, "data": task["result"]["data"]}

    def report(context: dict[str, Any], info: TaskInfo) -> TaskResult:
        topic = context.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            raise TaskFailure("invalid_context", "context.topic must be a non-empty string")
        research_out = delegate(
            "research", {"query": topic, "max_sources": context.get("max_sources", 3)}, info
        )
        writing_out = delegate(
            "document-writing",
            {"title": topic.strip(), "findings": research_out["data"]["findings"]},
            info,
        )
        return TaskResult(
            data={
                "topic": topic,
                "report": writing_out["data"]["report"],
                "trace": [research_out["step"], writing_out["step"]],
            },
            summary=f"Report on {topic!r} assembled from 2 delegated tasks.",
        )

    agent.add_capability(
        "report",
        report,
        description="Research a topic and return a written report.",
        input_hint='{ "topic": string, "max_sources": integer }',
        output_hint='{ "topic": string, "report": markdown string, "trace": [ ... ] }',
    )
    return agent


def run_demo(
    topic: str,
    *,
    max_sources: int = 3,
    timeout: float = 60.0,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Start a registry and three agents on free local ports, run one report, shut down.

    Returns the orchestrator's final task payload.
    """
    say = log or (lambda message: None)
    servers = []
    try:
        registry_server = Registry().serve()
        servers.append(registry_server)
        say(f"registry      {registry_server.url}")
        for name, agent in (
            ("researcher", make_researcher()),
            ("writer", make_writer()),
            ("orchestrator", make_orchestrator(registry_server.url)),
        ):
            server = agent.serve(registry_url=registry_server.url)
            servers.append(server)
            say(f"{name:<13} {server.url}  ({', '.join(agent.capabilities)})")

        registry = RegistryClient(registry_server.url)
        orchestrator = AgentClient.from_manifest(registry.find_one("report"))
        conversation_id = new_id("conv")
        say(f"conversation  {conversation_id}")
        return orchestrator.delegate(
            "report",
            {"topic": topic, "max_sources": max_sources},
            conversation_id=conversation_id,
            timeout=timeout,
        )
    finally:
        for server in reversed(servers):
            server.close()

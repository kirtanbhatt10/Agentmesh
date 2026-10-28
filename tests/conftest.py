"""Shared fixtures: start reference servers on free local ports and always stop them."""

from __future__ import annotations

import pytest

from agentmesh import Agent, AgentClient, Registry


@pytest.fixture
def serve():
    """Call ``serve(agent_or_registry, **kwargs)`` to start it; servers close after the test."""
    servers = []

    def _serve(service, **kwargs):
        server = service.serve(**kwargs)
        servers.append(server)
        return server

    yield _serve
    for server in reversed(servers):
        server.close()


@pytest.fixture
def echo_agent() -> Agent:
    agent = Agent("echo", description="Echoes its context.")

    @agent.capability("echo", output_formats=("json", "markdown"))
    def echo(context, info):
        return {"echo": context, "attempt": info.attempt}

    return agent


@pytest.fixture
def echo_client(serve, echo_agent) -> AgentClient:
    return AgentClient(serve(echo_agent).url)


@pytest.fixture
def registry_url(serve) -> str:
    return serve(Registry()).url

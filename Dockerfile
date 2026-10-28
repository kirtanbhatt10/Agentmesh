# AgentMesh reference services (registry and demo agents), standard library only.
#   docker build -t agentmesh:local .
#   docker run --rm -p 8500:8500 agentmesh:local                # registry on :8500
#   docker run --rm agentmesh:local agentmesh demo              # self-contained demo
#   docker compose up                                           # registry + 3 agents
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY specs ./specs
COPY src ./src
RUN pip install . && useradd --create-home --uid 10001 agentmesh

USER agentmesh
EXPOSE 8500
CMD ["agentmesh", "registry", "--host", "0.0.0.0", "--port", "8500"]

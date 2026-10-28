"""Build your own AgentMesh agent in ~40 lines.

Run it:  python examples/custom_agent.py

It starts a "text-stats" agent on a free local port, delegates one task to it over HTTP
the way any other agent would, prints the outcome and shuts down. Replace the handler
body with a call to your model or service of choice.
"""

from agentmesh import Agent, AgentClient, TaskFailure, TaskResult

agent = Agent(
    "text-stats",
    version="1.0.0",
    description="Counts words and sentences in a piece of text.",
)


@agent.capability(
    "text-statistics",
    description="Word, sentence and character counts for context.text.",
    input_hint='{ "text": string }',
    output_hint='{ "words": integer, "sentences": integer, "characters": integer }',
)
def text_statistics(context, info):
    text = context.get("text")
    if not isinstance(text, str) or not text.strip():
        # A structured, non-retryable protocol error instead of a stack trace.
        raise TaskFailure("invalid_context", "context.text must be a non-empty string")
    sentences = sum(text.count(mark) for mark in ".!?") or 1
    data = {"words": len(text.split()), "sentences": sentences, "characters": len(text)}
    return TaskResult(data=data, summary=f"{data['words']} words in task {info.task_id}")


if __name__ == "__main__":
    with agent.serve(port=0) as server:  # port=0 picks any free port
        client = AgentClient(server.url)
        print("manifest:", client.manifest()["capabilities"][0]["capability_id"])

        done = client.delegate("text-statistics", {"text": "Agents talk. Peers delegate!"})
        print(done["status"], done["result"])

        failed = client.delegate("text-statistics", {"text": ""})
        print(failed["status"], failed["error"])

        rejected = client.delegate("translate", {"text": "hola"})
        print(rejected["status"], rejected["error"]["code"])

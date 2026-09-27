"""AgentCore Runtime entrypoint.
"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from graph import invoke_agent

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict):
    """AgentCore Runtime entrypoint.

    Expected payload shape: {"prompt": "<user message>", "thread_id": "<optional>"}
    thread_id ties consecutive turns to the same conversation so the
    LangGraph checkpointer can resume slot-filling (e.g. a missing order ID).
    """
    print(f"invoke | payload={payload}")
    return invoke_agent(payload.get("prompt", ""), payload.get("thread_id"))


if __name__ == "__main__":
    app.run()

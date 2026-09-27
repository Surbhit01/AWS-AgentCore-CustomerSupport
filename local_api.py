"""Minimal local FastAPI server for testing the agent without AgentCore.

Mirrors agentcore_app.py's entrypoint (via graph.invoke_agent) but exposed
as a plain HTTP API. Run with:

    uvicorn local_api:app --reload

Then use the interactive Swagger UI at http://127.0.0.1:8000/docs to send
requests, or curl:

    curl -X POST http://127.0.0.1:8000/chat \\
        -H "Content-Type: application/json" \\
        -d '{"prompt": "What is your return policy?"}'
"""
from fastapi import FastAPI
from pydantic import BaseModel

from graph import invoke_agent

app = FastAPI(title="Customer Support Agent (local)")


class ChatRequest(BaseModel):
    prompt: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the agent. Reuse the same thread_id across calls
    to continue a conversation (e.g. after the agent asks for an order ID)."""
    result = invoke_agent(request.prompt, request.thread_id)
    return ChatResponse(**result)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

"""LangGraph definition for the customer support agent.

Standard ReAct-style shape: agent node (LLM decides) -> conditional edge ->
tool node -> back to agent node -> END once the LLM has what it needs.

Uses LangGraph's prebuilt ToolNode with handle_tool_errors=True so a tool
exception (see tools.get_order_status's ERR001 case) becomes a ToolMessage
the agent can react to gracefully, instead of crashing the graph.
"""
import uuid

from langchain_aws import ChatBedrockConverse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

import config
from config import logger
from tools import get_order_status, lookup_faq

SYSTEM_PROMPT = """You are a helpful customer support agent for an online store.

You have two tools:
- lookup_faq: for general questions (return policy, refunds, shipping, account/password, contact info)
- get_order_status: for checking the status of a specific order, which requires an order ID

Rules:
- If a request needs an order ID and the user hasn't given one, ask them for it directly.
  Never guess, assume, or invent an order ID.
- If a request needs both a policy answer and an order lookup (e.g. "I want to return
  order #A1023"), call both tools and combine the results into one clear answer.
- If a tool reports an error or that something wasn't found, relay that clearly to the
  user and suggest what they can do next (e.g. double-check the order ID).
- Keep answers concise and friendly.
"""

TOOLS = [lookup_faq, get_order_status]


def _agent_node(state: MessagesState):
    model = ChatBedrockConverse(model=config.MODEL_ID, provider=config.MODEL_PROVIDER).bind_tools(TOOLS)
    messages = state["messages"]
    if not messages or messages[0].type != "system":
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(messages)
    logger.info("agent node invoked | num_messages=%d", len(messages))
    response = model.invoke(messages)
    return {"messages": [response]}


def build_graph():
    graph_builder = StateGraph(MessagesState)

    graph_builder.add_node("agent", _agent_node) # node 1 
    graph_builder.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True)) # node 2

    graph_builder.set_entry_point("agent") # agent node is the entry point
    graph_builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph_builder.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph_builder.compile(checkpointer=checkpointer)


# Module-level compiled graph, reused by agentcore_app.py, local_api.py, and tests.
graph = build_graph()


def invoke_agent(prompt: str, thread_id: str | None = None) -> dict:
    """Run one turn through the graph."""
    thread_id = thread_id or str(uuid.uuid4())
    logger.info("invoke_agent | thread_id=%s prompt=%r", thread_id, prompt)

    try:
        logger.info("invoke_agent | Calling graph.invoke")
        result = graph.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:
        logger.exception("invoke_agent failed | thread_id=%s", thread_id)
        return {
            "response": (
                "Sorry, I couldn't process that request right now. "
                f"(error: {exc})"
            ),
            "thread_id": thread_id,
        }

    logger.info("invoke_agent completed | thread_id=%s result=%s", thread_id, result)
    final_message = result["messages"][-1]
    return {"response": final_message.content, "thread_id": thread_id}


def save_diagram(out_dir: str = ".") -> None:
    """Write the graph's mermaid source (and a rendered PNG, if reachable)
    to disk. Not called on import — run `python graph.py` to (re)generate
    these after changing the graph shape, e.g. for docs/recordings."""
    from pathlib import Path

    out_dir_path = Path(out_dir)
    mermaid_graph = graph.get_graph()

    mmd_path = out_dir_path / "graph_diagram.mmd"
    mmd_path.write_text(mermaid_graph.draw_mermaid())
    logger.info("wrote %s", mmd_path)

    png_path = out_dir_path / "graph_diagram.png"
    try:
        png_path.write_bytes(mermaid_graph.draw_mermaid_png())
        logger.info("wrote %s", png_path)
    except Exception:
        logger.warning(
            "could not render graph_diagram.png (needs internet access to "
            "mermaid.ink) — graph_diagram.mmd was still written",
            exc_info=True,
        )


if __name__ == "__main__":
    save_diagram()

"""Scripted local conversations exercising the agent's required behaviors.

Run with:  python -m tests.sample_conversations

These drive the compiled LangGraph graph directly (no AgentCore/AWS needed),
each scenario using a fixed thread_id so the checkpointer keeps state within
a scenario. Note: turns that reach the LLM (the agent node) require a valid
MODEL_ID and Bedrock access, which are intentionally left unset in
config.py — see README for how to fill those in before running this live.
"""
import uuid

from graph import invoke_agent


def run_turn(thread_id: str, user_text: str):
    print(f"  > {user_text}")
    result = invoke_agent(user_text, thread_id)
    print(f"  < {result['response']}")
    return result["response"]


def scenario_faq_only():
    print("\n[1] FAQ-only query")
    thread_id = str(uuid.uuid4())
    run_turn(thread_id, "What's your return policy?")


def scenario_order_status_only():
    print("\n[2] Order-status-only query")
    thread_id = str(uuid.uuid4())
    run_turn(thread_id, "Where's my order #A1023?")


def scenario_missing_order_id_followup():
    print("\n[3] Missing order ID -> follow-up resolution")
    thread_id = str(uuid.uuid4())
    run_turn(thread_id, "I want to return my order")
    run_turn(thread_id, "A1023")


def scenario_combined_query():
    print("\n[4] Combined query (both tools)")
    thread_id = str(uuid.uuid4())
    run_turn(thread_id, "I want to return order #A1023, what's the process?")


def scenario_tool_failure():
    print("\n[5] Simulated tool failure")
    thread_id = str(uuid.uuid4())
    run_turn(thread_id, "What's the status of order ERR001?")


if __name__ == "__main__":
    scenario_faq_only()
    scenario_order_status_only()
    scenario_missing_order_id_followup()
    scenario_combined_query()
    scenario_tool_failure()

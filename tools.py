"""Tool implementations for the customer support agent.

Both tools use hardcoded, in-memory data (no real backend) but are built to
behave sensibly under messy real-world input: mixed-case/whitespace IDs,
unrecognized queries, and a seeded failure case used to exercise LangGraph's
built-in tool-error handling.
"""
import re

from langchain_core.tools import tool

from config import logger
from db import get_order

# ---------------------------------------------------------------------------
# FAQ data + tool
# ---------------------------------------------------------------------------

FAQ_DATA = [
    {
        "keywords": ["return", "returns", "returning", "send back"],
        "answer": (
            "You can return most items within 30 days of delivery for a full "
            "refund. The item must be unused and in its original packaging."
        ),
    },
    {
        "keywords": ["refund", "refunds", "money back"],
        "answer": (
            "Refunds are processed within 5-7 business days after we receive "
            "your returned item, and issued to your original payment method."
        ),
    },
    {
        "keywords": ["shipping", "delivery time", "how long", "arrive"],
        "answer": (
            "Standard shipping takes 3-5 business days. Expedited shipping "
            "(1-2 business days) is available at checkout for an extra fee."
        ),
    },
    {
        "keywords": ["password", "account", "login", "log in", "sign in"],
        "answer": (
            "To reset your password, go to the login page and click 'Forgot "
            "Password'. You'll receive a reset link at your registered email."
        ),
    },
    {
        "keywords": ["contact", "support", "phone", "email us", "help desk"],
        "answer": (
            "You can reach customer support at support@example.com or "
            "1-800-555-0100, Monday-Friday, 9am-6pm ET."
        ),
    },
]

_FAQ_TOPICS = ["return policy", "refunds", "shipping times", "account/password help", "contact info"]


@tool
def lookup_faq(query: str) -> str:
    """Look up an answer to a customer's frequently-asked question.

    Args:
        query: The customer's question, in their own words.
    """
    logger.info("lookup_faq called | query=%r", query)
    normalized = query.lower()

    best_entry = None
    best_score = 0
    for entry in FAQ_DATA:
        score = sum(1 for kw in entry["keywords"] if kw in normalized)
        print(f"lookup_faq | entry_keywords={entry['keywords']} score={score} | query={query}")
        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry is None or best_score == 0:
        logger.info("lookup_faq no match | query=%r", query)
        return (
            "I couldn't find an answer to that in our FAQ. I can help with: "
            + ", ".join(_FAQ_TOPICS)
            + ". Could you rephrase your question around one of these topics?"
        )

    logger.info("lookup_faq matched | query=%r score=%d", query, best_score)
    return best_entry["answer"]


# ---------------------------------------------------------------------------
# Order status tool (backed by db.py / orders.db)
# ---------------------------------------------------------------------------

# Reserved ID that deliberately triggers the failure-simulation path below,
# to demonstrate LangGraph's handle_tool_errors behavior. Not present in the
# orders table.
_SIMULATED_FAILURE_ID = "ERR001"

_ORDER_ID_PATTERN = re.compile(r"^[A-Z]{1,3}\d{2,6}$")


@tool
def get_order_status(order_id: str) -> str:
    """Look up the shipping status of a customer's order.

    Args:
        order_id: The order ID, e.g. "A1023". Case and surrounding
            whitespace do not matter.
    """
    logger.info("get_order_status called | order_id=%r", order_id)
    # order # b2004 -> #B2004 -> B2004 
    normalized = order_id.strip().upper().lstrip("#")

    # Order ID does not match the expected pattern (1-3 letters followed by 2-6 digits)
    if not _ORDER_ID_PATTERN.match(normalized):
        logger.info("get_order_status malformed id | order_id=%r", order_id)
        return (
            f"'{order_id}' doesn't look like a valid order ID (expected a "
            "format like 'A1023'). Could you double-check and resend it?"
        )

    if normalized == _SIMULATED_FAILURE_ID:
        logger.error("get_order_status simulated failure | order_id=%r", normalized)
        raise RuntimeError(
            "Order lookup service is temporarily unavailable for this order."
        )

    order = get_order(normalized)
    if order is None:
        logger.info("get_order_status not found | order_id=%r", normalized)
        return f"I couldn't find an order with ID '{normalized}'. Please double-check the order ID."

    logger.info("get_order_status found | order_id=%r status=%r", normalized, order["status"])

    # ("A1050", "Priya Nair", "Shipped", "2026-09-01", "UPS", "2026-09-10", "Desk Lamp, USB Cable"), 
    parts = [
        f"Order {order['order_id']} (placed {order['order_date']}) is currently: {order['status']}.",
        f"Items: {order['items']}.",
    ]
    if order["status"] != "Delivered" and order["estimated_delivery"]:
        parts.append(f"Estimated delivery: {order['estimated_delivery']}.")
    if order["carrier"]:
        parts.append(f"Carrier: {order['carrier']}.")
    return " ".join(parts)

"""SQLite-backed order data store.

Still seed/demo data (no live backend integration) — but stored in a real
schema instead of a Python dict, with room for the fields a real order
lookup would carry: customer name, order date, carrier, and an estimated
delivery date. The table is created and seeded automatically on first
import; re-imports are a no-op if data already exists.
"""
import sqlite3
from pathlib import Path

from config import logger



DB_PATH = Path(__file__).parent / "orders.db"

# order_id, customer_name, status, order_date, carrier, estimated_delivery, items
_SEED_ORDERS = [
    ("A1023", "Jamie Chen", "Processing", "2026-09-05", None, "2026-09-15", "Wireless Mouse"),
    ("A1050", "Priya Nair", "Shipped", "2026-09-01", "UPS", "2026-09-10", "Desk Lamp, USB Cable"),
    ("A1099", "Miguel Santos", "Delivered", "2026-08-20", "FedEx", None, "Bluetooth Headphones"),
    ("B2004", "Alex Kim", "Shipped", "2026-09-03", "USPS", "2026-09-12", "Notebook Set"),
]


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                status TEXT NOT NULL,
                order_date TEXT NOT NULL,
                carrier TEXT,
                estimated_delivery TEXT,
                items TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", _SEED_ORDERS
            )
            conn.commit()
            logger.info("orders.db seeded with %d sample orders", len(_SEED_ORDERS))
    finally:
        conn.close()


def get_order(order_id: str) -> dict | None:
    """Return the order row as a dict, or None if not found."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


_init_db()

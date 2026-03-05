import sqlite3
from pathlib import Path
from contextlib import contextmanager

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "cargo.db"


def get_db_path():
    return str(DB_PATH)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate_clients(conn):
    try:
        conn.execute("SELECT 1 FROM clients LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("""
            CREATE TABLE clients (
                id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                telegram_chat_id TEXT,
                phone TEXT,
                created_at TEXT NOT NULL
            )
        """)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(shipments)").fetchall()]
    if "client_id" not in cols:
        conn.execute("ALTER TABLE shipments ADD COLUMN client_id TEXT")
    if "client_phone" not in cols:
        conn.execute("ALTER TABLE shipments ADD COLUMN client_phone TEXT")
    if "dispatch_notified" not in cols:
        conn.execute("ALTER TABLE shipments ADD COLUMN dispatch_notified INTEGER NOT NULL DEFAULT 0")
    if "delivery_notified" not in cols:
        conn.execute("ALTER TABLE shipments ADD COLUMN delivery_notified INTEGER NOT NULL DEFAULT 0")


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shipments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                tracking TEXT NOT NULL DEFAULT '',
                product_list TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                dispatch_date TEXT NOT NULL,
                delivery_date TEXT,
                status TEXT NOT NULL DEFAULT 'in_transit',
                shipping_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0,
                amount_to_pay REAL NOT NULL DEFAULT 0,
                cashback REAL NOT NULL DEFAULT 0,
                file1 TEXT,
                file2 TEXT,
                file3 TEXT,
                calculated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        _migrate_clients(conn)


def row_to_shipment(row) -> dict:
    d = {
        "id": row["id"],
        "title": row["title"] or "",
        "tracking": row["tracking"] or "",
        "product_list": row["product_list"] or "",
        "notes": row["notes"] or "",
        "dispatch_date": row["dispatch_date"],
        "delivery_date": row["delivery_date"],
        "status": row["status"],
        "shipping_type": row["shipping_type"],
        "weight": row["weight"],
        "amount_to_pay": row["amount_to_pay"],
        "cashback": row["cashback"],
        "file1": row["file1"],
        "file2": row["file2"],
        "file3": row["file3"],
        "calculated": bool(row["calculated"]),
        "created_at": row["created_at"],
    }
    try:
        d["dispatch_notified"] = bool(row["dispatch_notified"])
    except (KeyError, IndexError):
        d["dispatch_notified"] = False
    try:
        d["delivery_notified"] = bool(row["delivery_notified"])
    except (KeyError, IndexError):
        d["delivery_notified"] = False
    try:
        d["client_id"] = row["client_id"]
    except (KeyError, IndexError):
        d["client_id"] = None
    try:
        d["client_phone"] = row["client_phone"]
    except (KeyError, IndexError):
        d["client_phone"] = None
    try:
        d["client_name"] = row["client_name"]
    except (KeyError, IndexError):
        d["client_name"] = None
    return d


def row_to_client(row) -> dict:
    return {
        "id": row["id"],
        "full_name": row["full_name"] or "",
        "city": row["city"] or "",
        "telegram_chat_id": row["telegram_chat_id"],
        "phone": row["phone"],
        "created_at": row["created_at"],
    }

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .risk import evaluate_order

DEFAULT_DB = Path(__file__).resolve().parents[1] / "warehouse_rescue.db"
DB_PATH = Path(os.environ.get("WAREHOUSE_RESCUE_DB", DEFAULT_DB))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize() -> None:
    with database() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_json TEXT NOT NULL,
                received_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_events_order_time ON events(order_id, occurred_at);
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL UNIQUE,
                case_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)


def ingest(event: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
    event = dict(event)
    event["event_id"] = str(event["event_id"])
    event["occurred_at"] = event["occurred_at"].astimezone(timezone.utc).isoformat()
    encoded = json.dumps(event, separators=(",", ":"), sort_keys=True)
    received_at = datetime.now(timezone.utc).isoformat()

    with database() as connection:
        prior = connection.execute("SELECT case_json FROM cases WHERE order_id = ?", (event["order_id"],)).fetchone()
        cursor = connection.execute(
            "INSERT OR IGNORE INTO events(event_id, order_id, event_type, occurred_at, event_json, received_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event["event_id"], event["order_id"], event["event_type"], event["occurred_at"], encoded, received_at),
        )
        inserted = cursor.rowcount == 1
        if not inserted:
            return False, json.loads(prior["case_json"]) if prior else None

        rows = connection.execute("SELECT event_json FROM events WHERE order_id = ?", (event["order_id"],)).fetchall()
        history = [json.loads(row["event_json"]) for row in rows]
        case = evaluate_order(
            event["order_id"], history,
            now=datetime.now(timezone.utc),
            existing_case=prior is not None,
        )
        if case is not None:
            connection.execute(
                "INSERT INTO cases(case_id, order_id, case_json, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(order_id) DO UPDATE SET case_id=excluded.case_id, case_json=excluded.case_json, updated_at=excluded.updated_at",
                (case["case_id"], event["order_id"], json.dumps(case, separators=(",", ":")), received_at),
            )
        return True, case


def list_cases() -> list[dict[str, Any]]:
    with database() as connection:
        rows = connection.execute("SELECT case_json FROM cases ORDER BY updated_at DESC").fetchall()
    return [json.loads(row["case_json"]) for row in rows]


def refresh_cases(*, now: datetime | None = None) -> list[dict[str, Any]]:
    """Re-evaluate known orders as their carrier cutoffs approach, even without new events."""
    now = now or datetime.now(timezone.utc)
    changed: list[dict[str, Any]] = []
    with database() as connection:
        order_rows = connection.execute("SELECT DISTINCT order_id FROM events").fetchall()
        for order_row in order_rows:
            order_id = order_row["order_id"]
            rows = connection.execute("SELECT event_json FROM events WHERE order_id = ?", (order_id,)).fetchall()
            history = [json.loads(row["event_json"]) for row in rows]
            prior = connection.execute("SELECT case_json FROM cases WHERE order_id = ?", (order_id,)).fetchone()
            case = evaluate_order(order_id, history, now=now, existing_case=prior is not None)
            if case is None:
                continue
            if prior and json.loads(prior["case_json"]) == case:
                continue
            updated_at = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "INSERT INTO cases(case_id, order_id, case_json, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(order_id) DO UPDATE SET case_id=excluded.case_id, case_json=excluded.case_json, updated_at=excluded.updated_at",
                (case["case_id"], order_id, json.dumps(case, separators=(",", ":")), updated_at),
            )
            changed.append(case)
    return changed

"""
SQLite storage backend that provides a Firestore-compatible interface.

Drop-in replacement for firebase.py. All routers use:
    from firebase import db
We swap that import to point here instead, providing the same
collection/document/where/stream API backed by SQLite + JSON.
"""
import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Optional


from config import database_path

DB_PATH = database_path()
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """One connection per thread for thread safety."""
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(database_path(), check_same_thread=False)
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def _ensure_table(conn: sqlite3.Connection, collection: str) -> None:
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{collection}" '
        "(doc_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
    )
    conn.commit()


class DocumentSnapshot:
    """Mimics Firestore DocumentSnapshot."""

    def __init__(self, data: Optional[dict]):
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict:
        return self._data


class DocumentReference:
    """Mimics Firestore DocumentReference."""

    def __init__(self, collection: str, doc_id: str):
        self._collection = collection
        self._doc_id = doc_id

    def set(self, data: dict) -> None:
        conn = _get_conn()
        _ensure_table(conn, self._collection)
        serialised = json.dumps(data, default=_json_serialiser)
        conn.execute(
            f'INSERT OR REPLACE INTO "{self._collection}" (doc_id, data) VALUES (?, ?)',
            (self._doc_id, serialised),
        )
        conn.commit()

    def get(self) -> DocumentSnapshot:
        conn = _get_conn()
        _ensure_table(conn, self._collection)
        row = conn.execute(
            f'SELECT data FROM "{self._collection}" WHERE doc_id = ?',
            (self._doc_id,),
        ).fetchone()
        if row is None:
            return DocumentSnapshot(None)
        return DocumentSnapshot(json.loads(row[0]))

    def update(self, updates: dict) -> None:
        snap = self.get()
        if not snap.exists:
            return
        data = snap.to_dict()
        for key, value in updates.items():
            data[key] = value
        self.set(data)


class Query:
    """Mimics Firestore Query with chained .where() and .stream()."""

    def __init__(self, collection: str, filters: list[tuple]):
        self._collection = collection
        self._filters = filters

    def where(self, field: str, op: str, value: Any) -> "Query":
        return Query(self._collection, self._filters + [(field, op, value)])

    def stream(self) -> list[DocumentSnapshot]:
        conn = _get_conn()
        _ensure_table(conn, self._collection)
        rows = conn.execute(f'SELECT data FROM "{self._collection}"').fetchall()

        results = []
        for (raw,) in rows:
            data = json.loads(raw)
            if _matches_all(data, self._filters):
                results.append(DocumentSnapshot(data))
        return results


class CollectionReference:
    """Mimics Firestore CollectionReference."""

    def __init__(self, name: str):
        self._name = name

    def document(self, doc_id: str) -> DocumentReference:
        return DocumentReference(self._name, doc_id)

    def where(self, field: str, op: str, value: Any) -> Query:
        return Query(self._name, [(field, op, value)])

    def stream(self) -> list[DocumentSnapshot]:
        return Query(self._name, []).stream()


class Database:
    """Top-level object matching `db` from firebase.py."""

    def collection(self, name: str) -> CollectionReference:
        return CollectionReference(name)


# Module-level instance — routers import this
db = Database()


# --- helpers ---

def _resolve_nested(data: dict, dotted_key: str) -> Any:
    """Resolve a dotted key like 'party.name' against a nested dict."""
    parts = dotted_key.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _matches_all(data: dict, filters: list[tuple]) -> bool:
    """Check if a document matches all filter conditions."""
    for field, op, value in filters:
        actual = _resolve_nested(data, field)
        if not _compare(actual, op, value):
            return False
    return True


def _compare(actual: Any, op: str, value: Any) -> bool:
    if op == "==":
        return actual == value
    # For range comparisons, handle datetime strings
    if isinstance(actual, str) and isinstance(value, datetime):
        try:
            actual = datetime.fromisoformat(actual)
        except (ValueError, TypeError):
            return False
    if isinstance(actual, datetime) and isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return False
    if op == ">=":
        return actual >= value
    if op == "<=":
        return actual <= value
    if op == ">":
        return actual > value
    if op == "<":
        return actual < value
    return False


def _json_serialiser(obj: Any) -> str:
    """Handle datetime and enum serialisation for JSON."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

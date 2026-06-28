"""Persistent and in-memory review session storage."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, cast

from scope.schema_util import validate_artifact


class SessionStore(ABC):
    """Abstract interface for review session persistence."""

    @abstractmethod
    def save(self, artifact: dict[str, Any]) -> None:
        """Persist a session artifact keyed by session_id."""

    @abstractmethod
    def load(self, session_id: str) -> dict[str, Any]:
        """Load session artifact by ID; raise KeyError if missing."""

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """Return True if session exists."""

    @abstractmethod
    def status(self, session_id: str) -> dict[str, Any]:
        """Return session artifact summary for status queries."""


def _validate_session_artifact(artifact: dict[str, Any]) -> None:
    validate_artifact(artifact, "scope_review_session.schema.json")
    for vote in artifact.get("votes", []):
        validate_artifact(vote, "scope_reviewer_vote.schema.json")


class MemorySessionStore(SessionStore):
    """In-process session storage (default, non-durable)."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def save(self, artifact: dict[str, Any]) -> None:
        _validate_session_artifact(artifact)
        self._sessions[artifact["session_id"]] = dict(artifact)

    def load(self, session_id: str) -> dict[str, Any]:
        artifact = self._sessions.get(session_id)
        if artifact is None:
            raise KeyError(f"Unknown review session: {session_id}")
        return dict(artifact)

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def status(self, session_id: str) -> dict[str, Any]:
        return self.load(session_id)


class JsonFileSessionStore(SessionStore):
    """File-backed session storage (one JSON file per session)."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe_id = session_id.replace("/", "_")
        return self.directory / f"{safe_id}.json"

    def save(self, artifact: dict[str, Any]) -> None:
        _validate_session_artifact(artifact)
        path = self._path(artifact["session_id"])
        with path.open("w", encoding="utf-8") as fh:
            json.dump(artifact, fh, indent=2, sort_keys=True)
            fh.write("\n")

    def load(self, session_id: str) -> dict[str, Any]:
        path = self._path(session_id)
        if not path.exists():
            raise KeyError(f"Unknown review session: {session_id}")
        with path.open(encoding="utf-8") as fh:
            return cast(dict[str, Any], json.load(fh))

    def exists(self, session_id: str) -> bool:
        return self._path(session_id).exists()

    def status(self, session_id: str) -> dict[str, Any]:
        return self.load(session_id)


class SQLiteSessionStore(SessionStore):
    """SQLite-backed session storage for local durability."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_sessions (
                    session_id TEXT PRIMARY KEY,
                    artifact_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, artifact: dict[str, Any]) -> None:
        from datetime import datetime, timezone

        _validate_session_artifact(artifact)
        updated = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        payload = json.dumps(artifact, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_sessions (session_id, artifact_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    artifact_json = excluded.artifact_json,
                    updated_at = excluded.updated_at
                """,
                (artifact["session_id"], payload, updated),
            )
            conn.commit()

    def load(self, session_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT artifact_json FROM review_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown review session: {session_id}")
        return cast(dict[str, Any], json.loads(row["artifact_json"]))

    def exists(self, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM review_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row is not None

    def status(self, session_id: str) -> dict[str, Any]:
        return self.load(session_id)


def create_session_store(
    store_type: str,
    session_dir: str | Path | None = None,
) -> SessionStore:
    """Factory for session store backends."""
    normalized = store_type.lower()
    if normalized == "memory":
        return MemorySessionStore()
    if normalized == "json":
        return JsonFileSessionStore(session_dir or ".scope/sessions")
    if normalized == "sqlite":
        path = session_dir or ".scope/sessions.db"
        return SQLiteSessionStore(path)
    raise ValueError(f"Unknown session store type: {store_type}")

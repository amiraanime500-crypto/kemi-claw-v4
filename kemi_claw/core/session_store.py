"""Persistent agent session storage for resumable Kemi runs."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from typing import Any


class SessionStore:
    def __init__(self, root: str | None = None):
        self.root = root or os.getenv(
            "KEMI_SESSION_DIR",
            os.path.join(os.path.expanduser("~"), ".kemi", "sessions"),
        )
        os.makedirs(self.root, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, session_id: str) -> str:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:128]
        if not safe:
            raise ValueError("invalid session id")
        return os.path.join(self.root, safe + ".json")

    def save(self, session_id: str, state: dict[str, Any]) -> None:
        payload = dict(state)
        payload["updated_at"] = time.time()
        path = self._path(session_id)
        with self._lock:
            fd, tmp = tempfile.mkstemp(prefix=".session-", dir=self.root, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False, default=str)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)

    def load(self, session_id: str) -> dict[str, Any] | None:
        path = self._path(session_id)
        try:
            with self._lock, open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def delete(self, session_id: str) -> None:
        try:
            os.unlink(self._path(session_id))
        except FileNotFoundError:
            pass

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        items = []
        for name in os.listdir(self.root):
            if not name.endswith(".json"):
                continue
            state = self.load(name[:-5])
            if state:
                items.append(state)
        items.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return items[: max(1, min(int(limit), 500))]


session_store = SessionStore()

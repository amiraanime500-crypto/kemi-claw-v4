"""Durable trajectory events for replay, evaluation, and self-improvement."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .guardrails import bound_text, redact_secrets


class TrajectoryRecorder:
    def __init__(self, root: str | Path = ".kemi/trajectories", max_events: int = 2000):
        self.root = Path(root)
        self.max_events = max(100, max_events)

    def _path(self, session_id: str) -> Path:
        safe = "".join(c for c in str(session_id) if c.isalnum() or c in "._-")[:80] or "session"
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root / f"{safe}.jsonl"

    def record(self, session_id: str, event: str, payload: Any) -> None:
        item = {"ts": time.time(), "event": event, "payload": bound_text(redact_secrets(payload), 12000)}
        path = self._path(session_id)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        self._compact(path)

    def read(self, session_id: str, limit: int = 200) -> list[dict]:
        path = self._path(session_id)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
        out = []
        for line in lines:
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    out.append(value)
            except json.JSONDecodeError:
                continue
        return out

    def _compact(self, path: Path) -> None:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) > self.max_events:
                path.write_text("\n".join(lines[-self.max_events:]) + "\n", encoding="utf-8")
        except OSError:
            pass

"""Persistent cross-session memory backed by SQLite."""
import json
import sqlite3
import time

from ..config import settings


class Brain:
    def __init__(self, path: str = None):
        self.conn = sqlite3.connect(path or settings.brain_path)
        self._init_db()

    def _init_db(self):
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session TEXT, target TEXT, kind TEXT,
                content TEXT, created_at REAL)"""
        )
        self.conn.commit()

    def remember(self, session, target, kind, content):
        self.conn.execute(
            "INSERT INTO memory (session,target,kind,content,created_at) "
            "VALUES (?,?,?,?,?)",
            (session, target, kind, json.dumps(content), time.time()),
        )
        self.conn.commit()

    def recall(self, target=None, kind=None, limit=50):
        q = "SELECT session,target,kind,content,created_at FROM memory WHERE 1=1"
        args = []
        if target:
            q += " AND target=?"
            args.append(target)
        if kind:
            q += " AND kind=?"
            args.append(kind)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        rows = self.conn.execute(q, args).fetchall()
        return [
            {
                "session": r[0],
                "target": r[1],
                "kind": r[2],
                "content": json.loads(r[3]),
                "at": r[4],
            }
            for r in rows
        ]

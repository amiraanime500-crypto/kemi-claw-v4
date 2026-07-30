"""User storage in SQLite with hashed passwords."""
import os
import sqlite3

from .models import Role


class UserStore:
    def __init__(self, path=None):
        db_path = path or os.getenv("KEMI_USERS_DB", "./kemi_users.db")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.conn = sqlite3.connect(
            db_path, timeout=10
        )
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL)"""
        )
        self.conn.commit()

    def create(self, username, password_hash, role: Role):
        self.conn.execute(
            "INSERT INTO users (username,password_hash,role) VALUES (?,?,?)",
            (username, password_hash, role.value),
        )
        self.conn.commit()

    def get(self, username):
        row = self.conn.execute(
            "SELECT username,password_hash,role FROM users WHERE username=?",
            (username,),
        ).fetchone()
        if not row:
            return None
        return {"username": row[0], "password_hash": row[1], "role": row[2]}

    def list_users(self):
        rows = self.conn.execute("SELECT username,role FROM users").fetchall()
        return [{"username": r[0], "role": r[1]} for r in rows]

    def delete(self, username):
        self.conn.execute("DELETE FROM users WHERE username=?", (username,))
        self.conn.commit()

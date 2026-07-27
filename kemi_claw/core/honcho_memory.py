"""Honcho-style persistent memory."""
import os, time
from datetime import datetime
MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")

class HonchoMemory:
    def __init__(self):
        self.mem_file = os.path.join(MEMORY_DIR, "MEMORY.md")
        self._cache = {"users": {}, "scans": [], "facts": []}
        try:
            with open(self.mem_file) as fh:
                for line in fh:
                    if line.startswith("- Scan:"):
                        p = line.replace("- Scan:", "").strip().split("|")
                        if len(p) >= 2:
                            self._cache["scans"].append({"target": p[0].strip(), "rate": p[1].strip(), "ts": time.time()})
        except: pass

    def remember_user(self, uid, name=None):
        if uid not in self._cache["users"]:
            self._cache["users"][uid] = {"first_seen": time.time(), "interactions": 0, "name": name or f"User_{uid}"}
        self._cache["users"][uid]["interactions"] += 1
        if name: self._cache["users"][uid]["name"] = name

    def remember_scan(self, uid, target, goal, count, rate):
        self._cache["scans"].append({"uid": uid, "target": target, "goal": goal[:50], "count": count, "rate": rate, "ts": time.time()})
        if len(self._cache["scans"]) > 100: self._cache["scans"] = self._cache["scans"][-100:]
        with open(self.mem_file, "a") as fh:
            fh.write(f"- Scan: {target} | {rate:.0f}% | {datetime.utcnow().isoformat()[:19]}\n")

    def recall_scans(self, uid=None, limit=5):
        s = self._cache["scans"]
        if uid: s = [x for x in s if x.get("uid") == uid]
        return s[-limit:]

    def get_context(self, uid):
        u = self._cache["users"].get(uid, {})
        if not u.get("interactions"): return ""
        ctx = f"User {u.get('name','?')} — {u['interactions']} interactions."
        scans = self.recall_scans(uid, 3)
        if scans: ctx += " Last: " + ", ".join(f"{s['target']}({s.get('rate',0):.0f}%)" for s in scans)
        return ctx

memory = HonchoMemory()

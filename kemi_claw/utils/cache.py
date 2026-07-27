"""Smart caching + session management for Kemi agent."""
import os, json, time, hashlib
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def cache_key(target, tool_name, *args):
    raw = f"{target}:{tool_name}:{json.dumps(args, sort_keys=True)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def cache_get(target, tool_name, *args, max_age_seconds=3600):
    key = cache_key(target, tool_name, *args)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                data = json.load(f)
            age = time.time() - data.get("timestamp", 0)
            if age < max_age_seconds:
                return data.get("result")
        except: pass
    return None


def cache_set(target, tool_name, result, *args):
    key = cache_key(target, tool_name, *args)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(cache_file, "w") as f:
            json.dump({"timestamp": time.time(), "result": result, "target": target, "tool": tool_name}, f)
    except: pass


def cache_clear(target=None, tool_name=None):
    if target:
        for f in os.listdir(CACHE_DIR):
            path = os.path.join(CACHE_DIR, f)
            try:
                with open(path) as fh:
                    data = json.load(fh)
                if data.get("target") == target:
                    os.unlink(path)
            except: pass
    else:
        for f in os.listdir(CACHE_DIR):
            os.unlink(os.path.join(CACHE_DIR, f))


def cache_stats():
    files = os.listdir(CACHE_DIR)
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    return {"entries": len(files), "size_bytes": total_size, "size_mb": round(total_size / 1e6, 2)}


class SessionManager:
    """Manage scan sessions — pause, resume, track history."""
    
    def __init__(self, session_dir=None):
        self.session_dir = session_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sessions")
        os.makedirs(self.session_dir, exist_ok=True)
    
    def create_session(self, target, goal, tools=None):
        sid = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + hashlib.md5(target.encode()).hexdigest()[:6]
        session = {
            "id": sid, "target": target, "goal": goal, "tools": tools or [],
            "status": "created", "created_at": datetime.now().isoformat(),
            "steps_completed": 0, "steps_total": 0, "results": [],
        }
        self._save(sid, session)
        return sid
    
    def update_session(self, sid, **kwargs):
        session = self._load(sid)
        if session:
            session.update(kwargs)
            session["updated_at"] = datetime.now().isoformat()
            self._save(sid, session)
        return session
    
    def add_result(self, sid, result):
        session = self._load(sid)
        if session:
            session["results"].append(result)
            session["steps_completed"] = len(session["results"])
            session["updated_at"] = datetime.now().isoformat()
            self._save(sid, session)
        return session
    
    def get_session(self, sid):
        return self._load(sid)
    
    def list_sessions(self, status=None, limit=20):
        sessions = []
        for f in sorted(os.listdir(self.session_dir), reverse=True):
            if f.endswith(".json"):
                s = self._load(f.replace(".json", ""))
                if s and (status is None or s.get("status") == status):
                    sessions.append({"id": s["id"], "target": s["target"],
                                     "goal": s["goal"][:60], "status": s["status"],
                                     "created": s["created_at"][:19]})
            if len(sessions) >= limit: break
        return sessions
    
    def pause(self, sid):
        return self.update_session(sid, status="paused")
    
    def resume(self, sid):
        return self.update_session(sid, status="resumed")
    
    def complete(self, sid):
        return self.update_session(sid, status="completed", completed_at=datetime.now().isoformat())
    
    def _save(self, sid, data):
        path = os.path.join(self.session_dir, f"{sid}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load(self, sid):
        path = os.path.join(self.session_dir, f"{sid}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None


sessions = SessionManager()

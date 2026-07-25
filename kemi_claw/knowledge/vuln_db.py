"""Simple historical vulnerability knowledge interface (local JSON file)."""
import json
import os


class VulnKnowledge:
    def __init__(self, path="knowledge_base.json"):
        self.path = path
        self.data = json.load(open(path)) if os.path.exists(path) else []

    def match(self, service: str, version: str = ""):
        hits = []
        for v in self.data:
            if service.lower() in v.get("service", "").lower():
                if not version or version in v.get("affected", ""):
                    hits.append(v)
        return hits

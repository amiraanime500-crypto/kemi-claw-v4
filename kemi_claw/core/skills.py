"""Portable procedural skills with progressive disclosure."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class SkillStore:
    def __init__(self, root: str | Path = "skills"):
        self.root = Path(root)

    def list(self) -> list[dict[str, str]]:
        if not self.root.exists():
            return []
        result = []
        for path in sorted(self.root.glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            name = path.parent.name
            match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
            result.append({"name": name, "description": match.group(1).strip() if match else ""})
        return result

    def load(self, name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]", "", name)
        path = self.root / safe / "SKILL.md"
        if not path.is_file():
            raise FileNotFoundError(name)
        return path.read_text(encoding="utf-8", errors="replace")

    def save(self, name: str, content: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "", name)
        if not safe or not content.strip():
            raise ValueError("skill name and content are required")
        path = self.root / safe / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def index(self) -> str:
        """Return a compact model-facing index; full skills are loaded on demand."""
        return json.dumps(self.list(), ensure_ascii=False)

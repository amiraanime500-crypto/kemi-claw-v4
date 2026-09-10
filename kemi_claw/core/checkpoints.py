"""Bounded workspace snapshots for safe file-change rollback."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


class CheckpointStore:
    def __init__(self, root: str = ".kemi/checkpoints", max_checkpoints: int = 8):
        self.root = Path(root)
        self.max_checkpoints = max(1, min(int(max_checkpoints), 32))

    def create(self, paths: list[str], label: str = "checkpoint") -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        stamp = hashlib.sha256(f"{label}:{os.urandom(12).hex()}".encode()).hexdigest()[:16]
        destination = self.root / stamp
        destination.mkdir()
        manifest = {"id": stamp, "label": label, "files": []}
        for raw in paths[:128]:
            source = Path(raw)
            if not source.exists() or not source.is_file():
                continue
            safe_name = hashlib.sha256(str(source.resolve()).encode()).hexdigest() + ".bin"
            target = destination / safe_name
            shutil.copy2(source, target)
            manifest["files"].append({"path": str(source), "snapshot": safe_name})
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self._trim()
        return manifest

    def restore(self, checkpoint_id: str) -> dict:
        if not checkpoint_id or "/" in checkpoint_id or "\\" in checkpoint_id:
            raise ValueError("invalid checkpoint id")
        directory = self.root / checkpoint_id
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError("checkpoint not found")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        restored = []
        for item in manifest.get("files", []):
            target = Path(item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=".kemi-restore-")
            os.close(fd)
            try:
                shutil.copy2(directory / item["snapshot"], temp_name)
                os.replace(temp_name, target)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            restored.append(str(target))
        return {"id": checkpoint_id, "restored": restored}

    def _trim(self) -> None:
        checkpoints = sorted((p for p in self.root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in checkpoints[self.max_checkpoints:]:
            shutil.rmtree(old, ignore_errors=True)

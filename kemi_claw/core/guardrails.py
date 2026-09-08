"""Runtime policy and safety controls for Kemi's autonomous execution loop."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
]
_SENSITIVE_KEYS = re.compile(r"(?i)^(api[_-]?key|token|secret|password|authorization|access[_-]?token|refresh[_-]?token)$")

@dataclass(frozen=True)
class ExecutionPolicy:
    max_steps: int = 32
    max_retries: int = 2
    max_tool_output: int = 12000
    allow_dangerous_shell: bool = False
    allow_package_install: bool = True

    @classmethod
    def from_env(cls) -> "ExecutionPolicy":
        def integer(name: str, default: int, low: int, high: int) -> int:
            try:
                value = int(os.getenv(name, str(default)))
            except ValueError:
                value = default
            return max(low, min(value, high))
        return cls(
            max_steps=integer("KEMI_MAX_STEPS", 32, 1, 100),
            max_retries=integer("KEMI_MAX_RETRIES", 2, 0, 5),
            max_tool_output=integer("KEMI_MAX_TOOL_OUTPUT", 12000, 1000, 100000),
            allow_dangerous_shell=os.getenv("KEMI_ALLOW_DANGEROUS_SHELL", "0").lower() in {"1", "true", "yes", "on"},
            allow_package_install=os.getenv("KEMI_ALLOW_PACKAGE_INSTALL", "1").lower() in {"1", "true", "yes", "on"},
        )

    def check_tool(self, tool: str, args: dict[str, Any]) -> tuple[bool, str | None]:
        if tool == "pkg_install" and not self.allow_package_install:
            return False, "package installation is disabled by policy"
        if tool == "shell_exec" and not self.allow_dangerous_shell:
            command = str(args.get("command", "")).strip()
            if re.search(r"(?i)(^|[;&|])\s*(rm\s+-rf|mkfs(?:\.|\s)|dd\s+if=|shutdown\b|reboot\b|halt\b|poweroff\b|:\(\)\s*\{)", command):
                return False, "potentially destructive shell command blocked by policy"
        return True, None

def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): "[REDACTED]" if _SENSITIVE_KEYS.match(str(k)) else redact_secrets(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    if not isinstance(value, str):
        return value
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(lambda m: (m.group(1) + "=[REDACTED]") if m.lastindex and m.lastindex >= 2 else "[REDACTED]", result)
    return result

def bound_text(value: Any, limit: int) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "\n...[truncated]"
    if isinstance(value, dict):
        return {k: bound_text(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [bound_text(v, limit) for v in value]
    return value

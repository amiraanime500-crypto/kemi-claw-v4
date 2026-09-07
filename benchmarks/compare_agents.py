#!/usr/bin/env python3
"""Reproducible, safe adapter benchmark for Kemi and another agent.

The harness never chooses a target and never performs network activity itself.
Each adapter receives one JSON task on stdin and must print one JSON object on
stdout. Use the same model, prompt budget, timeout, and fixture data for both
agents. Example:

  python benchmarks/compare_agents.py \
    --kemi-command 'python benchmarks/adapters/kemi.py' \
    --hermes-command 'python benchmarks/adapters/hermes.py' \
    --output benchmark-results.json

This is deliberately a measurement tool, not a claim that Kemi is "1000x"
better. It reports raw counts, median, p95, and completeness so the claim can
be tested or rejected from evidence.
"""
from __future__ import annotations

import argparse
import json
import shlex
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASKS = [
    {
        "id": "structured_plan",
        "prompt": "Return a JSON plan for organizing a local documentation task.",
        "required": ("steps", "plan", "actions"),
    },
    {
        "id": "tool_selection",
        "prompt": "Choose one available read-only tool for checking a local JSON file.",
        "required": ("tool", "action", "selection"),
    },
    {
        "id": "error_recovery",
        "prompt": "A tool timed out. Return a safe retry or stop decision with a reason.",
        "required": ("retry", "recovery", "decision", "reason"),
    },
    {
        "id": "evidence_summary",
        "prompt": "Summarize three supplied observations without inventing facts.",
        "observations": ["status=200", "latency_ms=42", "header=present"],
        "required": ("summary", "evidence", "findings"),
    },
]


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * quantile))))
    return round(ordered[index], 2)


def parse_output(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # A plain text response is still useful for a completeness measurement.
        return text


def assess(task: dict[str, Any], output: Any, returncode: int) -> dict[str, Any]:
    if returncode != 0 or output is None:
        return {"passed": False, "complete": 0.0, "reason": "process_failed_or_empty"}
    if not isinstance(output, dict):
        return {"passed": False, "complete": 0.0, "reason": "non_json_object"}
    if output.get("error"):
        return {"passed": False, "complete": 0.0, "reason": "adapter_error"}
    keys = {str(key).lower() for key in output}
    matches = [candidate for candidate in task["required"] if candidate in keys]
    completeness = len(matches) / max(1, len(task["required"]))
    return {
        "passed": completeness >= 0.5,
        "complete": round(completeness, 3),
        "matched_fields": matches,
        "reason": "ok" if completeness >= 0.5 else "missing_expected_fields",
    }


def run_adapter(command: str, task: dict[str, Any], timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            shlex.split(command),
            input=(json.dumps(task, ensure_ascii=False) + "\n").encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        output = parse_output(completed.stdout.decode("utf-8", errors="replace"))
        assessment = assess(task, output, completed.returncode)
        result = {
            "task_id": task["id"],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "returncode": completed.returncode,
            **assessment,
        }
        if assessment["reason"] != "ok":
            result["stderr_tail"] = completed.stderr.decode("utf-8", errors="replace")[-300:]
        return result
    except subprocess.TimeoutExpired:
        return {
            "task_id": task["id"],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "passed": False,
            "complete": 0.0,
            "reason": "timeout",
        }
    except (OSError, ValueError) as exc:
        return {
            "task_id": task["id"],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "passed": False,
            "complete": 0.0,
            "reason": type(exc).__name__,
        }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(item["latency_ms"]) for item in results]
    return {
        "runs": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "pass_rate": round(sum(1 for item in results if item["passed"]) / max(1, len(results)), 3),
        "mean_completeness": round(statistics.mean(item["complete"] for item in results), 3) if results else 0.0,
        "median_latency_ms": percentile(latencies, 0.5),
        "p95_latency_ms": percentile(latencies, 0.95),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kemi-command", required=True, help="Command for the Kemi adapter")
    parser.add_argument("--hermes-command", required=True, help="Command for the Hermes adapter")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 100:
        parser.error("--iterations must be between 1 and 100")

    all_tasks = TASKS * args.iterations
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "tasks": [task["id"] for task in TASKS],
            "iterations": args.iterations,
            "timeout_seconds": args.timeout,
            "network_activity": "none by this harness",
        },
        "kemi": summarize([run_adapter(args.kemi_command, task, args.timeout) for task in all_tasks]),
        "hermes": summarize([run_adapter(args.hermes_command, task, args.timeout) for task in all_tasks]),
    }
    # Do not emit command strings: adapters often contain local paths or flags.
    report["comparison"] = {
        "pass_rate_delta": round(report["kemi"]["pass_rate"] - report["hermes"]["pass_rate"], 3),
        "median_latency_ratio_kemi_over_hermes": (
            round(report["kemi"]["median_latency_ms"] / report["hermes"]["median_latency_ms"], 3)
            if report["hermes"]["median_latency_ms"] else None
        ),
        "interpretation": "Inspect task-level results; aggregate ratios are not proof of superiority.",
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

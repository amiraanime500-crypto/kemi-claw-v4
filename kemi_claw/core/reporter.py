"""Build a Markdown report from session results."""
from datetime import datetime, timezone


def build_report(session, goal, target, results):
    lines = [
        "# Kemi-Claw Report",
        f"- Session: {session}",
        f"- Target: {target}",
        f"- Goal: {goal}",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Findings",
        "",
    ]
    for i, r in enumerate(results, 1):
        step = r.get("step", {})
        tool = step.get("tool", "?")
        rationale = step.get("rationale", "")
        lines.append(f"### {i}. {tool}")
        lines.append(f"_Rationale:_ {rationale}")
        lines.append("```")
        lines.append(str(r.get("result")))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)

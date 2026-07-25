import asyncio

from kemi_claw.core.brain import Brain
from kemi_claw.core.reporter import build_report


def test_brain_roundtrip(tmp_path):
    b = Brain(str(tmp_path / "t.db"))
    b.remember("s1", "t1", "note", {"x": 1})
    rows = b.recall(target="t1")
    assert rows and rows[0]["content"]["x"] == 1


def test_report_builds():
    rep = build_report(
        "s1",
        "goal",
        "t1",
        [{"step": {"tool": "nmap_scan"}, "result": {"ok": True}}],
    )
    assert "Kemi-Claw Report" in rep
    assert "nmap_scan" in rep


def test_registry_unknown_tool():
    from kemi_claw.tools.mcp_registry import registry

    res = asyncio.run(registry.call("does_not_exist", {}))
    assert "error" in res

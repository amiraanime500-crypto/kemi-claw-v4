import json

from kemi_claw.core.trajectory import TrajectoryRecorder
from kemi_claw.skills.manager import SkillManager


def test_skill_retrieval_prefers_relevant_skill(tmp_path):
    manager = SkillManager(tmp_path / "skills.json")
    manager.register("python-debug", "debug Python tests and inspect tracebacks", {"tags": "python tests"})
    manager.register("web-research", "research sources and summarize findings", {"tags": "web"})
    manager.evaluate("python-debug", 1.0, True)

    skills = manager.relevant("fix Python test traceback", limit=2)
    assert skills
    assert skills[0].name == "python-debug"


def test_skill_registry_round_trip(tmp_path):
    path = tmp_path / "skills.json"
    first = SkillManager(path)
    first.register("safe-edit", "make small reversible file edits")
    first.evaluate("safe-edit", 0.8, True)

    second = SkillManager(path)
    assert second.skills["safe-edit"].attempts == 1
    assert second.skills["safe-edit"].successes == 1


def test_trajectory_is_redacted_and_bounded(tmp_path):
    recorder = TrajectoryRecorder(tmp_path, max_events=100)
    recorder.record("abc", "step", {"token": "Bearer secret-value", "data": "x" * 20000})
    events = recorder.read("abc")
    assert len(events) == 1
    payload = json.dumps(events[0])
    assert "secret-value" not in payload
    assert len(payload) < 15000

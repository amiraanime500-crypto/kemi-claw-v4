"""Celery tasks that run the Kemi-Claw agent in the background."""
import asyncio

from .celery_app import celery_app
from ..core.agent import KemiClawAgent
import kemi_claw.tools.builtin_tools  # noqa: F401  (registers built-in tools)


@celery_app.task(bind=True, name="kemi.run_target")
def run_target(self, goal, target, provider=None, authorized=False):
    self.update_state(state="RUNNING", meta={"target": target, "goal": goal})
    agent = KemiClawAgent(provider)
    result = asyncio.run(agent.run(goal, target, authorized=authorized))
    return {
        "target": target,
        "session": result.get("session"),
        "report": result.get("report"),
    }


@celery_app.task(name="kemi.run_batch")
def run_batch(goal, targets, provider=None, authorized=False):
    """Fan a list of targets out across multiple workers."""
    if not authorized:
        return {"error": "target authorization not confirmed", "queued": []}
    job_ids = []
    for t in targets:
        async_res = run_target.delay(goal, t, provider, authorized)
        job_ids.append({"target": t, "task_id": async_res.id})
    return {"queued": job_ids}

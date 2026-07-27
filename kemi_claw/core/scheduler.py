"""Cron scheduler for periodic security scans."""
import asyncio, os, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()
_jobs = {}


async def add_scan_job(name, target, goal, chat_id, schedule="0 */6 * * *"):
    jid = f"kemi_{name}"
    
    async def _run():
        try:
            from kemi_claw.core.agent import KemiClawAgent
            from kemi_claw.integrations.telegram_bot import send_message
            agent = KemiClawAgent(provider="openai", model="meta/llama-3.1-8b-instruct")
            r = await agent.run(goal=goal, target=target, authorized=True)
            results = r.get("results", [])
            errs = sum(1 for x in results if isinstance(x.get("result"), dict) and "error" in x["result"])
            rate = (len(results) - errs) / max(len(results), 1) * 100
            await send_message(chat_id, f"Scheduled scan: {name}\nTarget: {target}\n{len(results)} steps | {int(rate)}% success")
        except Exception as e:
            print(f"[Scheduler] {name}: {e}")
    
    scheduler.add_job(_run, CronTrigger.from_crontab(schedule), id=jid, replace_existing=True)
    _jobs[name] = {"target": target, "goal": goal, "schedule": schedule, "chat_id": chat_id, "created": time.time()}
    if not scheduler.running:
        scheduler.start()
    return {"ok": True, "job": name, "schedule": schedule}


def list_jobs():
    return [{"name": k, **v} for k, v in _jobs.items()]


def remove_job(name):
    jid = f"kemi_{name}"
    try:
        scheduler.remove_job(jid)
    except: pass
    if name in _jobs:
        del _jobs[name]
    return {"removed": name, "ok": True}


def pause_job(name):
    jid = f"kemi_{name}"
    scheduler.pause_job(jid)
    return {"paused": name, "ok": True}


def resume_job(name):
    jid = f"kemi_{name}"
    scheduler.resume_job(jid)
    return {"resumed": name, "ok": True}

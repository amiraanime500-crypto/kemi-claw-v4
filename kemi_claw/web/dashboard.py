"""Web dashboard with RBAC: sessions view, batch launch, queue status."""
from celery.result import AsyncResult
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..auth.models import Role, User
from ..auth.security import require_role
from ..auth.routes import router as auth_router
from ..core.brain import Brain
from ..queue.celery_app import celery_app
from ..queue.tasks import run_batch

app = FastAPI(title="Kemi-Claw Dashboard", version="4.0")
app.include_router(auth_router)
templates = Jinja2Templates(directory="kemi_claw/web/templates")


class BatchRequest(BaseModel):
    goal: str
    targets: list
    provider: str | None = None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# viewer and above: read sessions
@app.get("/api/sessions")
async def sessions(user: User = Depends(require_role(Role.VIEWER))):
    return Brain().recall(kind="final", limit=50)


# operator and above: launch tasks
@app.post("/api/batch")
async def batch(
    req: BatchRequest, user: User = Depends(require_role(Role.OPERATOR))
):
    res = run_batch.delay(req.goal, req.targets, req.provider)
    return {"batch_task_id": res.id, "by": user.username}


@app.get("/api/task/{task_id}")
async def task_status(
    task_id: str, user: User = Depends(require_role(Role.VIEWER))
):
    r = AsyncResult(task_id, app=celery_app)
    return {"id": task_id, "state": r.state, "info": r.info}

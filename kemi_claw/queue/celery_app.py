"""Celery setup with Redis as broker and result backend."""
import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("kemi_claw", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=86400,
    task_soft_time_limit=900,
    task_time_limit=960,
    worker_prefetch_multiplier=1,
    imports=("kemi_claw.queue.tasks",),
)

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("autoapply", broker=REDIS_URL, backend=REDIS_URL)


@celery.task(name="scrape_task")
def scrape_task(company: str, limit: int = 10):
    from db import save_jobs
    from scraper import scrape_lever

    return {"saved": save_jobs(scrape_lever(company, limit))}

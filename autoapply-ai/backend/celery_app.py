import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("autoapply", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"], timezone="UTC")

if os.getenv("INGEST_INTERVAL_MINUTES"):
    celery.conf.beat_schedule = {
        "ingest-watchlists": {
            "task": "ingest_task",
            "schedule": float(os.getenv("INGEST_INTERVAL_MINUTES")) * 60,
        }
    }


@celery.task(name="scrape_task")
def scrape_task(company: str, limit: int = 10, user: str = "default"):
    from db import save_jobs
    from scraper import scrape_lever

    return {"saved": save_jobs(scrape_lever(company, limit), user)}


@celery.task(name="ingest_task")
def ingest_task(user: str = None):
    from db import profiles, save_jobs
    from scraper import scrape_lever

    query = {"user": user} if user else {"companies": {"$exists": True, "$ne": []}}
    saved, errors = 0, []
    for profile in profiles.find(query):
        for company in profile.get("companies", []):
            try:
                saved += save_jobs(scrape_lever(company, 10), profile["user"])
            except Exception as exc:
                errors.append(f"{company}: {exc}")
    return {"saved": saved, "errors": errors}


@celery.task(name="prepare_application_task")
def prepare_application_task(app_id: str):
    from pipeline import prepare_application

    prepare_application(app_id)


@celery.task(name="submit_application_task")
def submit_application_task(app_id: str):
    from pipeline import submit_application

    submit_application(app_id)

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
db = client[os.getenv("DB_NAME", "autoapply")]

profiles = db["profiles"]
resumes = db["resumes"]
jobs = db["jobs"]


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(doc):
    """Convert a Mongo document into something JSON-serializable."""
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


def save_jobs(items):
    """Upsert scraped jobs by URL so re-running a scrape never duplicates rows."""
    jobs.create_index("url", unique=True)
    for item in items:
        jobs.update_one(
            {"url": item["url"]},
            {"$set": item, "$setOnInsert": {"status": "new", "scraped_at": now()}},
            upsert=True,
        )
    return len(items)

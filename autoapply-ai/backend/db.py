import os
from datetime import datetime, timezone

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
db = client[os.getenv("DB_NAME", "autoapply")]

users = db["users"]
profiles = db["profiles"]
resumes = db["resumes"]
jobs = db["jobs"]
applications = db["applications"]
application_logs = db["application_logs"]

_jobs_index_ready = False


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(doc):
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


def ensure_jobs_index():
    global _jobs_index_ready
    if _jobs_index_ready:
        return
    try:
        jobs.drop_index("url_1")
    except Exception:
        pass
    jobs.create_index([("user", 1), ("url", 1)], unique=True)
    _jobs_index_ready = True


def ensure_indexes():
    ensure_jobs_index()
    users.create_index("email", unique=True)
    applications.create_index([("user", 1), ("job_id", 1)])
    application_logs.create_index("application_id")


def save_jobs(items, user="default"):
    ensure_jobs_index()
    for item in items:
        jobs.update_one(
            {"user": user, "url": item["url"]},
            {"$set": item, "$setOnInsert": {"status": "new", "scraped_at": now()}},
            upsert=True,
        )
    return len(items)


def log_event(application_id, event, detail=""):
    application_logs.insert_one(
        {"application_id": str(application_id), "event": event, "detail": detail, "at": now()}
    )


def set_application(application_id, **fields):
    applications.update_one({"_id": ObjectId(application_id)}, {"$set": {**fields, "updated_at": now()}})


def claim_legacy(user):
    profiles.update_many({"user": "default"}, {"$set": {"user": user}})
    resumes.update_many({"user": "default"}, {"$set": {"user": user}})
    jobs.update_many({"user": {"$exists": False}}, {"$set": {"user": user}})

from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import auth
import docgen
import generator
import matcher
from db import (
    application_logs,
    applications,
    claim_legacy,
    clean,
    ensure_indexes,
    jobs,
    log_event,
    now,
    profiles,
    resumes,
    save_jobs,
    set_application,
    users,
)
from pipeline import UPLOADS, slug
from resume_parser import extract_keywords, extract_text
from scraper import scrape_lever


@asynccontextmanager
async def lifespan(_):
    try:
        ensure_indexes()
    except Exception:
        pass
    yield


app = FastAPI(title="AutoApply AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ACTIVE = ["queued", "preparing", "pending_review", "approved", "submitting"]
MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "review": "image/png",
    "result": "image/png",
}


class Credentials(BaseModel):
    email: str
    password: str


class Profile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    current_company: str = ""
    target_titles: list[str] = []
    locations: list[str] = []
    companies: list[str] = []
    background: str = ""


class ScrapeRequest(BaseModel):
    company: str
    limit: int = 10


class ReviewEdits(BaseModel):
    answers: dict[str, str] = {}
    cover_note: Optional[str] = None


def oid(value):
    try:
        return ObjectId(value)
    except InvalidId:
        raise HTTPException(404, "Not found")


def owned(collection, doc_id, user):
    doc = collection.find_one({"_id": oid(doc_id), "user": user})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def register(creds: Credentials):
    email = creds.email.strip().lower()
    if "@" not in email or len(creds.password) < 8:
        raise HTTPException(400, "Enter a valid email and a password of at least 8 characters.")
    if users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists.")
    first_user = users.count_documents({}) == 0
    users.insert_one({"email": email, "password": auth.hash_password(creds.password), "created_at": now()})
    if first_user:
        claim_legacy(email)
    return {"token": auth.create_token(email), "email": email}


@app.post("/auth/login")
def login(creds: Credentials):
    email = creds.email.strip().lower()
    user = users.find_one({"email": email})
    if not user or not auth.verify_password(creds.password, user["password"]):
        raise HTTPException(401, "Incorrect email or password.")
    return {"token": auth.create_token(email), "email": email}


@app.get("/auth/me")
def me(user: str = Depends(auth.current_user)):
    return {"email": user}


@app.put("/profile")
def save_profile(profile: Profile, user: str = Depends(auth.current_user)):
    profiles.update_one({"user": user}, {"$set": {**profile.model_dump(), "updated_at": now()}}, upsert=True)
    return profile


@app.get("/profile")
def get_profile(user: str = Depends(auth.current_user)):
    doc = profiles.find_one({"user": user}) or {}
    return clean(doc) if doc else Profile().model_dump()


@app.post("/resume")
async def upload_resume(file: UploadFile = File(...), user: str = Depends(auth.current_user)):
    data = await file.read()
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not text:
        raise HTTPException(400, "No text could be extracted from this file.")
    keywords = extract_keywords(text)
    resumes.update_one(
        {"user": user},
        {"$set": {"filename": file.filename, "text": text, "keywords": keywords, "uploaded_at": now()}},
        upsert=True,
    )
    return {"filename": file.filename, "characters": len(text), "keywords": keywords}


@app.get("/resume")
def get_resume(user: str = Depends(auth.current_user)):
    doc = resumes.find_one({"user": user}, {"text": 0})
    return clean(doc) if doc else None


@app.post("/scrape")
def scrape(req: ScrapeRequest, user: str = Depends(auth.current_user)):
    try:
        items = scrape_lever(req.company.strip(), req.limit)
    except Exception as e:
        raise HTTPException(502, f"Scrape failed: {e}")
    return {"saved": save_jobs(items, user)}


@app.post("/scrape/async")
def scrape_async(req: ScrapeRequest, user: str = Depends(auth.current_user)):
    from celery_app import scrape_task

    task = scrape_task.delay(req.company.strip(), req.limit, user)
    return {"task_id": task.id}


@app.post("/ingest")
def ingest(user: str = Depends(auth.current_user)):
    from celery_app import ingest_task

    profile = profiles.find_one({"user": user}) or {}
    if not profile.get("companies"):
        raise HTTPException(400, "Add companies to your watchlist in your profile first.")
    return {"task_id": ingest_task.delay(user).id}


@app.get("/tasks/{task_id}")
def task_status(task_id: str, user: str = Depends(auth.current_user)):
    from celery_app import celery

    result = celery.AsyncResult(task_id)
    payload = result.result if result.successful() else str(result.result) if result.failed() else None
    return {"state": result.state, "result": payload}


@app.get("/jobs")
def list_jobs(user: str = Depends(auth.current_user)):
    docs = list(jobs.find({"user": user}, {"description": 0}).sort("match_score", -1))
    return [clean(d) for d in docs]


@app.post("/match-all")
def match_all(limit: int = 5, user: str = Depends(auth.current_user)):
    resume = resumes.find_one({"user": user})
    if not resume:
        raise HTTPException(400, "Upload a resume first.")
    profile = profiles.find_one({"user": user}) or {}
    pending = list(jobs.find({"user": user, "match_score": {"$exists": False}}).limit(limit))
    scored = 0
    for job in pending:
        try:
            result = matcher.score_job(profile, resume["text"], job)
        except Exception as e:
            raise HTTPException(502, f"Scoring failed after {scored} jobs: {e}")
        jobs.update_one({"_id": job["_id"]}, {"$set": result})
        scored += 1
    return {"scored": scored}


@app.post("/jobs/{job_id}/status")
def set_status(job_id: str, status: str, user: str = Depends(auth.current_user)):
    owned(jobs, job_id, user)
    jobs.update_one({"_id": oid(job_id)}, {"$set": {"status": status}})
    return {"ok": True}


@app.post("/jobs/{job_id}/resume")
def export_resume(job_id: str, format: str = "docx", user: str = Depends(auth.current_user)):
    if format not in ("docx", "pdf"):
        raise HTTPException(400, "Format must be docx or pdf.")
    job = owned(jobs, job_id, user)
    resume = resumes.find_one({"user": user})
    if not resume:
        raise HTTPException(400, "Upload a resume first.")
    profile = profiles.find_one({"user": user}) or {}
    try:
        tailored = generator.tailor_resume(profile, resume["text"], job)
    except Exception as e:
        raise HTTPException(502, f"Resume tailoring failed: {e}")
    build = docgen.build_docx if format == "docx" else docgen.build_pdf
    name = f"{slug(job.get('company'))}-{slug(job.get('title'))}-resume.{format}"
    return Response(
        build(profile, tailored),
        media_type=MEDIA[format],
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.post("/jobs/{job_id}/apply")
def apply_to_job(job_id: str, user: str = Depends(auth.current_user)):
    job = owned(jobs, job_id, user)
    existing = applications.find_one({"user": user, "job_id": job_id, "status": {"$in": ACTIVE + ["submitted", "dry_run"]}})
    if existing:
        return clean(existing)
    return clean(queue_application(job, user))


def queue_application(job, user):
    from celery_app import prepare_application_task

    doc = {
        "user": user,
        "job_id": str(job["_id"]),
        "title": job.get("title"),
        "company": job.get("company"),
        "url": job.get("url"),
        "match_score": job.get("match_score"),
        "status": "queued",
        "error": "",
        "created_at": now(),
        "updated_at": now(),
    }
    doc["_id"] = applications.insert_one(doc).inserted_id
    log_event(doc["_id"], "queued", "Added to the application queue")
    prepare_application_task.delay(str(doc["_id"]))
    return doc


@app.post("/apply-top")
def apply_top(min_score: int = 70, limit: int = 5, user: str = Depends(auth.current_user)):
    taken = {a["job_id"] for a in applications.find({"user": user, "status": {"$ne": "rejected"}}, {"job_id": 1})}
    candidates = jobs.find({"user": user, "match_score": {"$gte": min_score}}).sort("match_score", -1)
    queued = 0
    for job in candidates:
        if queued >= limit:
            break
        if str(job["_id"]) in taken:
            continue
        queue_application(job, user)
        queued += 1
    return {"queued": queued}


@app.get("/applications")
def list_applications(user: str = Depends(auth.current_user)):
    docs = applications.find({"user": user}, {"questions": 0, "tailored": 0}).sort("created_at", -1)
    return [clean(d) for d in docs]


@app.get("/applications/{app_id}")
def get_application(app_id: str, user: str = Depends(auth.current_user)):
    doc = owned(applications, app_id, user)
    logs = [clean(d) for d in application_logs.find({"application_id": app_id}).sort("at", 1)]
    return {**clean(doc), "logs": logs}


@app.put("/applications/{app_id}/review")
def edit_review(app_id: str, edits: ReviewEdits, user: str = Depends(auth.current_user)):
    doc = owned(applications, app_id, user)
    if doc["status"] != "pending_review":
        raise HTTPException(400, "This application is not awaiting review.")
    questions = doc.get("questions", [])
    for q in questions:
        if q["id"] in edits.answers:
            q["answer"] = edits.answers[q["id"]]
    fields = {"questions": questions}
    if edits.cover_note is not None:
        fields["cover_note"] = edits.cover_note
    set_application(app_id, **fields)
    log_event(app_id, "edited", "Answers updated by you")
    return {"ok": True}


@app.post("/applications/{app_id}/approve")
def approve(app_id: str, user: str = Depends(auth.current_user)):
    from celery_app import submit_application_task

    doc = owned(applications, app_id, user)
    if doc["status"] != "pending_review":
        raise HTTPException(400, "This application is not awaiting review.")
    missing = [q["label"] for q in doc.get("questions", []) if q.get("required") and not (q.get("answer") or "").strip()]
    if missing:
        raise HTTPException(400, f"Answer the required questions first: {'; '.join(missing)}")
    set_application(app_id, status="approved")
    log_event(app_id, "approved", "You approved this application")
    submit_application_task.delay(app_id)
    return {"ok": True}


@app.post("/applications/{app_id}/reject")
def reject(app_id: str, user: str = Depends(auth.current_user)):
    doc = owned(applications, app_id, user)
    if doc["status"] not in ("pending_review", "failed"):
        raise HTTPException(400, "This application can no longer be rejected.")
    set_application(app_id, status="rejected")
    log_event(app_id, "rejected", "You skipped this application")
    return {"ok": True}


@app.post("/applications/{app_id}/retry")
def retry(app_id: str, user: str = Depends(auth.current_user)):
    from celery_app import prepare_application_task

    doc = owned(applications, app_id, user)
    if doc["status"] != "failed":
        raise HTTPException(400, "Only failed applications can be retried.")
    set_application(app_id, status="queued", error="")
    log_event(app_id, "queued", "Retrying")
    prepare_application_task.delay(app_id)
    return {"ok": True}


@app.get("/applications/{app_id}/files/{kind}")
def application_file(app_id: str, kind: str, user: str = Depends(auth.current_user)):
    doc = owned(applications, app_id, user)
    name = (doc.get("files") or {}).get(kind)
    path = UPLOADS / app_id / name if name else None
    if not path or not path.exists():
        raise HTTPException(404, "File not found")
    download = f"{slug(doc.get('company'))}-{slug(doc.get('title'))}-{kind}{path.suffix}"
    return FileResponse(path, media_type=MEDIA[kind], filename=download)


@app.get("/stats")
def stats(user: str = Depends(auth.current_user)):
    all_jobs = list(jobs.find({"user": user}, {"match_score": 1, "missing_skills": 1, "company": 1}))
    scores = [j["match_score"] for j in all_jobs if "match_score" in j]
    apps = list(applications.find({"user": user}, {"status": 1, "created_at": 1}))
    missing = Counter(s.lower() for j in all_jobs for s in j.get("missing_skills", []))
    cutoff = datetime.now(timezone.utc) - timedelta(days=13)
    per_day = Counter()
    for a in apps:
        created = datetime.fromisoformat(a["created_at"])
        if created >= cutoff:
            per_day[created.date().isoformat()] += 1
    days = [(cutoff + timedelta(days=i)).date().isoformat() for i in range(14)]
    return {
        "jobs_total": len(all_jobs),
        "jobs_scored": len(scores),
        "avg_match": round(sum(scores) / len(scores)) if scores else 0,
        "applications_total": len(apps),
        "by_status": dict(Counter(a["status"] for a in apps)),
        "score_buckets": {
            "70+": sum(s >= 70 for s in scores),
            "40-69": sum(40 <= s < 70 for s in scores),
            "under 40": sum(s < 40 for s in scores),
        },
        "top_missing_skills": [{"skill": k, "count": v} for k, v in missing.most_common(8)],
        "applications_by_day": [{"date": d, "count": per_day.get(d, 0)} for d in days],
        "companies": dict(Counter(j["company"] for j in all_jobs if j.get("company")).most_common(6)),
    }

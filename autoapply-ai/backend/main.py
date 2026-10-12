from bson import ObjectId
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import matcher
from db import clean, jobs, now, profiles, resumes, save_jobs
from resume_parser import extract_keywords, extract_text
from scraper import scrape_lever

app = FastAPI(title="AutoApply AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

USER = "default"  # single-user for the checkpoint; auth is a next step


class Profile(BaseModel):
    name: str = ""
    target_titles: list[str] = []
    locations: list[str] = []
    background: str = ""


class ScrapeRequest(BaseModel):
    company: str
    limit: int = 10


@app.get("/health")
def health():
    return {"status": "ok"}


@app.put("/profile")
def save_profile(profile: Profile):
    profiles.update_one({"user": USER}, {"$set": {**profile.model_dump(), "updated_at": now()}}, upsert=True)
    return profile


@app.get("/profile")
def get_profile():
    doc = profiles.find_one({"user": USER}) or {}
    return clean(doc) if doc else Profile().model_dump()


@app.post("/resume")
async def upload_resume(file: UploadFile = File(...)):
    data = await file.read()
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not text:
        raise HTTPException(400, "No text could be extracted from this file.")
    keywords = extract_keywords(text)
    resumes.update_one(
        {"user": USER},
        {"$set": {"filename": file.filename, "text": text, "keywords": keywords, "uploaded_at": now()}},
        upsert=True,
    )
    return {"filename": file.filename, "characters": len(text), "keywords": keywords}


@app.get("/resume")
def get_resume():
    doc = resumes.find_one({"user": USER}, {"text": 0})
    return clean(doc) if doc else None


@app.post("/scrape")
def scrape(req: ScrapeRequest):
    try:
        items = scrape_lever(req.company.strip(), req.limit)
    except Exception as e:
        raise HTTPException(502, f"Scrape failed: {e}")
    return {"saved": save_jobs(items)}


@app.post("/scrape/async")
def scrape_async(req: ScrapeRequest):
    """Queue the scrape on Celery/Redis instead of blocking the web server."""
    from celery_app import scrape_task

    task = scrape_task.delay(req.company.strip(), req.limit)
    return {"task_id": task.id}


@app.get("/tasks/{task_id}")
def task_status(task_id: str):
    from celery_app import celery

    result = celery.AsyncResult(task_id)
    return {"state": result.state, "result": result.result if result.ready() else None}


@app.get("/jobs")
def list_jobs():
    docs = list(jobs.find({}, {"description": 0}).sort("match_score", -1))
    return [clean(d) for d in docs]


@app.post("/match-all")
def match_all(limit: int = 5):
    resume = resumes.find_one({"user": USER})
    if not resume:
        raise HTTPException(400, "Upload a resume first.")
    profile = profiles.find_one({"user": USER}) or {}
    pending = list(jobs.find({"match_score": {"$exists": False}}).limit(limit))
    for job in pending:
        result = matcher.score_job(profile, resume["text"], job)
        jobs.update_one({"_id": job["_id"]}, {"$set": result})
    return {"scored": len(pending)}


@app.post("/jobs/{job_id}/status")
def set_status(job_id: str, status: str):
    jobs.update_one({"_id": ObjectId(job_id)}, {"$set": {"status": status}})
    return {"ok": True}

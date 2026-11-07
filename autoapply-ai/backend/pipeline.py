import os
import re
from pathlib import Path

from bson import ObjectId

import applicator
import docgen
import generator
from db import applications, jobs, log_event, now, profiles, resumes, set_application

UPLOADS = Path(__file__).parent / "uploads"


def workdir(app_id):
    path = UPLOADS / str(app_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "resume"


def load(app_id):
    app = applications.find_one({"_id": ObjectId(app_id)})
    job = jobs.find_one({"_id": ObjectId(app["job_id"])})
    profile = profiles.find_one({"user": app["user"]}) or {}
    resume = resumes.find_one({"user": app["user"]})
    return app, job, profile, resume


def prepare_application(app_id):
    try:
        app, job, profile, resume = load(app_id)
        if job.get("source") != "lever":
            raise ValueError("Auto-fill currently supports Lever postings only.")
        if not resume:
            raise ValueError("Upload a resume first.")
        set_application(app_id, status="preparing", error="")
        log_event(app_id, "preparing", "Tailoring the resume and reading the application form")

        tailored = generator.tailor_resume(profile, resume["text"], job)
        folder = workdir(app_id)
        (folder / "resume.docx").write_bytes(docgen.build_docx(profile, tailored))
        (folder / "resume.pdf").write_bytes(docgen.build_pdf(profile, tailored))
        log_event(app_id, "resume_ready", "Tailored DOCX and PDF resumes generated")

        def answer(questions):
            if not questions:
                return questions
            answers = generator.answer_questions(profile, resume["text"], job, questions)
            for q in questions:
                q["answer"] = answers.get(q["id"], "")
            log_event(app_id, "answers_ready", f"{len(questions)} screening questions drafted")
            return questions

        result = applicator.run_form(
            job["url"],
            profile,
            str(folder / "resume.pdf"),
            tailored["cover_note"],
            str(folder / "review.png"),
            answer_fn=answer,
        )
        set_application(
            app_id,
            status="pending_review",
            questions=result["questions"],
            tailored=tailored,
            cover_note=tailored["cover_note"],
            files={"docx": "resume.docx", "pdf": "resume.pdf", "review": "review.png"},
        )
        log_event(app_id, "pending_review", "Form pre-filled. Waiting for your approval")
    except Exception as exc:
        set_application(app_id, status="failed", error=str(exc))
        log_event(app_id, "failed", str(exc))


def submit_application(app_id):
    try:
        app, job, profile, _ = load(app_id)
        if app["status"] != "approved":
            return
        live = os.getenv("SUBMIT_ENABLED", "false").lower() == "true"
        set_application(app_id, status="submitting")
        log_event(app_id, "submitting", "Submitting the application" if live else "Dry run: filling the form without submitting")
        folder = workdir(app_id)
        result = applicator.run_form(
            job["url"],
            profile,
            str(folder / "resume.pdf"),
            app.get("cover_note", ""),
            str(folder / "result.png"),
            questions=app.get("questions", []),
            submit=live,
        )
        files = {**app.get("files", {}), "result": "result.png"}
        if not live:
            set_application(app_id, status="dry_run", files=files, error="")
            log_event(app_id, "dry_run", "SUBMIT_ENABLED is false, so the form was not sent")
        elif result["submitted"]:
            set_application(app_id, status="submitted", files=files, submitted_at=now(), error="")
            jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "applied"}})
            log_event(app_id, "submitted", result["message"])
        else:
            set_application(app_id, status="failed", files=files, error=result["message"])
            log_event(app_id, "failed", result["message"])
    except Exception as exc:
        set_application(app_id, status="failed", error=str(exc))
        log_event(app_id, "failed", str(exc))

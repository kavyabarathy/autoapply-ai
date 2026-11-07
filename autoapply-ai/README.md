# AutoApply AI

Automated job application and matching platform (KTP capstone).

## Run it

### 1. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
cp .env.example .env             # Windows PowerShell: Copy-Item .env.example .env
uvicorn main:app --reload --port 8000
```
Fill in `.env` first: `MONGODB_URI`, `JWT_SECRET`, and the LLM key. 

API docs: http://localhost:8000/docs

### 2. Redis and Celery worker (required for applications)
```bash
docker run -p 6379:6379 redis
cd backend
celery -A celery_app.celery worker --loglevel=info --pool=solo
```
Optional automatic watchlist ingestion: set `INGEST_INTERVAL_MINUTES` in `.env`, then run `celery -A celery_app.celery beat --loglevel=info` in a third terminal.

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 and register an account.

## How it works
1. Profile tab: add contact details, target titles, locations, a watchlist of Lever companies, and upload your master resume.
2. Jobs tab: scrape or queue a Lever company (for example `palantir`), ingest the watchlist, then score jobs with the LLM.
3. Press Apply on a job, or Apply to top matches. A Celery worker tailors your resume (DOCX and PDF), drafts answers to screening questions, and pre-fills the Lever form with Playwright.
4. Applications tab: review the screenshot, edit answers, then Approve and submit. Nothing is sent before approval.
5. Dashboard tab: analytics on jobs, scores, skill gaps, and application statuses.

`SUBMIT_ENABLED=false` (default) makes approval run a dry run that fills the form but does not send it. Set it to `true` to submit for real. Sites that show a captcha may block automated submission, in which case the application is marked failed with a message.

## Status
Done: React dashboard, FastAPI, MongoDB, JWT auth, resume parsing, Playwright scraper, LLM match scoring, Celery + Redis queue, python-docx and PDF resume export, form auto-fill, Review & Submit, application logs, analytics.

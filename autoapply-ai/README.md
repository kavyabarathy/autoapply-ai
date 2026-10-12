# AutoApply AI

Automated job application and matching platform.

## Run it

### 1. Backend
```bash
cd backend
python -m venv .venv && source .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # then fill in MONGODB_URI and GEMINI_API_KEY
uvicorn main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

### 3. Optional: Celery + Redis
```bash
docker run -p 6379:6379 redis
cd backend && celery -A celery_app.celery worker --loglevel=info --pool=solo
```
Then `POST /scrape/async` queues the scrape and `GET /tasks/{id}` reports status.

## Status
Done: React dashboard, FastAPI, MongoDB, resume parsing, Playwright scraper, LLM match scoring.
Next: Celery integration in the UI, python-docx resume export, form auto-fill, Review & Submit, auth.

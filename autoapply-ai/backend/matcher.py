import json
import os

from openai import OpenAI

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from the environment
    return _client


SYSTEM = (
    "You are a recruiter assistant. Compare a candidate to a job posting. "
    "Respond ONLY with JSON: "
    '{"score": <integer 0-100>, "reason": "<one sentence>", "missing_skills": ["..."]}'
)


def score_job(profile: dict, resume_text: str, job: dict) -> dict:
    user = (
        f"CANDIDATE TARGET TITLES: {profile.get('target_titles', [])}\n"
        f"CANDIDATE BACKGROUND: {profile.get('background', '')}\n"
        f"RESUME:\n{resume_text[:4000]}\n\n"
        f"JOB TITLE: {job.get('title')}\n"
        f"JOB DESCRIPTION:\n{job.get('description', '')[:4000]}"
    )
    resp = _get_client().chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    data = json.loads(resp.choices[0].message.content)
    return {
        "match_score": int(data.get("score", 0)),
        "match_reason": data.get("reason", ""),
        "missing_skills": data.get("missing_skills", []),
    }

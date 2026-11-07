import json
import os

from matcher import _get_client

TAILOR_SYSTEM = (
    "You rewrite a candidate's resume for one specific job. Use ONLY facts present in the resume and profile. "
    "Never invent employers, titles, dates, degrees, skills or metrics. Reorder and rephrase to emphasize "
    "relevance to the job and mirror the job's keywords only where they are truthful. "
    "Respond ONLY with JSON: "
    '{"headline": "<short role headline>", "summary": "<2-3 sentences>", "skills": ["..."], '
    '"sections": [{"heading": "Experience", "entries": [{"title": "...", "subtitle": "<company, dates>", '
    '"bullets": ["..."]}]}], "cover_note": "<3 sentences for the additional information box>"}. '
    "Include every section from the resume such as Experience, Projects and Education."
)

ANSWER_SYSTEM = (
    "You answer job application questions in the first person on behalf of the candidate, using only the "
    "resume and profile. Keep free-text answers under 120 words. For questions with options, return exactly "
    "one of the options (a list of options for checkbox questions). If the data does not contain the answer, "
    "or the question concerns work authorization, salary, demographics or legal attestations, return an empty "
    'string so the candidate answers it. Respond ONLY with JSON: {"answers": {"<id>": "<answer>"}}'
)


def _chat_json(system, user, temperature=0.3):
    resp = _get_client().chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
    )
    text = resp.choices[0].message.content.strip()
    return json.loads(text[text.find("{") : text.rfind("}") + 1])


def _profile_block(profile):
    return (
        f"NAME: {profile.get('name', '')}\n"
        f"TARGET TITLES: {profile.get('target_titles', [])}\n"
        f"LOCATIONS: {profile.get('locations', [])}\n"
        f"BACKGROUND: {profile.get('background', '')}\n"
    )


def tailor_resume(profile, resume_text, job):
    user = (
        f"{_profile_block(profile)}\nRESUME:\n{resume_text[:6000]}\n\n"
        f"JOB TITLE: {job.get('title')}\nCOMPANY: {job.get('company')}\n"
        f"JOB DESCRIPTION:\n{job.get('description', '')[:4000]}"
    )
    data = _chat_json(TAILOR_SYSTEM, user)
    sections = []
    for section in data.get("sections") or []:
        entries = []
        for entry in section.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            entries.append(
                {
                    "title": str(entry.get("title") or ""),
                    "subtitle": str(entry.get("subtitle") or ""),
                    "bullets": [str(b) for b in (entry.get("bullets") or []) if b],
                }
            )
        if entries:
            sections.append({"heading": str(section.get("heading") or "Experience"), "entries": entries})
    return {
        "headline": str(data.get("headline") or ""),
        "summary": str(data.get("summary") or ""),
        "skills": [str(s) for s in (data.get("skills") or []) if s],
        "sections": sections,
        "cover_note": str(data.get("cover_note") or ""),
    }


def _normalize(question, value):
    if isinstance(value, list):
        value = " | ".join(str(v) for v in value)
    value = str(value or "").strip()
    options = question.get("options") or []
    if not options or not value:
        return value
    chosen = []
    for part in value.split(" | "):
        match = next((o for o in options if o.lower() == part.strip().lower()), None)
        if match:
            chosen.append(match)
    return " | ".join(chosen)


def answer_questions(profile, resume_text, job, questions):
    listing = json.dumps(
        [{"id": q["id"], "question": q["label"], "type": q["kind"], "options": q.get("options", [])} for q in questions]
    )
    user = (
        f"{_profile_block(profile)}\nRESUME:\n{resume_text[:6000]}\n\n"
        f"JOB TITLE: {job.get('title')}\nCOMPANY: {job.get('company')}\n"
        f"JOB DESCRIPTION:\n{job.get('description', '')[:3000]}\n\nQUESTIONS:\n{listing}"
    )
    raw = _chat_json(ANSWER_SYSTEM, user, temperature=0.4).get("answers") or {}
    return {q["id"]: _normalize(q, raw.get(q["id"], "")) for q in questions}

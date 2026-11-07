from playwright.sync_api import sync_playwright

TEXT_FIELDS = {
    "name": "name",
    "email": "email",
    "phone": "phone",
    "org": "current_company",
    'urls[LinkedIn]': "linkedin",
    'urls[GitHub]': "github",
    'urls[Portfolio]': "website",
}


def apply_url(job_url):
    url = job_url.rstrip("/")
    return url if url.endswith("/apply") else url + "/apply"


def collect_questions(page):
    questions = []
    for index, item in enumerate(page.query_selector_all("li.application-question")):
        control = item.query_selector(
            "textarea[name^='cards'], select[name^='cards'], input[name^='cards']:not([type='hidden'])"
        )
        if not control:
            continue
        name = control.get_attribute("name")
        tag = control.evaluate("el => el.tagName.toLowerCase()")
        kind = "textarea" if tag == "textarea" else "select" if tag == "select" else (control.get_attribute("type") or "text")
        options = []
        if kind == "select":
            options = [
                o.inner_text().strip()
                for o in control.query_selector_all("option")
                if o.get_attribute("value") and o.inner_text().strip()
            ]
        elif kind in ("radio", "checkbox"):
            options = [
                i.get_attribute("value")
                for i in item.query_selector_all(f"input[name='{name}']")
                if i.get_attribute("value")
            ]
        label_el = item.query_selector(".application-label")
        label = (label_el.inner_text() if label_el else name).replace("✱", "").strip()
        questions.append(
            {
                "id": f"q{index}",
                "name": name,
                "label": label,
                "kind": kind,
                "options": options,
                "required": item.query_selector(".required") is not None,
                "answer": "",
            }
        )
    return questions


def upload_resume(page, resume_path):
    field = page.query_selector("input[name='resume']")
    if not field or not resume_path:
        return
    field.set_input_files(resume_path)
    try:
        page.wait_for_selector(".resume-upload-success, .resume-upload-failure", timeout=15000)
    except Exception:
        page.wait_for_timeout(2000)


def fill_standard(page, profile, cover_note):
    for field_name, key in TEXT_FIELDS.items():
        value = profile.get(key)
        element = page.query_selector(f"input[name='{field_name}']")
        if value and element:
            element.fill(value)
    notes = page.query_selector("textarea[name='comments']")
    if cover_note and notes:
        notes.fill(cover_note)


def fill_custom(page, questions):
    for q in questions:
        answer = (q.get("answer") or "").strip()
        if not answer:
            continue
        selector = f"[name='{q['name']}']"
        try:
            if q["kind"] == "select":
                page.select_option(selector, label=answer)
            elif q["kind"] == "radio":
                page.check(f"input[name='{q['name']}'][value='{answer}']")
            elif q["kind"] == "checkbox":
                for value in answer.split(" | "):
                    page.check(f"input[name='{q['name']}'][value='{value}']")
            else:
                page.fill(selector, answer)
        except Exception:
            continue


def click_submit(page):
    button = page.query_selector("#btn-submit, button[type='submit']")
    if not button:
        return {"submitted": False, "message": "Submit button not found on the page."}
    button.click()
    try:
        page.wait_for_url("**/thanks**", timeout=20000)
        return {"submitted": True, "message": "Application submitted."}
    except Exception:
        body = page.inner_text("body").lower()
        if "application submitted" in body or "thanks for applying" in body:
            return {"submitted": True, "message": "Application submitted."}
        return {
            "submitted": False,
            "message": "Submission was not confirmed. A captcha or a missing required field may have blocked it.",
        }


def run_form(url, profile, resume_path, cover_note, screenshot, questions=None, answer_fn=None, submit=False):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(apply_url(url), wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("form", timeout=15000)
            if questions is None:
                questions = collect_questions(page)
                if answer_fn:
                    questions = answer_fn(questions)
            upload_resume(page, resume_path)
            fill_standard(page, profile, cover_note)
            fill_custom(page, questions)
            outcome = click_submit(page) if submit else {"submitted": False, "message": ""}
            page.screenshot(path=screenshot, full_page=True)
            return {"questions": questions, **outcome}
        finally:
            browser.close()

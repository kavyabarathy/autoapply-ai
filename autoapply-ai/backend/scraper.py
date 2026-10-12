"""Playwright scraper for public Lever job boards (https://jobs.lever.co/<company>)."""
from playwright.sync_api import sync_playwright


def scrape_lever(company: str, limit: int = 10) -> list[dict]:
    base = f"https://jobs.lever.co/{company}"
    listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(base, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector("div.posting", timeout=15000)

        for card in page.query_selector_all("div.posting")[:limit]:
            link = card.query_selector("a.posting-title")
            if not link:
                continue
            title_el = card.query_selector("h5")
            loc_el = card.query_selector(".posting-categories .location")
            listings.append(
                {
                    "title": title_el.inner_text().strip() if title_el else "Untitled",
                    "company": company,
                    "location": loc_el.inner_text().strip() if loc_el else "",
                    "url": link.get_attribute("href"),
                    "source": "lever",
                }
            )

        for item in listings:
            try:
                page.goto(item["url"], wait_until="domcontentloaded", timeout=30000)
                content = page.locator(".content")
                text = content.first.inner_text() if content.count() else page.inner_text("body")
                item["description"] = text.strip()[:6000]
            except Exception as exc:  # keep going if one posting fails
                item["description"] = ""
                item["scrape_error"] = str(exc)

        browser.close()

    return listings

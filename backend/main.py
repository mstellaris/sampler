import json
import os
import re
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

DB_PATH = Path("/data/bookmarks.db")
SCREENSHOTS_DIR = Path("/data/screenshots")
LINKEDIN_IMAGES_DIR = Path("/data/linkedin-images")
LINKEDIN_AUTH_PATH = Path("/data/linkedin-auth.json")

app = FastAPI(title="Bookmark Saver API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    LINKEDIN_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                screenshot TEXT,
                linkedin_data TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        # Migrations for older schemas
        columns = [row[1] for row in db.execute("PRAGMA table_info(bookmarks)").fetchall()]
        if "screenshot" not in columns:
            db.execute("ALTER TABLE bookmarks ADD COLUMN screenshot TEXT")
        if "linkedin_data" not in columns:
            db.execute("ALTER TABLE bookmarks ADD COLUMN linkedin_data TEXT")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class BookmarkIn(BaseModel):
    url: str
    title: str = ""


class BookmarkOut(BaseModel):
    id: int
    url: str
    title: str
    screenshot: str | None
    linkedin_data: dict | None
    created_at: str


def is_linkedin_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in ("linkedin.com", "www.linkedin.com")


def linkedin_login(playwright):
    """Log into LinkedIn and save session, or reuse existing session."""
    email = os.environ.get("LINKEDIN_EMAIL", "")
    password = os.environ.get("LINKEDIN_PASSWORD", "")
    if not email or not password:
        return None

    browser = playwright.chromium.launch()

    # Try reusing saved session
    if LINKEDIN_AUTH_PATH.exists():
        context = browser.new_context(
            storage_state=str(LINKEDIN_AUTH_PATH),
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()
        page.goto("https://www.linkedin.com/feed/", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        # Check if we're still logged in
        if "/login" not in page.url and "/authwall" not in page.url:
            return browser, context, page
        # Session expired, close and re-login
        context.close()

    # Fresh login
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.goto("https://www.linkedin.com/login", timeout=15000, wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    page.fill('#username', email)
    page.fill('#password', password)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3000)

    # Check if login succeeded
    if "/login" in page.url or "/checkpoint" in page.url:
        browser.close()
        return None

    # Save session
    context.storage_state(path=str(LINKEDIN_AUTH_PATH))
    return browser, context, page


def scrape_linkedin_post(bookmark_id: int, url: str):
    """Scrape a LinkedIn post using an authenticated session."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            result = linkedin_login(p)
            if result is None:
                return
            browser, context, page = result

            try:
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Try to expand "see more" if present
                try:
                    see_more = page.locator("button.see-more, button[aria-label*='see more']").first
                    if see_more.is_visible(timeout=1000):
                        see_more.click()
                        page.wait_for_timeout(500)
                except Exception:
                    pass

                # Extract author
                author = ""
                try:
                    author_el = page.locator(".update-components-actor__name, .feed-shared-actor__name").first
                    author = author_el.inner_text(timeout=2000).strip()
                    # Clean up: remove "View …'s profile" etc.
                    author = author.split("\n")[0].strip()
                except Exception:
                    pass

                # Extract headline
                headline = ""
                try:
                    headline_el = page.locator(".update-components-actor__description, .feed-shared-actor__description").first
                    headline = headline_el.inner_text(timeout=2000).strip()
                    headline = headline.split("\n")[0].strip()
                except Exception:
                    pass

                # Extract post text
                text = ""
                try:
                    text_el = page.locator(".update-components-text, .feed-shared-update-v2__description, .feed-shared-text").first
                    text = text_el.inner_text(timeout=2000).strip()
                except Exception:
                    pass

                # Extract date
                date = ""
                try:
                    date_el = page.locator(".update-components-actor__sub-description, .feed-shared-actor__sub-description").first
                    date = date_el.inner_text(timeout=2000).strip()
                    date = date.split("\n")[0].strip()
                except Exception:
                    pass

                # Extract and download images
                images = []
                try:
                    img_dir = LINKEDIN_IMAGES_DIR / str(bookmark_id)
                    img_dir.mkdir(parents=True, exist_ok=True)
                    img_elements = page.locator(".update-components-image__image img, .feed-shared-image__image img").all()
                    for i, img in enumerate(img_elements[:5]):  # Cap at 5 images
                        src = img.get_attribute("src")
                        if src:
                            filename = f"img_{i}.jpg"
                            resp = page.request.get(src)
                            if resp.ok:
                                (img_dir / filename).write_bytes(resp.body())
                                images.append(filename)
                except Exception:
                    pass

                # Save session for next time
                context.storage_state(path=str(LINKEDIN_AUTH_PATH))

                data = {
                    "author": author,
                    "headline": headline,
                    "text": text,
                    "date": date,
                    "images": images,
                }

                with get_db() as db:
                    db.execute(
                        "UPDATE bookmarks SET linkedin_data = ? WHERE id = ?",
                        (json.dumps(data), bookmark_id),
                    )
            finally:
                browser.close()

    except Exception:
        pass  # LinkedIn scraping is best-effort


def capture_screenshot(bookmark_id: int, url: str):
    try:
        from playwright.sync_api import sync_playwright

        path = SCREENSHOTS_DIR / f"{bookmark_id}.png"
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            page.screenshot(path=str(path))
            browser.close()

        with get_db() as db:
            db.execute(
                "UPDATE bookmarks SET screenshot = ? WHERE id = ?",
                (f"{bookmark_id}.png", bookmark_id),
            )
    except Exception:
        pass  # Screenshot is best-effort; bookmark still works without it


def process_bookmark(bookmark_id: int, url: str):
    """Background task: capture screenshot, then scrape LinkedIn if applicable."""
    capture_screenshot(bookmark_id, url)
    if is_linkedin_url(url):
        scrape_linkedin_post(bookmark_id, url)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/bookmarks", response_model=list[BookmarkOut])
def list_bookmarks():
    with get_db() as db:
        rows = db.execute(
            "SELECT id, url, title, screenshot, linkedin_data, created_at FROM bookmarks ORDER BY id DESC"
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["linkedin_data"] = json.loads(d["linkedin_data"]) if d["linkedin_data"] else None
        results.append(d)
    return results


@app.post("/api/bookmarks", response_model=BookmarkOut, status_code=201)
def create_bookmark(bookmark: BookmarkIn):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO bookmarks (url, title, created_at) VALUES (?, ?, ?)",
            (bookmark.url, bookmark.title, now),
        )
        new_id = cursor.lastrowid

    threading.Thread(
        target=process_bookmark, args=(new_id, bookmark.url), daemon=True
    ).start()

    return {
        "id": new_id,
        "url": bookmark.url,
        "title": bookmark.title,
        "screenshot": None,
        "linkedin_data": None,
        "created_at": now,
    }


@app.get("/api/screenshots/{bookmark_id}")
def get_screenshot(bookmark_id: int):
    path = SCREENSHOTS_DIR / f"{bookmark_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/linkedin-images/{bookmark_id}/{filename}")
def get_linkedin_image(bookmark_id: int, filename: str):
    # Sanitize filename to prevent path traversal
    safe_name = Path(filename).name
    path = LINKEDIN_IMAGES_DIR / str(bookmark_id) / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/jpeg")


@app.delete("/api/bookmarks/{bookmark_id}", status_code=204)
def delete_bookmark(bookmark_id: int):
    with get_db() as db:
        result = db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bookmark not found")
    # Clean up screenshot file
    path = SCREENSHOTS_DIR / f"{bookmark_id}.png"
    path.unlink(missing_ok=True)
    # Clean up LinkedIn images directory
    img_dir = LINKEDIN_IMAGES_DIR / str(bookmark_id)
    shutil.rmtree(img_dir, ignore_errors=True)

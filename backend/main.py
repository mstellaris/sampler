import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

DB_PATH = Path("/data/bookmarks.db")
SCREENSHOTS_DIR = Path("/data/screenshots")

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
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                screenshot TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        # Migration: add screenshot column if upgrading from older schema
        columns = [row[1] for row in db.execute("PRAGMA table_info(bookmarks)").fetchall()]
        if "screenshot" not in columns:
            db.execute("ALTER TABLE bookmarks ADD COLUMN screenshot TEXT")


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
    created_at: str


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


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/bookmarks", response_model=list[BookmarkOut])
def list_bookmarks():
    with get_db() as db:
        rows = db.execute(
            "SELECT id, url, title, screenshot, created_at FROM bookmarks ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


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
        target=capture_screenshot, args=(new_id, bookmark.url), daemon=True
    ).start()

    return {
        "id": new_id,
        "url": bookmark.url,
        "title": bookmark.title,
        "screenshot": None,
        "created_at": now,
    }


@app.get("/api/screenshots/{bookmark_id}")
def get_screenshot(bookmark_id: int):
    path = SCREENSHOTS_DIR / f"{bookmark_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(path, media_type="image/png")


@app.delete("/api/bookmarks/{bookmark_id}", status_code=204)
def delete_bookmark(bookmark_id: int):
    with get_db() as db:
        result = db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bookmark not found")
    # Clean up screenshot file
    path = SCREENSHOTS_DIR / f"{bookmark_id}.png"
    path.unlink(missing_ok=True)

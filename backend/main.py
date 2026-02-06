import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_PATH = Path("/data/bookmarks.db")

app = FastAPI(title="Bookmark Saver API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )


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
    created_at: str


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/bookmarks", response_model=list[BookmarkOut])
def list_bookmarks():
    with get_db() as db:
        rows = db.execute(
            "SELECT id, url, title, created_at FROM bookmarks ORDER BY id DESC"
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
    return {"id": new_id, "url": bookmark.url, "title": bookmark.title, "created_at": now}


@app.delete("/api/bookmarks/{bookmark_id}", status_code=204)
def delete_bookmark(bookmark_id: int):
    with get_db() as db:
        result = db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bookmark not found")

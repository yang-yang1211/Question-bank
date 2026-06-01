"""
database.py - SQLite CRUD operations for QuizSysteam
"""
import sqlite3
import os
from pathlib import Path
from typing import List

DB_PATH = Path(__file__).parent.parent.parent / "db" / "quiz.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables if not exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pdf_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS generation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_name TEXT NOT NULL,
                output_file TEXT NOT NULL,
                question_count INTEGER,
                model_name TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)
        conn.commit()


# ── PDF Sources ──────────────────────────────────────────────────────────────

def add_pdf_source(chapter_name: str, file_path: str) -> int:
    """Add a new PDF source. Returns new row id."""
    file_name = Path(file_path).name
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO pdf_sources (chapter_name, file_path, file_name) VALUES (?, ?, ?)",
            (chapter_name, file_path, file_name),
        )
        conn.commit()
        return cur.lastrowid


def delete_pdf_source(source_id: int):
    """Delete a PDF source by id."""
    with get_connection() as conn:
        conn.execute("DELETE FROM pdf_sources WHERE id = ?", (source_id,))
        conn.commit()


def get_all_pdf_sources() -> List[dict]:
    """Return all PDF sources as list of dicts."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pdf_sources ORDER BY chapter_name, created_at"
        ).fetchall()
        return [dict(r) for r in rows]


def get_pdf_sources_by_chapter(chapter_name: str) -> List[dict]:
    """Return all PDF sources for a specific chapter."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pdf_sources WHERE chapter_name = ?",
            (chapter_name,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_chapters() -> List[str]:
    """Return distinct chapter names sorted."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT chapter_name FROM pdf_sources ORDER BY chapter_name"
        ).fetchall()
        return [r["chapter_name"] for r in rows]


# ── Generation Logs ──────────────────────────────────────────────────────────

def add_generation_log(
    chapter_name: str, output_file: str, question_count: int, model_name: str
):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO generation_logs
               (chapter_name, output_file, question_count, model_name)
               VALUES (?, ?, ?, ?)""",
            (chapter_name, output_file, question_count, model_name),
        )
        conn.commit()


def get_generation_logs(limit: int = 50) -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM generation_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

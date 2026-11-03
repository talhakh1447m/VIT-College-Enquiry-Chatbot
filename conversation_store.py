"""
Conversation Storage module for VIT Mumbai College Enquiry Chatbot.
Persists chat transcripts, session history, and citations into SQLite.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent

# On Vercel / AWS Lambda, use writable /tmp storage; locally use data/conversations.db
if os.environ.get("VERCEL"):
    DB_PATH = Path(tempfile.gettempdir()) / "vit_conversations.db"
else:
    DB_PATH = BASE_DIR / "data" / "conversations.db"


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database tables if they do not exist."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    title TEXT DEFAULT 'College Enquiry'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT,
                    provider TEXT,
                    model TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id)")
    finally:
        conn.close()


def generate_title_from_message(message: str) -> str:
    """Generate a clean, user-friendly session title from the first question."""
    cleaned = message.strip().replace("\n", " ")
    # Remove leading greetings
    for prefix in ["hello", "hi", "hey", "can you tell me", "what is", "tell me about"]:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    if len(cleaned) > 40:
        cleaned = cleaned[:37].rsplit(" ", 1)[0] + "..."
    title = cleaned.strip("?.,! ")
    return (title[:1].upper() + title[1:]) if title else "College Enquiry"


def save_message(
    session_id: str,
    role: str,
    content: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> None:
    """Save an incoming or outgoing message into SQLite, setting title if new."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    sources_json = json.dumps(sources, ensure_ascii=False) if sources else None

    conn = get_db_connection()
    try:
        with conn:
            # Check if session already exists
            existing = conn.execute(
                "SELECT title FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if not existing:
                title = generate_title_from_message(content) if role == "user" else "College Enquiry"
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, created_at, updated_at, title)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, now, now, title)
                )
            else:
                # Update timestamp and title if generic
                new_title = existing["title"]
                if existing["title"] == "College Enquiry" and role == "user":
                    new_title = generate_title_from_message(content)
                conn.execute(
                    """
                    UPDATE sessions SET updated_at = ?, title = ? WHERE session_id = ?
                    """,
                    (now, new_title, session_id)
                )

            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, sources, provider, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, role, content, sources_json, provider, model, now)
            )
    finally:
        conn.close()


def get_session_messages(session_id: str, limit: int = 60) -> List[Dict[str, Any]]:
    """Retrieve message history for a given session."""
    init_db()
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT role, content, sources, provider, model, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, limit)
        ).fetchall()

        messages = []
        for r in rows:
            sources = None
            if r["sources"]:
                try:
                    sources = json.loads(r["sources"])
                except Exception:
                    sources = None
            messages.append({
                "role": r["role"],
                "content": r["content"],
                "sources": sources,
                "provider": r["provider"],
                "model": r["model"],
                "created_at": r["created_at"]
            })
        return messages
    finally:
        conn.close()


def list_recent_sessions(limit: int = 30) -> List[Dict[str, Any]]:
    """List recent conversation sessions with metadata."""
    init_db()
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.session_id, s.created_at, s.updated_at, s.title,
                   COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    init_db()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        return True
    except Exception:
        return False
    finally:
        conn.close()

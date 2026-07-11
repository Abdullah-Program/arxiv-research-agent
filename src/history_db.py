import sqlite3
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"

def get_db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 2. Messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        sources TEXT, -- JSON string array
        timestamp TEXT,
        node_logs TEXT, -- JSON string dict
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()
    print("[history_db] SQLite database initialized.")

def create_session(title: str) -> str:
    """Create a new session and return its ID."""
    session_id = str(uuid.uuid4().hex[:8])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (id, title) VALUES (?, ?)",
        (session_id, title)
    )
    conn.commit()
    conn.close()
    return session_id

def list_sessions() -> List[Dict[str, Any]]:
    """List all sessions ordered by created_at DESC."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, created_at FROM sessions ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    """Get all messages for a session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, text, sources, timestamp, node_logs FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    messages = []
    for row in rows:
        d = dict(row)
        # Deserialize JSON fields
        d["sources"] = json.loads(d["sources"]) if d["sources"] else []
        d["node_logs"] = json.loads(d["node_logs"]) if d["node_logs"] else {}
        messages.append(d)
    return messages

def add_message(session_id: str, role: str, text: str, sources: List[str] = None, timestamp: str = None, node_logs: Dict[str, Any] = None):
    """Add a message to a session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, role, text, sources, timestamp, node_logs) VALUES (?, ?, ?, ?, ?, ?)",
        (
            session_id,
            role,
            text,
            json.dumps(sources or []),
            timestamp,
            json.dumps(node_logs or {})
        )
    )
    conn.commit()
    conn.close()

def delete_session(session_id: str):
    """Delete a session and all its messages."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

# Initialize on import/load
init_db()

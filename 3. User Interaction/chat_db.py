import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_history.db")

def init_chat_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Sessions table
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        name TEXT,
        created_at TIMESTAMP
    )""")
    # Messages table
    # type: 'text' or 'result' (if it contains the advice + recs bundle)
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        type TEXT,
        metadata TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )""")
    conn.commit()
    conn.close()

def create_session(session_id, name=None):
    if not name:
        name = f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (id, name, created_at) VALUES (?, ?, ?)", 
              (session_id, name, datetime.now()))
    conn.commit()
    conn.close()

def get_sessions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, created_at FROM sessions ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]

def delete_session(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

def rename_session(session_id, new_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sessions SET name = ? WHERE id = ?", (new_name, session_id))
    conn.commit()
    conn.close()

def add_message(session_id, role, content, msg_type='text', metadata=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    meta_json = json.dumps(metadata) if metadata else None
    c.execute("INSERT INTO messages (session_id, role, content, type, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (session_id, role, content, msg_type, meta_json, datetime.now()))
    conn.commit()
    conn.close()

def get_chat_history(session_id, limit=10):
    """
    Returns last N messages for the session.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content, type, metadata FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "type": r[2], "metadata": json.loads(r[3]) if r[3] else None} for r in rows]

init_chat_db()

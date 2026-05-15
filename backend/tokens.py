import sqlite3
import uuid
import os
from datetime import datetime

# Use persistent volume on Railway, local file otherwise
_DATA_DIR = '/data' if os.path.exists('/data') else os.path.dirname(os.path.abspath(__file__))
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, 'morelike.db')


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            credits INTEGER NOT NULL DEFAULT 1,
            email TEXT,
            lemon_order_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            email TEXT,
            message TEXT NOT NULL,
            reply TEXT,
            replied_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()


def create_token(email=None, credits=3, lemon_order_id=None):
    token = uuid.uuid4().hex[:12].upper()
    conn = get_db()
    conn.execute(
        'INSERT INTO tokens (token, credits, email, lemon_order_id) VALUES (?, ?, ?, ?)',
        (token, credits, email, lemon_order_id)
    )
    conn.commit()
    conn.close()
    return token


def is_token_valid(token):
    conn = get_db()
    row = conn.execute(
        'SELECT credits FROM tokens WHERE token = ?', (token,)
    ).fetchone()
    conn.close()
    if row and row['credits'] > 0:
        return True
    return False


def get_credits(token):
    conn = get_db()
    row = conn.execute(
        'SELECT credits, email FROM tokens WHERE token = ?', (token,)
    ).fetchone()
    conn.close()
    if row:
        return {'credits': row['credits'], 'email': row['email']}
    return None


def use_credit(token):
    conn = get_db()
    row = conn.execute(
        'SELECT credits FROM tokens WHERE token = ?', (token,)
    ).fetchone()
    if not row or row['credits'] <= 0:
        conn.close()
        return False
    conn.execute(
        'UPDATE tokens SET credits = credits - 1 WHERE token = ?', (token,)
    )
    _log_action(conn, token, 'credit_used')
    conn.commit()
    conn.close()
    return True


def claim_token_by_email(email):
    """Find the most recent unused token for a given email."""
    conn = get_db()
    row = conn.execute(
        'SELECT token, credits FROM tokens WHERE email = ? AND credits > 0 ORDER BY created_at DESC LIMIT 1',
        (email,)
    ).fetchone()
    conn.close()
    if row:
        return {'token': row['token'], 'credits': row['credits']}
    return None


def _log_action(conn, token, action):
    conn.execute(
        'INSERT INTO usage_log (token, action) VALUES (?, ?)',
        (token, action)
    )


def log_action(token, action):
    conn = get_db()
    _log_action(conn, token, action)
    conn.commit()
    conn.close()


def save_feedback(token, message, email=None):
    conn = get_db()
    conn.execute(
        'INSERT INTO feedback (token, email, message) VALUES (?, ?, ?)',
        (token, email, message)
    )
    conn.commit()
    conn.close()


def get_all_feedback():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM feedback ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_reply(feedback_id, reply_text):
    conn = get_db()
    conn.execute(
        'UPDATE feedback SET reply = ?, replied_at = ? WHERE id = ?',
        (reply_text, datetime.now().isoformat(), feedback_id)
    )
    conn.commit()
    conn.close()
    return True

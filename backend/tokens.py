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


# Plan configuration
PLAN_CONFIG = {
    'basic':     {'max_videos': 3, 'max_minutes': 3,  'price': '$8',  'credits': 3},
    'pro':       {'max_videos': 5, 'max_minutes': 5,  'price': '$10', 'credits': 3},
    'promax':    {'max_videos': 5, 'max_minutes': 15, 'price': '$15', 'credits': 5},
    'unlimited': {'max_videos': 5, 'max_minutes': 60, 'price': '—',   'credits': 9999},
    'custom':    {'max_videos': 5, 'max_minutes': 15, 'price': '—',   'credits': 1},
}

# Plans not shown on the public website or API responses
HIDDEN_PLANS = {'unlimited', 'custom'}


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            credits INTEGER NOT NULL DEFAULT 1,
            email TEXT,
            lemon_order_id TEXT,
            plan TEXT NOT NULL DEFAULT 'basic',
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

    # Migrate existing tables that lack the plan column
    try:
        conn.execute('ALTER TABLE tokens ADD COLUMN plan TEXT NOT NULL DEFAULT "basic"')
    except Exception:
        pass  # column already exists

    conn.commit()
    conn.close()


def create_token(email=None, credits=None, lemon_order_id=None, plan='basic', custom_limits=None):
    if credits is None:
        credits = PLAN_CONFIG.get(plan, PLAN_CONFIG['basic']).get('credits', 3)
    token = uuid.uuid4().hex.upper()  # Full 32 hex chars = 128 bits
    conn = get_db()
    conn.execute(
        'INSERT INTO tokens (token, credits, email, lemon_order_id, plan) VALUES (?, ?, ?, ?, ?)',
        (token, credits, email, lemon_order_id, plan)
    )
    # Store custom plan limits as JSON in a separate table or as metadata
    if custom_limits:
        try:
            conn.execute(
                'CREATE TABLE IF NOT EXISTS token_limits (token TEXT PRIMARY KEY, max_videos INTEGER, max_minutes INTEGER, FOREIGN KEY(token) REFERENCES tokens(token))'
            )
            conn.execute(
                'INSERT OR REPLACE INTO token_limits (token, max_videos, max_minutes) VALUES (?, ?, ?)',
                (token, custom_limits.get('max_videos', 5), custom_limits.get('max_minutes', 15))
            )
        except Exception:
            pass
    conn.commit()
    conn.close()
    return token


def get_plan_limits(token):
    """Return max_videos and max_minutes for the token's plan. Checks custom limits first."""
    conn = get_db()
    row = conn.execute('SELECT plan FROM tokens WHERE token = ?', (token,)).fetchone()
    if row:
        plan = row['plan']
        # Check for custom limit overrides
        if plan in ('custom', 'unlimited'):
            custom_row = conn.execute(
                'SELECT max_videos, max_minutes FROM token_limits WHERE token = ?', (token,)
            ).fetchone()
            conn.close()
            if custom_row:
                return {'max_videos': custom_row['max_videos'], 'max_minutes': custom_row['max_minutes']}
        conn.close()
        return PLAN_CONFIG.get(plan, PLAN_CONFIG['basic'])
    conn.close()
    return PLAN_CONFIG['basic']


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
        'SELECT credits, email, plan FROM tokens WHERE token = ?', (token,)
    ).fetchone()
    conn.close()
    if row:
        return {'credits': row['credits'], 'email': row['email'], 'plan': row['plan']}
    return None


def use_credit(token):
    conn = get_db()
    row = conn.execute(
        'SELECT credits FROM tokens WHERE token = ?', (token,)
    ).fetchone()
    if not row or row['credits'] <= 0:
        conn.close()
        return False
    new_credits = row['credits'] - 1
    if new_credits <= 0:
        conn.execute('DELETE FROM tokens WHERE token = ?', (token,))
    else:
        conn.execute('UPDATE tokens SET credits = ? WHERE token = ?', (new_credits, token))
    _log_action(conn, token, 'credit_used')
    conn.commit()
    conn.close()
    return True


def claim_token_by_email(email):
    """Find the most recent unused token for a given email — only tokens created by a real Lemon Squeezy order."""
    conn = get_db()
    row = conn.execute(
        'SELECT token, credits, plan FROM tokens WHERE email = ? AND credits > 0 AND lemon_order_id IS NOT NULL ORDER BY created_at DESC LIMIT 1',
        (email,)
    ).fetchone()
    conn.close()
    if row:
        return {'token': row['token'], 'credits': row['credits'], 'plan': row['plan']}
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

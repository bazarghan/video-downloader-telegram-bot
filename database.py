import sqlite3
import uuid
import threading
from contextlib import contextmanager

# Use a thread-local storage for sqlite3 connections
local_state = threading.local()
DB_FILE = 'bot.db'

def get_connection():
    if not hasattr(local_state, "conn"):
        local_state.conn = sqlite3.connect(DB_FILE)
        local_state.conn.row_factory = sqlite3.Row
    return local_state.conn

@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        yield conn.cursor()
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e

def init_db(db_file='bot.db'):
    global DB_FILE
    DB_FILE = db_file
    with get_cursor() as cur:
        # Cache for already uploaded videos
        cur.execute('''
            CREATE TABLE IF NOT EXISTS video_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                format_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                UNIQUE(url, format_id)
            )
        ''')
        # Map for short URL IDs to bypass Telegram's 64-byte callback limit
        cur.execute('''
            CREATE TABLE IF NOT EXISTS url_map (
                short_id TEXT PRIMARY KEY,
                url TEXT NOT NULL
            )
        ''')

def get_file_id(url: str, format_id: str) -> str:
    with get_cursor() as cur:
        cur.execute('SELECT file_id FROM video_cache WHERE url = ? AND format_id = ?', (url, format_id))
        row = cur.fetchone()
        return row['file_id'] if row else None

def save_file_id(url: str, format_id: str, file_id: str):
    with get_cursor() as cur:
        cur.execute('''
            INSERT OR REPLACE INTO video_cache (url, format_id, file_id)
            VALUES (?, ?, ?)
        ''', (url, format_id, file_id))

def get_url(short_id: str) -> str:
    with get_cursor() as cur:
        cur.execute('SELECT url FROM url_map WHERE short_id = ?', (short_id,))
        row = cur.fetchone()
        return row['url'] if row else None

def save_url(url: str) -> str:
    with get_cursor() as cur:
        # Check if already exists to reuse short_id
        cur.execute('SELECT short_id FROM url_map WHERE url = ?', (url,))
        row = cur.fetchone()
        if row:
            return row['short_id']
            
        short_id = uuid.uuid4().hex[:10]  # Short enough, random enough
        cur.execute('INSERT INTO url_map (short_id, url) VALUES (?, ?)', (short_id, url))
        return short_id

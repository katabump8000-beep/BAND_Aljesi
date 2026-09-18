import sqlite3
from datetime import datetime, timedelta

DB_PATH = "meliora.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # جدول المستخدمين المسجلين
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            registered_at TEXT
        )
    """)
    
    # جدول المحظورين مؤقتاً
    c.execute("""
        CREATE TABLE IF NOT EXISTS blocked (
            user_id INTEGER PRIMARY KEY,
            blocked_until TEXT
        )
    """)
    
    # جدول الإعدادات (كلمة السر، عدد المحاولات)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # جدول محاولات فاشلة
    c.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            user_id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)
    
    # القيم الافتراضية
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('main_password', '12005')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_password', '85688')")
    
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_attempts(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count FROM attempts WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def increment_attempts(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO attempts (user_id, count) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE attempts SET count = count + 1 WHERE user_id = ?", (user_id,))
    c.execute("SELECT count FROM attempts WHERE user_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.commit()
    conn.close()
    return count

def reset_attempts(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM attempts WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def block_user(user_id, minutes=5):
    until = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO blocked (user_id, blocked_until) VALUES (?, ?)", (user_id, until))
    conn.commit()
    conn.close()

def is_blocked(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT blocked_until FROM blocked WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    until = datetime.fromisoformat(row[0])
    if datetime.now() >= until:
        unblock_user(user_id)
        return False
    return True

def unblock_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM blocked WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def register_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, registered_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, registered_at FROM users ORDER BY registered_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_by_username(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    clean = username.lstrip("@").strip()
    c.execute("SELECT user_id, username, first_name FROM users WHERE LOWER(username) = LOWER(?)", (clean,))
    row = c.fetchone()
    conn.close()
    return row

def delete_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def delete_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM users")
    conn.commit()
    conn.close()
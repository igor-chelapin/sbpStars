import sqlite3
from datetime import datetime

DB_PATH = "stars_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            role TEXT DEFAULT 'buyer',
            stars_balance INTEGER DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            created_at TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE,
            buyer_id INTEGER,
            agent_id INTEGER,
            qr_link TEXT,
            rub_amount INTEGER,
            stars_amount INTEGER,
            stars_for_agent INTEGER,
            status TEXT DEFAULT 'waiting_agent',
            proof_file_id TEXT,
            created_at TIMESTAMP,
            taken_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY(buyer_id) REFERENCES users(tg_id),
            FOREIGN KEY(agent_id) REFERENCES users(tg_id)
        )
    """)
    
    conn.commit()
    conn.close()

def get_user(tg_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    user = cur.fetchone()
    conn.close()
    return user

def create_user(tg_id, role='buyer'):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (tg_id, role, created_at) VALUES (?, ?, ?)",
        (tg_id, role, datetime.now())
    )
    conn.commit()
    conn.close()

def update_user_role(tg_id, role):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET role = ? WHERE tg_id = ?", (role, tg_id))
    conn.commit()
    conn.close()

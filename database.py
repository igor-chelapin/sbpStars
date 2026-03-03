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
            completed_at TIMESTAMP
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

def create_user(tg_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (tg_id, created_at) VALUES (?, ?)",
        (tg_id, datetime.now())
    )
    conn.commit()
    conn.close()

def update_user_balance(tg_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET stars_balance = stars_balance + ? WHERE tg_id = ?", (amount, tg_id))
    conn.commit()
    conn.close()

def create_order(buyer_id, qr_link, rub_amount, stars_amount, stars_for_agent):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM orders")
    count = cur.fetchone()[0] + 1
    order_number = f"ORD{count:04d}"
    
    cur.execute("""
        INSERT INTO orders 
        (order_number, buyer_id, qr_link, rub_amount, stars_amount, stars_for_agent, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (order_number, buyer_id, qr_link, rub_amount, stars_amount, stars_for_agent, 'waiting_agent'))
    
    conn.commit()
    order_id = cur.lastrowid
    conn.close()
    return order_number
import sqlite3

DB = "bot.db"

def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init():
    c = get_conn().cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0,
        total REAL DEFAULT 0,
        referred_by INTEGER DEFAULT 0,
        ref_code TEXT UNIQUE,
        join_date TEXT,
        referrals_count INTEGER DEFAULT 0,
        referrals_watched_ads INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS links(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        original_url TEXT,
        short TEXT,
        earned REAL DEFAULT 0,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS withdraws(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        wallet TEXT,
        status TEXT DEFAULT 'pending',
        request_date TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS support_tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        reply TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS points(
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        total_earned INTEGER DEFAULT 0,
        total_spent INTEGER DEFAULT 0,
        last_daily_bonus TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS points_transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        type TEXT,
        description TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS points_pricing(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER,
        price REAL,
        stars_price INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS ad_views(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        ad_id INTEGER,
        service TEXT,
        viewed_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS referral_tracking(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        new_user_id INTEGER,
        ad_watched INTEGER DEFAULT 0,
        points_awarded INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)

    # جدول لتخزين الفواتير المؤقتة (للتحقق من الدفع)
    c.execute("""
    CREATE TABLE IF NOT EXISTS pending_invoices(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        payload TEXT,
        amount INTEGER,
        created_at TEXT
    )
    """)

    c.connection.commit()
    c.connection.close()
from database import get_db_connection

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    cursor.execute("PRAGMA table_info(users)")
    existing_user_columns = {column["name"] for column in cursor.fetchall()}
    company_columns = {
        "company_logo": "TEXT",
        "company_address": "TEXT",
        "company_hotline": "TEXT",
        "company_id": "INTEGER",
        "staff_registration_key": "TEXT",
        "is_prime_staff": "INTEGER DEFAULT 0",
        "company_about": "TEXT",
        "company_media": "TEXT",
    }

    for column_name, column_type in company_columns.items():
        if column_name not in existing_user_columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")

    # ADS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS advertisements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        company_id INTEGER,
        product_name TEXT,
        quantity TEXT,
        ad_type TEXT,
        description TEXT,
        location TEXT,
        start_date TEXT,
        end_date TEXT,
        status TEXT DEFAULT 'pending',
        assigned_staff TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (company_id) REFERENCES users(id)
    )
    """)

    cursor.execute("PRAGMA table_info(advertisements)")
    existing_ad_columns = {column["name"] for column in cursor.fetchall()}
    ad_columns = {
        "company_id": "INTEGER",
        "status": "TEXT DEFAULT 'pending'",
        "assigned_staff": "TEXT",
        "created_at": "TEXT",
    }

    for column_name, column_type in ad_columns.items():
        if column_name not in existing_ad_columns:
            cursor.execute(f"ALTER TABLE advertisements ADD COLUMN {column_name} {column_type}")

    conn.commit()
    conn.close()

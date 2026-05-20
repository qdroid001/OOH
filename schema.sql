PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    password TEXT,
    role TEXT,
    company_logo TEXT,
    company_address TEXT,
    company_hotline TEXT,
    company_id INTEGER,
    staff_registration_key TEXT,
    is_prime_staff INTEGER DEFAULT 0,
    company_about TEXT,
    company_media TEXT,
    profile_pic TEXT,
    staff_about TEXT,
    first_name TEXT,
    last_name TEXT,
    phone_number TEXT,
    address TEXT,
    department TEXT,
    skills TEXT,
    FOREIGN KEY(company_id) REFERENCES users(id)
);

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
    completion_media TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(company_id) REFERENCES users(id)
);

import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("pettys.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
""")

password_hash = generate_password_hash("admin123")

cursor.execute("""
INSERT OR IGNORE INTO admin_users (username, password_hash)
VALUES (?, ?)
""", ("jose", password_hash))

conn.commit()
conn.close()

print("Admin user created.")
print("Username: jose")
print("Password: admin123")

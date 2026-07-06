import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

username = input("Admin username: ").strip()
password = getpass("New password: ").strip()
confirm = getpass("Confirm password: ").strip()

if not username or not password:
    print("Username and password cannot be empty.")
    exit()

if password != confirm:
    print("Passwords do not match.")
    exit()

conn = sqlite3.connect("pettys.db")
cursor = conn.cursor()

cursor.execute("""
UPDATE admin_users
SET password_hash = ?
WHERE username = ?
""", (generate_password_hash(password), username))

conn.commit()

if cursor.rowcount == 0:
    print("No admin user found with that username.")
else:
    print("Password updated successfully.")

conn.close()

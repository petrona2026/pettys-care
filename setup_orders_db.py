import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "pettys.db")

conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT UNIQUE,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    notes TEXT,

    subtotal REAL DEFAULT 0,
    shipping_amount REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,

    total REAL,

    status TEXT DEFAULT 'Pending Payment',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,

    product_name TEXT,
    product_slug TEXT,

    size_code TEXT,
    size_name TEXT,

    quantity INTEGER,
    price REAL,
    subtotal REAL,

    FOREIGN KEY(order_id) REFERENCES orders(id)
)
""")
# ---- Upgrade existing orders table if needed ----

columns = {
    row[1]
    for row in cursor.execute("PRAGMA table_info(orders)")
}

if "subtotal" not in columns:
    cursor.execute("ALTER TABLE orders ADD COLUMN subtotal REAL DEFAULT 0")

if "shipping_amount" not in columns:
    cursor.execute("ALTER TABLE orders ADD COLUMN shipping_amount REAL DEFAULT 0")

if "tax_amount" not in columns:
    cursor.execute("ALTER TABLE orders ADD COLUMN tax_amount REAL DEFAULT 0")

# ---- Upgrade existing order_items table if needed ----

item_columns = {
    row[1]
    for row in cursor.execute("PRAGMA table_info(order_items)")
}

if "size_code" not in item_columns:
    cursor.execute("ALTER TABLE order_items ADD COLUMN size_code TEXT")

if "size_name" not in item_columns:
    cursor.execute("ALTER TABLE order_items ADD COLUMN size_name TEXT")
conn.commit()
conn.close()

print("Orders database created successfully.")

import sqlite3

conn = sqlite3.connect("pettys.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS store_settings (
    id INTEGER PRIMARY KEY,
    business_name TEXT,
    owner_name TEXT,
    contact_email TEXT,
    phone TEXT,
    website TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    facebook TEXT,
    instagram TEXT,
    youtube TEXT,
    shipping_fee REAL,
    tax_rate REAL,
    currency TEXT,
    logo TEXT
)
""")

cursor.execute("""
INSERT OR IGNORE INTO store_settings (
    id,
    business_name,
    owner_name,
    contact_email,
    website,
    currency,
    shipping_fee,
    tax_rate
)
VALUES (
    1,
    "PETTY'S CARE",
    "Petronila",
    "petronila@pettyscare.com",
    "https://pettyscare.com",
    "USD",
    0,
    0
)
""")

conn.commit()
conn.close()

print("Store settings created successfully.")

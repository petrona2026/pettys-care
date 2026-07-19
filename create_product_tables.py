import sqlite3
from pathlib import Path

DB_PATH = Path("pettys.db")


def create_product_tables() -> None:
    connection = sqlite3.connect(DB_PATH)

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name_en TEXT NOT NULL,
                name_es TEXT,
                short_description_en TEXT,
                short_description_es TEXT,
                image TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                featured INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_sizes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                size_code TEXT NOT NULL,
                name_en TEXT NOT NULL,
                name_es TEXT,
                weight TEXT NOT NULL,
                price REAL NOT NULL,
                regular_price REAL,
                stock INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (product_id)
                    REFERENCES products (id)
                    ON DELETE CASCADE,
                UNIQUE(product_id, size_code)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                ingredients_json TEXT,
                benefits_json TEXT,
                perfect_for_json TEXT,
                FOREIGN KEY (product_id)
                    REFERENCES products (id)
                    ON DELETE CASCADE,
                UNIQUE(product_id, language)
            )
        """)

        connection.commit()
        print("Product tables created successfully.")

    except sqlite3.Error as error:
        connection.rollback()
        print(f"Database error: {error}")
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_product_tables()

import sqlite3

DB_PATH = "pettys.db"

columns_to_add = {
    "name_en": "TEXT",
    "name_es": "TEXT",
    "short_description_en": "TEXT",
    "short_description_es": "TEXT",
    "active": "INTEGER NOT NULL DEFAULT 1",
    "featured": "INTEGER NOT NULL DEFAULT 0",
    "updated_at": "TEXT",
}


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def upgrade_products_table():
    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        for column_name, column_definition in columns_to_add.items():
            if column_exists(cursor, "products", column_name):
                print(f"Already exists: {column_name}")
                continue

            cursor.execute(
                f"ALTER TABLE products "
                f"ADD COLUMN {column_name} {column_definition}"
            )
            print(f"Added: {column_name}")

        cursor.execute("""
            UPDATE products
            SET
                name_en = COALESCE(NULLIF(name_en, ''), name),
                short_description_en =
                    COALESCE(NULLIF(short_description_en, ''), description),
                active =
                    CASE
                        WHEN LOWER(status) = 'active' THEN 1
                        ELSE 0
                    END,
                updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        """)

        conn.commit()
        print("Products table upgraded successfully.")

    except sqlite3.Error as error:
        conn.rollback()
        print(f"Database error: {error}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    upgrade_products_table()

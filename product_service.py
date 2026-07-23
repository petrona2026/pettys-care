import json
import sqlite3
from pathlib import Path

DB_PATH = Path("pettys.db")


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def get_all_products(active_only=True):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                name,
                slug,
                description,
                image,
                price,
                stock
            FROM products
            ORDER BY id
        """)

        rows = cursor.fetchall()
        products = []

        for row in rows:
            cursor.execute("""
                SELECT
                    id,
                    size_code,
                    stock
                FROM product_sizes
                WHERE product_id = ?
                ORDER BY id
            """, (row["id"],))

            size_rows = cursor.fetchall()

            sizes = [
                {
                    "id": size["id"],
                    "size_code": size["size_code"],
                    "stock": size["stock"],
                }
                for size in size_rows
            ]

            products.append({
                "id": row["id"],
                "name": row["name"],
                "name_en": row["name"],
                "name_es": row["name"],
                "slug": row["slug"],
                "description": row["description"] or "",
                "image": row["image"] or "",
                "price": row["price"],
                "stock": row["stock"],
                "sizes": sizes,
            })

        return products

    finally:
        connection.close()


def get_product_by_slug(slug, active_only=True):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                id,
                slug,
                COALESCE(NULLIF(name_en, ''), name_es, slug) AS name,
                short_description_en,
                short_description_es,
                image,
                active,
                featured
            FROM products
            WHERE LOWER(slug) = LOWER(?)
        """

        parameters = [slug]

        if active_only:
            query += " AND active = 1"

        cursor.execute(query, parameters)
        product_row = cursor.fetchone()

        if product_row is None:
            return None

        return build_product(cursor, product_row)

    finally:
        connection.close()


def build_product(cursor, product_row):
    cursor.execute("""
        SELECT
            size_code,
            name_en,
            name_es,
            weight,
            price,
            regular_price,
            stock,
            active
        FROM product_sizes
        WHERE product_id = ?
        ORDER BY sort_order, id
    """, (product_row["id"],))

    size_rows = cursor.fetchall()

    sizes = [
        {
            "id": row["size_code"],
            "name": row["name_en"],
            "name_es": row["name_es"],
            "weight": row["weight"],
            "price": row["price"],
            "regular_price": row["regular_price"],
            "stock": row["stock"],
            "active": bool(row["active"]),
        }
        for row in size_rows
        if row["active"]
    ]

    cursor.execute("""
        SELECT
            language,
            ingredients_json,
            benefits_json,
            perfect_for_json
        FROM product_content
        WHERE product_id = ?
    """, (product_row["id"],))

    content_rows = cursor.fetchall()

    content = {}

    for row in content_rows:
        content[row["language"]] = {
            "ingredients": parse_json(row["ingredients_json"], []),
            "benefits": parse_json(row["benefits_json"], []),
            "perfect_for": parse_json(row["perfect_for_json"], []),
        }

    short = {
        "en": product_row["short_description_en"] or "",
        "es": product_row["short_description_es"] or "",
    }

    product = {
        "id": product_row["id"],
        "name": product_row["name"],
        "slug": product_row["slug"],
        "short": short,
        "image": product_row["image"] or "",
        "sizes": sizes,
        "content": content,
        "active": bool(product_row["active"]),
        "featured": bool(product_row["featured"]),
    }

    if sizes:
        product["price"] = sizes[0]["price"]
        product["regular_price"] = sizes[-1]["regular_price"]
    else:
        product["price"] = 0
        product["regular_price"] = None

    return product


def parse_json(value, default):
    if not value:
        return default

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default

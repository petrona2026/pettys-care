import os
import sqlite3

import resend
import stripe
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, session, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from product_profiles import product_profiles
from recommendation_engine import recommend_soap
from translations.en import translations as en
from translations.es import translations as es


load_dotenv()

DB_PATH = os.getenv("DB_PATH", "pettys.db")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = Flask(__name__)
resend.api_key = os.getenv("RESEND_API_KEY")


def send_order_confirmation_email(order_id):
    """
    Send a paid-order confirmation email once through Resend.

    Returns True when the email is sent successfully.
    Returns False when the order does not exist, the confirmation was already
    sent, the Resend API key is missing, or delivery fails.
    """

    if not resend.api_key:
        print("EMAIL ERROR: RESEND_API_KEY is missing.")
        return False

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT *
            FROM orders
            WHERE id = ?
            """,
            (order_id,),
        )
        order = cursor.fetchone()

        if order is None:
            print(f"EMAIL ERROR: Order {order_id} was not found.")
            return False

        if order["confirmation_email_sent"] == 1:
            print(
                "EMAIL SKIPPED: Confirmation for "
                f"{order['order_number']} was already sent."
            )
            return False

        cursor.execute(
            """
            SELECT *
            FROM order_items
            WHERE order_id = ?
            ORDER BY id
            """,
            (order_id,),
        )
        items = cursor.fetchall()

        language = session.get("language", "en")
        if language == "es":
            email_translations = es
        else:
            language = "en"
            email_translations = en

        text_body = (
            f"{email_translations['email_greeting']} "
            f"{order['first_name']},\n\n"
            f"{email_translations['email_order_received_message']}\n\n"
            f"{email_translations['email_order_number']}: "
            f"{order['order_number']}\n"
            f"{email_translations['total']}: "
            f"${order['total']:.2f}\n\n"
            f"{email_translations['email_thank_you']}\n\n"
            "PETTY'S CARE\n"
            "orders@pettyscare.com"
        )

        html_body = render_template(
            "emails/order_received.html",
            order=order,
            items=items,
            t=email_translations,
            language=language,
        )

        response = resend.Emails.send(
            {
                "from": "PETTY'S CARE <orders@pettyscare.com>",
                "to": [order["email"]],
                "subject": email_translations["email_order_received_subject"],
                "html": html_body,
                "text": text_body,
                "reply_to": "orders@pettyscare.com",
            }
        )

        cursor.execute(
            """
            UPDATE orders
            SET confirmation_email_sent = 1
            WHERE id = ?
            """,
            (order_id,),
        )
        conn.commit()

        print(
            "EMAIL SENT THROUGH RESEND: "
            f"{order['order_number']} to {order['email']}. "
            f"Response: {response}"
        )
        return True

    except Exception as error:
        conn.rollback()
        print("ORDER CONFIRMATION EMAIL ERROR:", repr(error))
        return False

    finally:
        conn.close()


@app.context_processor
def inject_translations():

    language = session.get("language", "en")

    if language == "es":
        t = es
    else:
        t = en

    return dict(t=t)
app.secret_key = os.getenv(
    "SECRET_KEY",
    "pettys-local-development-key"
)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"

class AdminUser(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, username FROM admin_users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    conn.close()

    if user:
        return AdminUser(user["id"], user["username"])

    return None
products = [
{
    "id": 1,
    "name": "Coconut Bliss",
    "slug": "coconut-bliss",
    "short": {
        "en": "Crafted with coconut oil and Vitamin E.",
        "es": "Elaborado con aceite de coco y vitamina E."
    },
    "price": 12.00,
    "image": "products_clean/01-coconut-bliss.png",
},
{
    "id": 2,
    "name": "Aloe Serenity",
    "slug": "aloe-serenity",
    "short": {
        "en": "A soothing aloe vera soap with Vitamin E.",
        "es": "Un jabón calmante de aloe vera con vitamina E."
    },
    "price": 12.00,
    "image": "products_clean/02-aloe-serenity.png",
},
{
    "id": 3,
    "name": "Golden Turmeric",
    "slug": "golden-turmeric",
    "short": {
        "en": "A warm botanical soap with turmeric and Vitamin E.",
        "es": "Un jabón botánico de cúrcuma con vitamina E."
    },
    "price": 12.00,
    "image": "products_clean/03-golden-turmeric.png",
},
{
    "id": 4,
    "name": "Honey Glow",
    "slug": "honey-glow",
    "short": {
        "en": "A comforting honey and oatmeal soap.",
        "es": "Un jabón reconfortante de miel y avena."
    },
    "price": 12.00,
    "image": "products_clean/04-honey-glow.png",
},
{
    "id": 5,
    "name": "Coffee Delight",
    "slug": "coffee-delight",
    "short": {
        "en": "A rich coffee-inspired handcrafted soap.",
        "es": "Un jabón artesanal inspirado en el café."
    },
    "price": 12.00,
    "image": "products_clean/05-coffee-delight.png",
},
{
    "id": 6,
    "name": "Charcoal Cleanse",
    "slug": "charcoal-cleanse",
    "short": {
        "en": "A bold activated charcoal soap.",
        "es": "Un jabón de carbón activado para una limpieza profunda."
    },
    "price": 12.00,
    "image": "products_clean/06-charcoal-cleanse.png",
},
    ]
@app.route("/set-language/<language>")
def set_language(language):

    if language not in ["en", "es"]:
        language = "en"

    session["language"] = language

    return redirect(request.referrer or url_for("index"))
@app.route("/")
def index():
    return render_template("index.html", products=products)

@app.route("/shop")
def shop():
    return render_template("shop.html", products=products)
@app.route("/products")
def product_list():
    return redirect(url_for("shop"))
@app.route("/soap-quiz")
def soap_quiz():
    return render_template("soap_quiz.html")
@app.route("/soap-quiz/start")
def soap_quiz_start():
    return render_template("soap_quiz_start.html")
@app.route("/soap-quiz/result")
def soap_quiz_result():

    skin = request.args.get("skin_type")
    use = request.args.get("use_area")
    goal = request.args.get("goal")
    
    slug, match_score, reasons = recommend_soap(
        skin,
        use,
        goal
    
    )
    
    return render_template(
    "soap_quiz_result.html",
    product=next(
        p for p in products
        if p["slug"] == slug
    ),
    skin=skin,
    use=use,
    goal=goal,
    reasons=reasons,
    match_score=match_score

)
@app.route("/products/<slug>")
def product_detail(slug):

    product = next(
        (item for item in products if item["slug"] == slug),
        None
    )

    if product is None:
        abort(404)
    language = session.get("language", "en")

    product_details = {
        "coconut-bliss": {
        "en": {
        "ingredients": [
            {
                "icon": "🥥",
                "name": "Coconut Oil",
                "description": "Helps create a rich, creamy lather while leaving the skin feeling soft and moisturized."
            },
            {
                "icon": "💧",
                "name": "Vegetable Glycerin",
                "description": "Attracts moisture to help the skin feel smooth, hydrated, and refreshed."
            },
            {
                "icon": "💛",
                "name": "Vitamin E",
                "description": "A natural antioxidant that helps nourish and care for the skin."
            }
        ],
        "benefits": [
            "Deep hydration",
            "Rich, creamy lather",
            "Helps soften dry-feeling skin",
            "Gentle everyday cleansing",
            "Leaves skin feeling smooth and refreshed"
        ],
        "perfect_for": [
            "Dry Skin",
            "Normal Skin",
            "Daily Use",
            "Face & Body"
        ]
    },

        "es": {
        "ingredients": [
            {
                "icon": "🥥",
                "name": "Aceite de Coco",
                "description": "Ayuda a crear una espuma rica y cremosa, dejando la piel suave e hidratada."
            },
            {
                "icon": "💧",
                "name": "Glicerina Vegetal",
                "description": "Atrae la humedad para ayudar a mantener la piel suave, hidratada y fresca."
            },
            {
                "icon": "💛",
                "name": "Vitamina E",
                "description": "Un antioxidante natural que ayuda a nutrir y cuidar la piel."
            }
        ],
        "benefits": [
            "Hidratación profunda",
            "Espuma rica y cremosa",
            "Ayuda a suavizar la piel reseca",
            "Limpieza suave para el uso diario",
            "Deja la piel suave y fresca"
        ],
        "perfect_for": [
            "Piel Seca",
            "Piel Normal",
            "Uso Diario",
            "Rostro y Cuerpo"
        ]
    }
},

        "aloe-serenity": {
    "en": {
        "ingredients": [
            {
                "icon": "🌿",
                "name": "Aloe Vera",
                "description": "Known for its soothing and refreshing qualities, helping the skin feel calm and comfortable."
            },
            {
                "icon": "💧",
                "name": "Vegetable Glycerin",
                "description": "Helps attract moisture and leaves the skin feeling soft and hydrated."
            },
            {
                "icon": "💛",
                "name": "Vitamin E",
                "description": "Helps nourish the skin with antioxidant care."
            }
        ],
        "benefits": [
            "Soothes and refreshes",
            "Gentle cleansing",
            "Helps maintain moisture",
            "Leaves skin feeling soft",
            "Ideal for everyday use"
        ],
        "perfect_for": [
            "Sensitive Skin",
            "Normal Skin",
            "Daily Use",
            "Face & Body"
        ]
    },

    "es": {
        "ingredients": [
            {
                "icon": "🌿",
                "name": "Aloe Vera",
                "description": "Conocida por sus propiedades calmantes y refrescantes, ayuda a que la piel se sienta cómoda y revitalizada."
            },
            {
                "icon": "💧",
                "name": "Glicerina Vegetal",
                "description": "Ayuda a atraer la humedad y deja la piel suave e hidratada."
            },
            {
                "icon": "💛",
                "name": "Vitamina E",
                "description": "Ayuda a nutrir la piel con cuidado antioxidante."
            }
        ],
        "benefits": [
            "Calma y refresca la piel",
            "Limpieza suave",
            "Ayuda a mantener la hidratación",
            "Deja la piel suave",
            "Ideal para uso diario"
        ],
        "perfect_for": [
            "Piel Sensible",
            "Piel Normal",
            "Uso Diario",
            "Rostro y Cuerpo"
        ]
    }
},
"golden-turmeric": {
    "en": {
        "ingredients": [
            {
                "icon": "✨",
                "name": "Turmeric",
                "description": "A botanical ingredient valued for helping promote brighter, more radiant-looking skin."
            },
            {
                "icon": "💧",
                "name": "Vegetable Glycerin",
                "description": "Helps retain moisture and leaves the skin feeling smooth."
            },
            {
                "icon": "💛",
                "name": "Vitamin E",
                "description": "Provides antioxidant care and helps nourish the skin."
            }
        ],
        "benefits": [
            "Promotes a brighter appearance",
            "Helps improve the look of uneven tone",
            "Gentle daily cleansing",
            "Leaves skin feeling smooth",
            "Rich in antioxidant care"
        ],
        "perfect_for": [
            "Dull-Looking Skin",
            "Normal Skin",
            "Daily Use",
            "Face & Body"
        ]
    },

    "es": {
        "ingredients": [
            {
                "icon": "✨",
                "name": "Cúrcuma",
                "description": "Ingrediente botánico apreciado por ayudar a que la piel luzca más brillante y radiante."
            },
            {
                "icon": "💧",
                "name": "Glicerina Vegetal",
                "description": "Ayuda a retener la humedad y deja la piel suave."
            },
            {
                "icon": "💛",
                "name": "Vitamina E",
                "description": "Proporciona cuidado antioxidante y ayuda a nutrir la piel."
            }
        ],
        "benefits": [
            "Favorece una apariencia más luminosa",
            "Ayuda a mejorar el aspecto del tono desigual",
            "Limpieza suave diaria",
            "Deja la piel suave",
            "Rica en cuidado antioxidante"
        ],
        "perfect_for": [
            "Piel de Apariencia Opaca",
            "Piel Normal",
            "Uso Diario",
            "Rostro y Cuerpo"
        ]
    }
},
"honey-glow": {
    "en": {
        "ingredients": [
            {
                "icon": "🍯",
                "name": "Pure Honey",
                "description": "Known for its moisturizing and soothing properties, helping the skin feel soft and comfortable."
            },
            {
                "icon": "💧",
                "name": "Vegetable Glycerin",
                "description": "Helps draw moisture to the skin for a smooth and hydrated feel."
            },
            {
                "icon": "💛",
                "name": "Vitamin E",
                "description": "Helps nourish and protect the skin with antioxidant care."
            }
        ],
        "benefits": [
            "Moisturizes and softens",
            "Soothes dry-feeling skin",
            "Gentle cleansing",
            "Leaves skin feeling smooth",
            "Supports healthy-looking skin"
        ],
        "perfect_for": [
            "Dry Skin",
            "Normal Skin",
            "Daily Use",
            "Face & Body"
        ]
    },

    "es": {
        "ingredients": [
            {
                "icon": "🍯",
                "name": "Miel Pura",
                "description": "Conocida por sus propiedades hidratantes y calmantes, ayuda a que la piel se sienta suave y confortable."
            },
            {
                "icon": "💧",
                "name": "Glicerina Vegetal",
                "description": "Ayuda a atraer la humedad hacia la piel para dejarla suave e hidratada."
            },
            {
                "icon": "💛",
                "name": "Vitamina E",
                "description": "Ayuda a nutrir y proteger la piel con cuidado antioxidante."
            }
        ],
        "benefits": [
            "Hidrata y suaviza",
            "Calma la piel reseca",
            "Limpieza suave",
            "Deja la piel tersa",
            "Favorece una apariencia saludable"
        ],
        "perfect_for": [
            "Piel Seca",
            "Piel Normal",
            "Uso Diario",
            "Rostro y Cuerpo"
        ]
    }
},
"coffee-delight": {
    "en": {
        "ingredients": [
            {
                "icon": "☕",
                "name": "Coffee",
                "description": "Provides gentle exfoliation to help remove surface buildup and leave the skin feeling smoother."
            },
            {
                "icon": "💧",
                "name": "Vegetable Glycerin",
                "description": "Helps keep the skin feeling soft and hydrated after cleansing."
            },
            {
                "icon": "💛",
                "name": "Vitamin E",
                "description": "Adds nourishing antioxidant care."
            }
        ],
        "benefits": [
            "Gentle exfoliation",
            "Helps smooth rough-feeling skin",
            "Refreshes the skin",
            "Cleanses away surface buildup",
            "Leaves skin feeling renewed"
        ],
        "perfect_for": [
            "Rough Skin",
            "Body Use",
            "Occasional Exfoliation",
            "Normal Skin"
        ]
    },

    "es": {
        "ingredients": [
            {
                "icon": "☕",
                "name": "Café",
                "description": "Proporciona una exfoliación suave que ayuda a eliminar las impurezas superficiales y deja la piel más lisa."
            },
            {
                "icon": "💧",
                "name": "Glicerina Vegetal",
                "description": "Ayuda a mantener la piel suave e hidratada después de la limpieza."
            },
            {
                "icon": "💛",
                "name": "Vitamina E",
                "description": "Aporta un cuidado antioxidante que ayuda a nutrir la piel."
            }
        ],
        "benefits": [
            "Exfoliación suave",
            "Ayuda a suavizar la piel áspera",
            "Refresca la piel",
            "Elimina impurezas superficiales",
            "Deja la piel renovada"
        ],
        "perfect_for": [
            "Piel Áspera",
            "Uso Corporal",
            "Exfoliación Ocasional",
            "Piel Normal"
        ]
    }
},
"charcoal-cleanse": {
    "en": {
        "ingredients": [
            {
                "icon": "⚫",
                "name": "Activated Charcoal",
                "description": "Helps lift away excess oil and surface impurities for a fresh, clean feeling."
            },
            {
                "icon": "💧",
                "name": "Vegetable Glycerin",
                "description": "Helps prevent the skin from feeling overly dry after cleansing."
            },
            {
                "icon": "💛",
                "name": "Vitamin E",
                "description": "Helps nourish the skin with antioxidant care."
            }
        ],
        "benefits": [
            "Deep-cleansing feel",
            "Helps remove excess oil",
            "Cleanses surface impurities",
            "Leaves skin feeling fresh",
            "Suitable for regular body cleansing"
        ],
        "perfect_for": [
            "Oily Skin",
            "Combination Skin",
            "Body Use",
            "Deep Cleansing"
        ]
    },

    "es": {
        "ingredients": [
            {
                "icon": "⚫",
                "name": "Carbón Activado",
                "description": "Ayuda a eliminar el exceso de grasa y las impurezas superficiales para una sensación de limpieza profunda."
            },
            {
                "icon": "💧",
                "name": "Glicerina Vegetal",
                "description": "Ayuda a evitar que la piel se sienta reseca después de la limpieza."
            },
            {
                "icon": "💛",
                "name": "Vitamina E",
                "description": "Ayuda a nutrir la piel con cuidado antioxidante."
            }
        ],
        "benefits": [
            "Sensación de limpieza profunda",
            "Ayuda a eliminar el exceso de grasa",
            "Limpia las impurezas superficiales",
            "Deja la piel fresca",
            "Ideal para la limpieza corporal regular"
        ],
        "perfect_for": [
            "Piel Grasa",
            "Piel Mixta",
            "Uso Corporal",
            "Limpieza Profunda"
        ]
    }
},
    }
    details = product_details.get(slug, {}).get(
        language,
        {
            "ingredients": [],
            "benefits": [],
            "perfect_for": []
        }
   )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, customer_name, rating, review_text, created_at
        FROM reviews
        WHERE product_slug = ?
          AND approved = 1
        ORDER BY created_at DESC
        """,
        (slug,),
    )
    reviews = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            COUNT(*) AS review_count,
            COALESCE(AVG(rating), 0) AS average_rating
        FROM reviews
        WHERE product_slug = ?
          AND approved = 1
        """,
        (slug,),
    )
    review_summary = cursor.fetchone()

    conn.close()

    review_count = review_summary["review_count"]
    average_rating = round(review_summary["average_rating"], 1)

    return render_template(
        "product_detail.html",
        product=product,
        details=details,
        reviews=reviews,
        review_count=review_count,
        average_rating=average_rating,
        review_submitted=request.args.get("review_submitted") == "1",
        review_error=request.args.get("review_error")
    )


@app.route("/products/<slug>/reviews", methods=["POST"])
def submit_review(slug):
    product = next(
        (item for item in products if item["slug"] == slug),
        None
    )

    if product is None:
        abort(404)

    customer_name = request.form.get("customer_name", "").strip()
    rating_value = request.form.get("rating", "").strip()
    review_text = request.form.get("review_text", "").strip()

    if not customer_name:
        return redirect(
            url_for(
                "product_detail",
                slug=slug,
                review_error="Please enter your name."
            ) + "#reviews"
        )

    try:
        rating = int(rating_value)
    except (TypeError, ValueError):
        rating = 0

    if rating < 1 or rating > 5:
        return redirect(
            url_for(
                "product_detail",
                slug=slug,
                review_error="Please select a rating from 1 to 5 stars."
            ) + "#reviews"
        )

    if len(review_text) < 10:
        return redirect(
            url_for(
                "product_detail",
                slug=slug,
                review_error="Please write at least 10 characters."
            ) + "#reviews"
        )

    if len(customer_name) > 100 or len(review_text) > 2000:
        return redirect(
            url_for(
                "product_detail",
                slug=slug,
                review_error="The review is too long."
            ) + "#reviews"
        )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO reviews (
            product_slug,
            customer_name,
            rating,
            review_text,
            approved
        )
        VALUES (?, ?, ?, ?, 0)
        """,
        (
            slug,
            customer_name,
            rating,
            review_text,
        ),
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "product_detail",
            slug=slug,
            review_submitted="1"
        ) + "#reviews"
    )


@app.route("/add-to-cart/<slug>", methods=["GET", "POST"])
def add_to_cart(slug):
    cart = session.get("cart", {})

    cart[slug] = cart.get(slug, 0) + 1

    session["cart"] = cart
    return redirect(url_for("cart"))
@app.route("/ingredients")
def ingredients():
    return render_template("ingredients.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/search")
def search():
    return render_template("search.html")


@app.route("/account")
def account():
    return render_template("account.html")

@app.route("/cart")
def cart():
    cart = session.get("cart", {})
    cart_items = []
    total = 0

    for slug, quantity in cart.items():
        product = next((p for p in products if p["slug"] == slug), None)

        if product:
            subtotal = product["price"] * quantity
            total += subtotal

            cart_items.append({
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal
            })

    cart_slugs = set(cart.keys())

    recommended_products = [
    product
    for product in products
    if product["slug"] not in cart_slugs
    ][:3]

    return render_template(
    "cart.html",
    cart_items=cart_items,
    total=total,
    recommended_products=recommended_products
)
@app.route("/update-cart/<slug>", methods=["POST"])
def update_cart(slug):
    cart = session.get("cart", {})

    if slug not in cart:
        return redirect(url_for("cart"))

    action = request.form.get("action")

    if action == "increase":
        cart[slug] += 1

    elif action == "decrease":
        cart[slug] -= 1

        if cart[slug] <= 0:
            cart.pop(slug)

    session["cart"] = cart
    session.modified = True

    return redirect(url_for("cart"))
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", {})

    if not cart:
        return redirect(url_for("cart"))

    cart_items = []
    total = 0

    for slug, quantity in cart.items():
        product = next((p for p in products if p["slug"] == slug), None)

        if product:
            subtotal = product["price"] * quantity
            total += subtotal
            cart_items.append({
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal
            })

    if request.method == "POST":
        customer = {
            "first_name": request.form.get("first_name"),
            "last_name": request.form.get("last_name"),
            "email": request.form.get("email"),
            "phone": request.form.get("phone"),
            "address": request.form.get("address"),
            "city": request.form.get("city"),
            "state": request.form.get("state"),
            "zip_code": request.form.get("zip_code"),
            "notes": request.form.get("notes"),
        }

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM orders")
        order_count = cursor.fetchone()[0] + 1
        order_number = f"PET-{100000 + order_count}"

        cursor.execute("""
            INSERT INTO orders (
                order_number, first_name, last_name, email, phone,
                address, city, state, zip_code, notes, total, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_number,
            customer["first_name"],
            customer["last_name"],
            customer["email"],
            customer["phone"],
            customer["address"],
            customer["city"],
            customer["state"],
            customer["zip_code"],
            customer["notes"],
            total,
            "Pending Payment"
        ))

        order_id = cursor.lastrowid

        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, product_name, product_slug, quantity, price, subtotal
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                item["product"]["name"],
                item["product"]["slug"],
                item["quantity"],
                item["product"]["price"],
                item["subtotal"]
            ))

        conn.commit()
        conn.close()

        session["customer"] = customer
        session["order_number"] = order_number
        session["order_id"] = order_id
        return redirect(url_for("payment"))

    return render_template("checkout.html", cart_items=cart_items, total=total)

@app.route("/payment")
def payment():
    customer = session.get("customer")
    order_number = session.get("order_number")
    cart = session.get("cart", {})

    if not customer or not cart:
        return redirect(url_for("checkout"))

    return render_template("payment.html", customer=customer, order_number=order_number)

@app.route("/remove-from-cart/<slug>")
def remove_from_cart(slug):
    cart = session.get("cart", {})

    if slug in cart:
        del cart[slug]

    session["cart"] = cart
    return redirect(url_for("cart"))
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM admin_users WHERE username = ?", (username,))
        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            login_user(AdminUser(user["id"], user["username"]))
            return redirect(url_for("admin_orders"))

        error = "Invalid username or password"

    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin_login"))

@app.route("/admin/orders")
@login_required
def admin_orders():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, order_number, first_name, last_name, email, total, status, created_at
        FROM orders
        ORDER BY created_at DESC
    """)

    orders = cursor.fetchall()

    conn.close()

    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/orders/<int:order_id>")
@login_required
def admin_order_detail(order_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = cursor.fetchall()

    conn.close()

    return render_template("admin_order_detail.html", order=order, items=items)

@app.route("/admin")
@login_required
def admin_dashboard():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Total Orders
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    
    # Total Products
    total_products = len(products)
    
    # Total Customers
    cursor.execute("SELECT COUNT(DISTINCT email) FROM orders")
    total_customers = cursor.fetchone()[0]

    # Total Revenue
    cursor.execute("SELECT IFNULL(SUM(total), 0) FROM orders")
    total_revenue = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_orders=total_orders,
        total_customers=total_customers,
        total_products=total_products,
        total_revenue=total_revenue
    )
@app.route("/admin/customers")
@login_required
def admin_customers():
    return render_template("admin_customers.html")


@app.route("/admin/suppliers")
@login_required
def admin_suppliers():
    return render_template("admin_suppliers.html")


@app.route("/admin/products")
@login_required
def admin_products():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()

    conn.close()

    return render_template("admin_products.html", products=products)

@app.route("/admin/products/add", methods=["GET", "POST"])
@login_required
def admin_add_product():
    if request.method == "POST":
        name = request.form.get("name")
        slug = request.form.get("slug")
        description = request.form.get("description")
        price = request.form.get("price")
        stock = request.form.get("stock")
        image_file = request.files.get("image")
        image = ""

        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join("static/images/products", filename)
            image_file.save(image_path)
            image = filename
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO products (name, slug, description, price, image, stock)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, slug, description, price, image, stock))

        conn.commit()
        conn.close()

        return redirect("/admin/products")

    return render_template("admin_add_product.html")
@app.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
def admin_edit_product(product_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name")
        slug = request.form.get("slug")
        description = request.form.get("description")
        price = request.form.get("price")
        stock = request.form.get("stock")
        image = request.form.get("image")
        status = request.form.get("status")

        cursor.execute("""
            UPDATE products
            SET name = ?, slug = ?, description = ?, price = ?, image = ?, stock = ?, status = ?
            WHERE id = ?
        """, (name, slug, description, price, image, stock, status, product_id))

        conn.commit()
        conn.close()

        return redirect("/admin/products")

    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()

    return render_template("admin_edit_product.html", product=product)
@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
@login_required
def admin_delete_product(product_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))

    conn.commit()
    conn.close()

    return redirect("/admin/products")
@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST":

        cursor.execute("""
            UPDATE store_settings
            SET business_name=?,
                owner_name=?,
                contact_email=?,
                website=?,
                phone=?,
                address=?,
                city=?,
                state=?,
                zip_code=?
            WHERE id=1
        """, (

            request.form["business_name"],
            request.form["owner_name"],
            request.form["contact_email"],
            request.form["website"],
            request.form["phone"],
            request.form["address"],
            request.form["city"],
            request.form["state"],
            request.form["zip_code"]

        ))

        conn.commit()

    cursor.execute("SELECT * FROM store_settings WHERE id=1")
    settings = cursor.fetchone()

    conn.close()

    return render_template(
        "admin_settings.html",
        settings=settings
    )

@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    new_status = request.form.get("status")

    allowed_statuses = [
        "Pending Payment",
        "Paid",
        "Preparing",
        "Packed",
        "Shipped",
        "Delivered",
        "Cancelled"
    ]

    if new_status not in allowed_statuses:
        return redirect(url_for("admin_order_detail", order_id=order_id))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (new_status, order_id))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_order_detail", order_id=order_id))

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    cart = session.get("cart", {})

    if not cart:
        return redirect(url_for("cart"))

    line_items = []

    for slug, quantity in cart.items():
        product = next((p for p in products if p["slug"] == slug), None)

        if product:
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": product["name"],
                    },
                    "unit_amount": int(product["price"] * 100),
                },
                "quantity": quantity,
            })

    print("=== ENTERING STRIPE CHECKOUT ===")
    print("Cart:", cart)
    print("Line items:", line_items)
    print("Stripe key loaded:", bool(stripe.api_key))
    print("Domain:", os.getenv("DOMAIN"))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=os.getenv("DOMAIN") + "/payment-success",
            cancel_url=os.getenv("DOMAIN") + "/cart",
        )
    except Exception as e:
        print("STRIPE ERROR:", repr(e))
        raise

    return redirect(checkout_session.url, code=303)
@app.route("/payment-success")
def payment_success():
    order_id = session.get("order_id")
    order_number = session.get("order_number")

    if order_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE orders
            SET status = ?
            WHERE id = ?
        """, ("Paid", order_id))

        conn.commit()
        conn.close()

        send_order_confirmation_email(order_id)

    session.pop("cart", None)

    return render_template(
        "payment_success.html",
        order_number=order_number
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

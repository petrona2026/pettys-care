import sqlite3
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from flask import Flask, render_template,session, redirect, url_for, request
import os
import stripe
from dotenv import load_dotenv

load_dotenv()
print("Stripe Key:", os.getenv("STRIPE_SECRET_KEY"))
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
app = Flask(__name__)
app.secret_key = "pettys-secret-key-change-later"
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"

class AdminUser(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect("pettys.db")
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
        "short": "Crafted with coconut oil and Vitamin E.",
        "price": 8.00,
        "image": "products_update/01-coconut-bliss.png",
    },
    {
        "id": 2,
        "name": "Aloe Serenity",
        "slug": "aloe-serenity",
        "short": "A soothing aloe vera soap with Vitamin E.",
        "price": 8.00,
        "image": "products_update/02-aloe-serenity.png",
    },
    {
        "id": 3,
        "name": "Golden Turmeric",
        "slug": "golden-turmeric",
        "short": "A warm botanical soap with turmeric and Vitamin E.",
        "price": 8.00,
        "image": "products_update/03-golden-turmeric.png",
    },
    {
        "id": 4,
        "name": "Honey Glow",
        "slug": "honey-glow",
        "short": "A comforting honey and oatmeal soap.",
        "price": 8.00,
        "image": "products_update/04-honey-glow.png",
    },
    {
        "id": 5,
        "name": "Coffee Delight",
        "slug": "coffee-delight",
        "short": "A rich coffee-inspired handcrafted soap.",
        "price": 8.00,
        "image": "products_update/05-coffee-delight.png",
    },
    {
        "id": 6,
        "name": "Charcoal Cleanse",
        "slug": "charcoal-cleanse",
        "short": "A bold activated charcoal soap.",
        "price": 8.00,
        "image": "products_update/06-charcoal-cleanse.png",
    },
]

@app.route("/")
def index():
    return render_template("index.html", products=products)

@app.route("/shop")
def shop():
    return render_template("shop.html", products=products)
@app.route("/products")
def product_list():
    return render_template("products.html", products=products)

@app.route("/products/<slug>")
def product_detail(slug):
    product = next((p for p in products if p["slug"] == slug), None)
    return render_template("product_detail.html", product=product)
@app.route("/add-to-cart/<slug>")
def add_to_cart(slug):
    cart = session.get("cart", {})

    cart[slug] = cart.get(slug, 0) + 1

    session["cart"] = cart
    return redirect(url_for("cart"))


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

    return render_template("cart.html", cart_items=cart_items, total=total)
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

        conn = sqlite3.connect("pettys.db")
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

        conn = sqlite3.connect("pettys.db")
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
    conn = sqlite3.connect("pettys.db")
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
    conn = sqlite3.connect("pettys.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = cursor.fetchall()

    conn.close()

    return render_template("admin_order_detail.html", order=order, items=items)

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

    conn = sqlite3.connect("pettys.db")
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

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=os.getenv("DOMAIN") + "/payment-success",
        cancel_url=os.getenv("DOMAIN") + "/cart",
    )

    return redirect(checkout_session.url, code=303)

@app.route("/payment-success")
def payment_success():
    order_id = session.get("order_id")
    order_number = session.get("order_number")

    if order_id:
        conn = sqlite3.connect("pettys.db")
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE orders
            SET status = ?
            WHERE id = ?
        """, ("Paid", order_id))

        conn.commit()
        conn.close()

    session.pop("cart", None)

    return render_template(
        "payment_success.html",
        order_number=order_number
    )
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

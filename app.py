from flask import Flask, render_template,session, redirect, url_for, request

app = Flask(__name__)
app.secret_key = "pettys-secret-key-change-later"
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

        session["customer"] = customer
        return redirect(url_for("payment"))

    return render_template("checkout.html", cart_items=cart_items, total=total)


@app.route("/payment")
def payment():
    customer = session.get("customer")
    cart = session.get("cart", {})

    if not customer or not cart:
        return redirect(url_for("checkout"))

    return render_template("payment.html", customer=customer)


@app.route("/remove-from-cart/<slug>")
def remove_from_cart(slug):
    cart = session.get("cart", {})

    if slug in cart:
        del cart[slug]

    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

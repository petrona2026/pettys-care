from flask import Flask, render_template

app = Flask(__name__)

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

@app.route("/about")
def about():
    return render_template("about.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

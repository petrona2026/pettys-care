from flask import Flask, render_template

app = Flask(__name__)

products = [
    {
        "id": 1,
        "name": "Coconut Bliss",
        "slug": "coconut-bliss",
        "short": "Crafted with coconut oil and Vitamin E.",
        "price": 8.00,
        "image": "products/coconut-bliss.png",
    },
    {
        "id": 2,
        "name": "Aloe Serenity",
        "slug": "aloe-serenity",
        "short": "A soothing aloe vera soap with Vitamin E.",
        "price": 8.00,
        "image": "products/aloe-vera.png",
    },
    {
        "id": 3,
        "name": "Golden Turmeric",
        "slug": "golden-turmeric",
        "short": "A warm botanical soap with turmeric and Vitamin E.",
        "price": 8.00,
        "image": "products/golden-turmeric.png",
    },
    {
        "id": 4,
        "name": "Honey Harvest",
        "slug": "honey-harvest",
        "short": "A comforting honey and oatmeal soap.",
        "price": 8.00,
        "image": "products/honey-harvest.png",
    },
    {
        "id": 5,
        "name": "Coffee Invigorate",
        "slug": "coffee-invigorate",
        "short": "A rich coffee-inspired handcrafted soap.",
        "price": 8.00,
        "image": "products/coffee-invigorate.png",
    },
    {
        "id": 6,
        "name": "Midnight Charcoal",
        "slug": "midnight-charcoal",
        "short": "A bold activated charcoal soap.",
        "price": 8.00,
        "image": "products/charcoal-cleanse.png",
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

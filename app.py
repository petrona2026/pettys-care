import os
import json
import sqlite3
import subprocess
import resend
import stripe
from flask import send_file
from pathlib import Path

from product_service import get_all_products
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, session, url_for, flash
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
def ensure_order_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Make sure the orders table exists first
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)

    order_columns = {row[1] for row in cursor.execute("PRAGMA table_info(orders)")}

    if "subtotal" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN subtotal REAL DEFAULT 0")

    if "shipping_amount" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN shipping_amount REAL DEFAULT 0")

    if "tax_amount" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN tax_amount REAL DEFAULT 0")

    # Only check order_items if it exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='order_items'
    """)

    if cursor.fetchone():
        item_columns = {row[1] for row in cursor.execute("PRAGMA table_info(order_items)")}

        if "size_code" not in item_columns:
            cursor.execute("ALTER TABLE order_items ADD COLUMN size_code TEXT")

        if "size_name" not in item_columns:
            cursor.execute("ALTER TABLE order_items ADD COLUMN size_name TEXT")

    conn.commit()
    conn.close()


ensure_order_schema()
def ensure_store_settings_table():
    conn = sqlite3.connect(DB_PATH)
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        1,
        "PETTY'S CARE",
        "Petronila",
        "petronila@pettyscare.com",
        "https://pettyscare.com",
        "USD",
        0,
        0
    ))

    conn.commit()
    conn.close()


ensure_store_settings_table()
def ensure_reviews_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_slug TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            review_text TEXT NOT NULL DEFAULT '',
            approved INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(reviews)")
    existing_columns = {
        row[1] for row in cursor.fetchall()
    }

    if "product_slug" not in existing_columns:
        cursor.execute(
            "ALTER TABLE reviews ADD COLUMN product_slug TEXT"
        )

    if "customer_name" not in existing_columns:
        cursor.execute(
            "ALTER TABLE reviews ADD COLUMN customer_name TEXT"
        )

    if "rating" not in existing_columns:
        cursor.execute(
            "ALTER TABLE reviews ADD COLUMN rating INTEGER DEFAULT 0"
        )

    if "review_text" not in existing_columns:
        cursor.execute(
            "ALTER TABLE reviews ADD COLUMN review_text TEXT DEFAULT ''"
        )

    if "approved" not in existing_columns:
        cursor.execute(
            "ALTER TABLE reviews ADD COLUMN approved INTEGER DEFAULT 0"
        )

    if "created_at" not in existing_columns:
        cursor.execute(
            "ALTER TABLE reviews ADD COLUMN created_at TIMESTAMP"
        )
        cursor.execute(
            """
            UPDATE reviews
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )

    conn.commit()
    conn.close()
ensure_reviews_table()

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

def ensure_store_settings_table():
    conn = sqlite3.connect(DB_PATH)
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
@app.route("/set-language/<language>")
def set_language(language):
    if language not in ("en", "es"):
        language = "en"

    session["language"] = language
    return redirect(request.referrer or url_for("index"))
@app.route("/admin/inventory")
@login_required
def admin_inventory():
    try:
        products = get_all_products()
        return render_template(
            "admin_inventory.html",
            products=products
        )

    except Exception:
        import traceback
        error_details = traceback.format_exc()
        print(error_details)

        return f"""
        <html>
            <head>
                <title>Inventory Error</title>
            </head>
            <body style="font-family: monospace; padding: 30px;">
                <h1>Inventory Error</h1>
                <pre>{error_details}</pre>
            </body>
        </html>
        """, 500
@app.route("/admin/inventory/<int:product_id>/update", methods=["POST"])
@login_required
def update_inventory(product_id):
    try:
        discovery_stock = int(request.form.get("discovery_stock", 0))
        classic_stock = int(request.form.get("classic_stock", 0))
    except (TypeError, ValueError):
        flash("Stock quantities must be valid whole numbers.", "error")
        return redirect(url_for("admin_inventory"))

    if discovery_stock < 0 or classic_stock < 0:
        flash("Stock quantities cannot be negative.", "error")
        return redirect(url_for("admin_inventory"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE product_sizes
            SET stock = ?
            WHERE product_id = ?
              AND size_code = 'mini'
        """, (discovery_stock, product_id))

        cursor.execute("""
            UPDATE product_sizes
            SET stock = ?
            WHERE product_id = ?
              AND size_code = 'standard'
        """, (classic_stock, product_id))

        conn.commit()
        flash("Inventory updated successfully.", "success")

    except sqlite3.Error as error:
        conn.rollback()
        print(f"Inventory update error: {error}")
        flash("Inventory could not be updated.", "error")

    finally:
        conn.close()

    return redirect(url_for("admin_inventory"))

@app.route("/admin/print-studio/product-inserts")
@login_required
def admin_product_inserts():
    products = get_all_products()

    selected_slug = session.get(
        "product_insert_slug",
        products[0]["slug"] if products else "",
    )

    return render_template(
        "admin_product_inserts.html",
        products=products,
        selected_slug=selected_slug,
    )

@app.route(
    "/admin/print-studio/product-inserts/generate",
    methods=["POST"],
)
@login_required
def generate_product_insert():
    product_slug = request.form.get("product_slug", "").strip()

    if not product_slug:
        flash("Select a product first.", "error")
        return redirect(url_for("admin_product_inserts"))

    try:
        subprocess.run(
            [
                "python",
                "printing/product_inserts/generate.py",
                product_slug,
            ],
            check=True,
        )

        session["product_insert_slug"] = product_slug

        flash(
            "The product insert was generated.",
            "success",
        )

    except subprocess.CalledProcessError:
        flash(
            "The product insert could not be generated.",
            "error",
        )

    return redirect(url_for("admin_product_inserts"))


@app.route("/admin/print-studio/product-inserts/preview")
@login_required
def preview_product_insert():
    product_slug = request.args.get(
        "product_slug",
        session.get("product_insert_slug", ""),
    ).strip()

    if not product_slug:
        flash(
            "Generate a product insert first.",
            "error",
        )
        return redirect(url_for("admin_product_inserts"))

    pdf_path = Path(
        f"generated_pdfs/product_inserts/"
        f"{product_slug}_product_inserts.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate this product insert first.",
            "error",
        )
        return redirect(url_for("admin_product_inserts"))

    response = send_file(
        pdf_path,
        mimetype="application/pdf",
        conditional=False,
        max_age=0,
    )

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

@app.route(
    "/admin/print-studio/product-inserts/print",
    methods=["POST"],
)
@login_required
def print_product_insert():
    product_slug = request.form.get(
        "product_slug",
        session.get("product_insert_slug", ""),
    ).strip()

    if not product_slug:
        flash("Select a product first.", "error")
        return redirect(url_for("admin_product_inserts"))

    pdf_path = Path(
        f"generated_pdfs/product_inserts/"
        f"{product_slug}_product_inserts.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate this product insert first.",
            "error",
        )
        return redirect(url_for("admin_product_inserts"))

    settings_file = Path("printing/printer_settings.json")

    try:
        with settings_file.open("r", encoding="utf-8") as file:
            printer_settings = json.load(file)

        printer_name = printer_settings.get(
            "default_printer",
            "",
        )

        if not printer_name:
            flash(
                "Select a default printer in Printer Settings.",
                "error",
            )
            return redirect(url_for("admin_product_inserts"))

        subprocess.run(
            [
                "lp",
                "-d",
                printer_name,
                str(pdf_path),
            ],
            check=True,
        )

        flash(
            f"The product insert was sent to {printer_name}.",
            "success",
        )

    except (OSError, json.JSONDecodeError):
        flash(
            "The printer settings could not be read.",
            "error",
        )

    except subprocess.CalledProcessError:
        flash(
            "The product insert could not be printed.",
            "error",
        )

    return redirect(url_for("admin_product_inserts"))

@app.route(
    "/admin/print-studio/printer-settings/test",
    methods=["POST"],
)
@login_required
def printer_test_page():
    settings_file = Path("printing/printer_settings.json")
    test_file = Path("generated_pdfs/printer_test.pdf")

    try:
        with settings_file.open("r", encoding="utf-8") as file:
            printer_settings = json.load(file)

        printer_name = printer_settings.get(
            "default_printer",
            "",
        )

        if not printer_name:
            flash(
                "Select a default printer first.",
                "error",
            )
            return redirect(url_for("printer_settings"))

        test_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        pdf = canvas.Canvas(
            str(test_file),
            pagesize=letter,
        )

        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawCentredString(
            306,
            700,
            "PETTY'S CARE",
        )

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(
            306,
            665,
            "Printer Test",
        )

        pdf.setFont("Helvetica", 12)
        pdf.drawCentredString(
            306,
            630,
            f"Printer: {printer_name}",
        )

        pdf.drawCentredString(
            306,
            600,
            "Status: SUCCESS",
        )

        pdf.save()

        subprocess.run(
            [
                "lp",
                "-d",
                printer_name,
                str(test_file),
            ],
            check=True,
        )

        flash(
            f"Test page was sent to {printer_name}.",
            "success",
        )

    except (OSError, json.JSONDecodeError):
        flash(
            "Printer settings could not be read.",
            "error",
        )

    except subprocess.CalledProcessError:
        flash(
            "The test page could not be printed.",
            "error",
        )

    return redirect(url_for("printer_settings"))



@app.route(
    "/admin/print-studio/printer-settings",
    methods=["GET", "POST"],
)
@login_required
def printer_settings():
    settings_file = Path("printing/printer_settings.json")

    default_settings = {
        "default_printer": "",
        "business_cards_printer": "",
        "labels_printer": "",
        "paper_size": "Letter",
    }

    if settings_file.exists():
        with settings_file.open("r", encoding="utf-8") as file:
            settings = json.load(file)
    else:
        settings = default_settings.copy()

    printers = []
    printer_detection_available = True

    try:
        result = subprocess.run(
            ["lpstat", "-p"],
            capture_output=True,
            text=True,
            check=False,
        )

        for line in result.stdout.splitlines():
            line = line.strip()

            if line.startswith("printer "):
                parts = line.split()

                if len(parts) >= 2:
                    printers.append(parts[1])

    except FileNotFoundError:
        # Railway (or another server) does not have lpstat/CUPS.
        printer_detection_available = False
        printers = []

    except OSError:
        printer_detection_available = False
        printers = []
        saved_printers = [
        settings.get("default_printer", ""),
        settings.get("business_cards_printer", ""),
        settings.get("labels_printer", ""),
    ]

    for printer_name in saved_printers:
        if printer_name and printer_name not in printers:
            printers.append(printer_name) 
    
    if request.method == "POST":
        settings["default_printer"] = request.form.get(
            "default_printer",
            "",
        )

        settings["business_cards_printer"] = request.form.get(
            "business_cards_printer",
            "",
        )

        settings["labels_printer"] = request.form.get(
            "labels_printer",
            "",
        )

        settings["paper_size"] = request.form.get(
            "paper_size",
            "Letter",
        )

        settings_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with settings_file.open("w", encoding="utf-8") as file:
            json.dump(settings, file, indent=2)

        flash(
            "Printer settings were saved.",
            "success",
        )

        return redirect(
            url_for("printer_settings")
        )

    return render_template(
        "admin_printer_settings.html",
        settings=settings,
        printers=printers,
        printer_detection_available=printer_detection_available,
    )

@app.route("/admin/print-studio/thank-you-cards/preview")
@login_required
def preview_thank_you_cards():
    pdf_path = Path(
        "generated_pdfs/thank_you_cards/pettys_thank_you_cards.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate the thank-you cards first.",
            "error",
        )
        return redirect(
            url_for("admin_thank_you_cards")
        )

    return send_file(
        pdf_path,
        mimetype="application/pdf",
    )



@app.route(
    "/admin/print-studio/thank-you-cards/generate",
    methods=["POST"],
)
@login_required
def generate_thank_you_cards():
    try:
        subprocess.run(
            [
                "python",
                "printing/thank_you_cards/generate.py",
            ],
            check=True,
        )

        flash(
            "The thank-you card sheet was generated.",
            "success",
        )

    except subprocess.CalledProcessError:
        flash(
            "The thank-you card sheet could not be generated.",
            "error",
        )

    return redirect(
        url_for("admin_thank_you_cards")
    )


@app.route(
    "/admin/print-studio/thank-you-cards/print",
    methods=["POST"],
)
@login_required
def print_thank_you_cards():
    pdf_path = Path(
        "generated_pdfs/thank_you_cards/pettys_thank_you_cards.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate the thank-you cards first.",
            "error",
        )
        return redirect(
            url_for("admin_thank_you_cards")
        )

    settings_file = Path("printing/printer_settings.json")

    try:
        with settings_file.open("r", encoding="utf-8") as file:
            printer_settings = json.load(file)

        printer_name = printer_settings.get(
            "default_printer",
            "",
        )

        if not printer_name:
            flash(
                "Select a default printer in Printer Settings.",
                "error",
            )
            return redirect(
                url_for("admin_thank_you_cards")
            )

        subprocess.run(
            [
                "lp",
                "-d",
                printer_name,
                str(pdf_path),
            ],
            check=True,
        )

        flash(
            f"The thank-you cards were sent to {printer_name}.",
            "success",
        )

    except (OSError, json.JSONDecodeError):
        flash(
            "The printer settings could not be read.",
            "error",
        )

    except subprocess.CalledProcessError:
        flash(
            "The thank-you cards could not be printed.",
            "error",
        )

    return redirect(
        url_for("admin_thank_you_cards")
    )

@app.route(
    "/admin/print-studio/labels/print",
    methods=["POST"],
)


@login_required
def print_logo_stickers():
    pdf_path = Path(
        "generated_pdfs/labels/logo_stickers_test.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate the label sheet first.",
            "error",
        )
        return redirect(
            url_for("admin_label_studio")
        )

    settings_file = Path("printing/printer_settings.json")

    try:
        with settings_file.open("r", encoding="utf-8") as file:
            printer_settings = json.load(file)

        printer_name = printer_settings.get(
            "labels_printer",
            "",
        )

        if not printer_name:
            flash(
                "Select a labels printer in Printer Settings.",
                "error",
            )
            return redirect(
                url_for("admin_label_studio")
            )

        subprocess.run(
            [
                "lp",
                "-d",
                printer_name,
                str(pdf_path),
            ],
            check=True,
        )

        flash(
            f"The label sheet was sent to {printer_name}.",
            "success",
        )

    except (OSError, json.JSONDecodeError):
        flash(
            "The printer settings could not be read.",
            "error",
        )

    except subprocess.CalledProcessError:
        flash(
            "The label sheet could not be printed.",
            "error",
        )

    return redirect(
        url_for("admin_label_studio")
    )

@app.route("/admin/print-studio/labels/preview")
@login_required
def preview_logo_stickers():
    pdf_path = Path(
        "generated_pdfs/labels/logo_stickers_test.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate the label sheet first.",
            "error",
        )
        return redirect(
            url_for("admin_label_studio")
        )

    return send_file(
        pdf_path,
        mimetype="application/pdf",
    )
@app.route(
    "/admin/print-studio/labels/generate",
    methods=["POST"],
)
@login_required
def generate_logo_stickers():
    try:
        subprocess.run(
            [
                "python",
                "printing/labels/logo_stickers.py",
            ],
            check=True,
        )

        flash(
            "The Avery 22877 label sheet was generated.",
            "success",
        )

    except subprocess.CalledProcessError:
        flash(
            "The label sheet could not be generated.",
            "error",
        )

    return redirect(
        url_for("admin_label_studio")
    )

@app.route(
    "/admin/print-studio/business-cards/print-front",
    methods=["POST"],
)
@login_required
def print_business_card_front():
    pdf_path = Path(
        "generated_pdfs/pettys_business_cards_front.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate the business cards first.",
            "error",
        )
        return redirect(url_for("admin_business_cards"))

    settings_file = Path("printing/printer_settings.json")

    try:
        with settings_file.open("r", encoding="utf-8") as file:
            printer_settings = json.load(file)

        printer_name = printer_settings.get(
            "business_cards_printer",
            "",
        )

        if not printer_name:
            flash(
                "Select a business-card printer in Printer Settings.",
                "error",
            )
            return redirect(url_for("admin_business_cards"))

        subprocess.run(
            [
                "lp",
                "-d",
                printer_name,
                str(pdf_path),
            ],
            check=True,
        )

        flash(
            f"The front sheet was sent to {printer_name}.",
            "success",
        )

    except (OSError, json.JSONDecodeError):
        flash(
            "The printer settings could not be read.",
            "error",
        )

    except subprocess.CalledProcessError:
        flash(
            "The front sheet could not be printed.",
            "error",
        )

    return redirect(url_for("admin_business_cards"))

@app.route("/admin/print-studio/thank-you-cards")
@login_required
def admin_thank_you_cards():
    return render_template("admin_thank_you_cards.html")


@app.route(
    "/admin/print-studio/business-cards/print-back",
    methods=["POST"],
)
@login_required
def print_business_card_back():
    pdf_path = Path(
        "generated_pdfs/pettys_business_cards_back.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate the business cards first.",
            "error",
        )
        return redirect(url_for("admin_business_cards"))

    settings_file = Path("printing/printer_settings.json")

    try:
        with settings_file.open("r", encoding="utf-8") as file:
            printer_settings = json.load(file)

        printer_name = printer_settings.get(
            "business_cards_printer",
            "",
        )

        if not printer_name:
            flash(
                "Select a business-card printer in Printer Settings.",
                "error",
            )
            return redirect(url_for("admin_business_cards"))

        subprocess.run(
            [
                "lp",
                "-d",
                printer_name,
                str(pdf_path),
            ],
            check=True,
        )

        flash(
            f"The back sheet was sent to {printer_name}.",
            "success",
        )

    except (OSError, json.JSONDecodeError):
        flash(
            "The printer settings could not be read.",
            "error",
        )

    except subprocess.CalledProcessError:
        flash(
            "The back sheet could not be printed.",
            "error",
        )

    return redirect(url_for("admin_business_cards"))

@app.route(
    "/admin/print-studio/labels",
    methods=["GET", "POST"],
)
@login_required
def admin_label_studio():
    calibration_file = Path("printing/calibration.json")

    position_names = [
        "A1", "B1", "C1",
        "A2", "B2", "C2",
        "A3", "B3", "C3",
        "A4", "B4", "C4",
    ]

    default_positions = {
        position_name: {
            "x": 0.0,
            "y": 0.0,
        }
        for position_name in position_names
    }

    default_data = {
        "avery_22877": {
            "global_x": 0.0,
            "global_y": 0.0,
            "positions": default_positions,
        },
        "avery_5877": {
            "x_offset": 0.0,
            "y_offset": 0.0,
        },
    }

    try:
        if calibration_file.exists():
            with calibration_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                calibration_data = json.load(file)
        else:
            calibration_data = default_data

    except (OSError, json.JSONDecodeError):
        calibration_data = default_data

    label_calibration = calibration_data.get(
        "avery_22877",
        default_data["avery_22877"],
    )

    global_x = float(
        label_calibration.get(
            "global_x",
            label_calibration.get("x_offset", 0.0),
        )
    )

    global_y = float(
        label_calibration.get(
            "global_y",
            label_calibration.get("y_offset", 0.0),
        )
    )

    saved_positions = label_calibration.get(
        "positions",
        {},
    )

    positions = {}

    for position_name in position_names:
        saved_position = saved_positions.get(
            position_name,
            {},
        )

        positions[position_name] = {
            "x": float(
                saved_position.get("x", 0.0)
            ),
            "y": float(
                saved_position.get("y", 0.0)
            ),
        }

    if request.method == "POST":
        try:
            global_x = float(
                request.form.get("global_x", 0.0)
            )

            global_y = float(
                request.form.get("global_y", 0.0)
            )

            for position_name in position_names:
                positions[position_name]["x"] = float(
                    request.form.get(
                        f"{position_name}_x",
                        positions[position_name]["x"],
                    )
                )

                positions[position_name]["y"] = float(
                    request.form.get(
                        f"{position_name}_y",
                        positions[position_name]["y"],
                    )
                )

        except (TypeError, ValueError):
            flash(
                "Please enter valid calibration numbers.",
                "error",
            )
            return redirect(
                url_for("admin_label_studio")
            )

        calibration_data["avery_22877"] = {
            "global_x": global_x,
            "global_y": global_y,
            "positions": positions,
        }

        calibration_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with calibration_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                calibration_data,
                file,
                indent=2,
            )

        flash(
            "Avery 22877 matrix calibration was saved.",
            "success",
        )

        return redirect(
            url_for("admin_label_studio")
        )

    return render_template(
        "admin_label_studio.html",
        global_x=global_x,
        global_y=global_y,
        positions=positions,
        position_names=position_names,
    )

@app.route("/admin/print-studio/business-cards/front")
@login_required
def preview_business_card_front():
    pdf_path = Path(
        "generated_pdfs/pettys_business_cards_front.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate the business cards first.",
            "error",
        )
        return redirect(url_for("admin_business_cards"))

    return send_file(
        pdf_path,
        mimetype="application/pdf",
    )


@app.route("/admin/print-studio/business-cards/back")
@login_required
def preview_business_card_back():
    pdf_path = Path(
        "generated_pdfs/pettys_business_cards_back.pdf"
    )

    if not pdf_path.exists():
        flash(
            "Generate the business cards first.",
            "error",
        )
        return redirect(url_for("admin_business_cards"))

    return send_file(
        pdf_path,
        mimetype="application/pdf",
    )
@app.route("/admin/print-studio")
@login_required
def admin_print_studio():
    return render_template("admin_print_studio.html")
@app.route("/admin/print-studio/business-cards")
@login_required
def admin_business_cards():
    return render_template("admin_business_cards.html")
@app.route("/admin/print-studio/business-cards/generate", methods=["POST"])
@login_required
def generate_business_cards():
    try:
        subprocess.run(
            ["python", "printing/business_cards.py"],
            check=True,
        )

        flash("Business card front and back PDFs were created successfully.", "success")

    except subprocess.CalledProcessError:
        flash("The business card PDFs could not be created.", "error")

    return redirect(url_for("admin_business_cards"))
@app.route("/admin/products-manager")
@login_required
def admin_products_manager():

    products = get_all_products(active_only=False)

    return render_template(
        "admin_products_manager.html",
        products=products
    )
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
    "price": 8.99,
    "regular_price": 12.00,
    "sizes": [
    {
        "id": "mini",
        "name": "Mini Bar",
        "weight": "2 oz",
        "price": 5.99
    },
    {
        "id": "standard",
        "name": "Standard Bar",
        "weight": "4 oz",
        "price": 8.99,
        "regular_price": 12.00
    }
],
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
    "price": 8.99,
    "regular_price": 12.00,
    "sizes": [
    {
        "id": "mini",
        "name": "Mini Bar",
        "weight": "2 oz",
        "price": 5.99
    },
    {
        "id": "standard",
        "name": "Standard Bar",
        "weight": "4 oz",
        "price": 8.99,
        "regular_price": 12.00
    }
],
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
    "price": 8.99,
    "regular_price": 12.00,
    "sizes": [
    {
        "id": "mini",
        "name": "Mini Bar",
        "weight": "2 oz",
        "price": 5.99
    },
    {
        "id": "standard",
        "name": "Standard Bar",
        "weight": "4 oz",
        "price": 8.99,
        "regular_price": 12.00
    }
],
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
    "price": 8.99,
    "regular_price": 12.00,
    "sizes": [
    {
        "id": "mini",
        "name": "Mini Bar",
        "weight": "2 oz",
        "price": 5.99
    },
    {
        "id": "standard",
        "name": "Standard Bar",
        "weight": "4 oz",
        "price": 8.99,
        "regular_price": 12.00
    }
],
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
    "price": 8.99,
    "regular_price": 12.00,
    "sizes": [
    {
        "id": "mini",
        "name": "Mini Bar",
        "weight": "2 oz",
        "price": 5.99
    },
    {
        "id": "standard",
        "name": "Standard Bar",
        "weight": "4 oz",
        "price": 8.99,
        "regular_price": 12.00
    }
],
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
    "price": 8.99,
    "regular_price": 12.00,
    "sizes": [
    {
        "id": "mini",
        "name": "Mini Bar",
        "weight": "2 oz",
        "price": 5.99
    },
    {
        "id": "standard",
        "name": "Standard Bar",
        "weight": "4 oz",
        "price": 8.99,
        "regular_price": 12.00
    }
],
    "image": "products_clean/06-charcoal-cleanse.png",
},
{
    "id": 7,
    "name": "Almond Deluxe",
    "slug": "almond-deluxe",
    "short": {
        "en": "A nourishing handcrafted soap with almond goodness.",
        "es": "Un jabón artesanal nutritivo con la bondad de la almendra."
    },
    "price": 8.99,
    "regular_price": 12.00,
    "sizes": [
    {
            "id": "mini",
            "name": "Mini Bar",
            "weight": "2 oz",
            "price": 5.99
    },
    {
            "id": "standard",
            "name": "Standard Bar",
            "weight": "4 oz",
            "price": 8.99,
            "regular_price": 12.00
    }
],
    "image": "products_clean/07-almond-deluxe.png",
},
{
    "id": 8,
    "name": "Orange Sunrise",
    "slug": "orange-sunrise",
    "short": {
        "en": "A bright handcrafted soap inspired by fresh orange.",
        "es": "Un jabón artesanal vibrante inspirado en la naranja fresca."
    },
    "price": 8.99,
    "regular_price": 12.00,
    "sizes": [
    {
            "id": "mini",
            "name": "Mini Bar",
            "weight": "2 oz",
            "price": 5.99
    },
    {
            "id": "standard",
            "name": "Standard Bar",
            "weight": "4 oz",
            "price": 8.99,
            "regular_price": 12.00
    }
    ],
    "image": "products_clean/08-orange-sunrise.png",
},
]
@app.route("/admin/reports")
@login_required
def admin_reports():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Total Orders
    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]

    # Total Sales
    cur.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM orders
        WHERE status NOT IN ('Cancelled', 'Pending Payment')
    """)
    total_sales = cur.fetchone()[0]

    # Total Customers
    cur.execute("""
        SELECT COUNT(DISTINCT LOWER(email))
        FROM orders
        WHERE email IS NOT NULL
          AND TRIM(email) != ''
    """)
    total_customers = cur.fetchone()[0]

    # Total Products
    cur.execute("SELECT COUNT(*) FROM products")
    total_products = cur.fetchone()[0]

    # Order Status Counts
    cur.execute("""
        SELECT status, COUNT(*) AS count
        FROM orders
        GROUP BY status
    """)
    status_rows = cur.fetchall()

    order_status_counts = {
        "Pending Payment": 0,
        "Paid": 0,
        "Preparing": 0,
        "Packed": 0,
        "Shipped": 0,
        "Delivered": 0,
        "Cancelled": 0
    }

    for row in status_rows:
        order_status_counts[row["status"]] = row["count"]

    conn.close()

    return render_template(
        "admin_reports.html",
        total_orders=total_orders,
        total_sales=total_sales,
        total_customers=total_customers,
        total_products=total_products,
        order_status_counts=order_status_counts
    )
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
    
    gallery_directory = (
        Path("static/images/gallery")
        / product["slug"]
    )

    gallery_images = []

    if gallery_directory.is_dir():
        allowed_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
    }

    gallery_images = sorted(
        [
            file.name
            for file in gallery_directory.iterdir()
            if file.is_file()
            and file.suffix.lower() in allowed_extensions
        ]
    )
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
"almond-deluxe": {
    "en": {
        "ingredients": [
            {
                "icon": "🌰",
                "name": "Almond Oil",
                "description": "Helps nourish the skin and leaves it feeling soft, smooth, and conditioned."
            },
            {
                "icon": "💧",
                "name": "Vegetable Glycerin",
                "description": "Helps attract and retain moisture so the skin feels hydrated and comfortable."
            },
            {
                "icon": "💛",
                "name": "Vitamin E",
                "description": "Provides antioxidant care while helping nourish and condition the skin."
            }
        ],
        "benefits": [
            "Helps maintain skin moisture",
            "Leaves skin feeling soft and smooth",
            "Gentle cleansing without a dry, tight feeling",
            "Helps comfort dry or delicate-feeling skin",
            "Nourishing care for everyday use"
        ],
        "perfect_for": [
            "Dry Skin",
            "Sensitive-Feeling Skin",
            "Daily Use",
            "Face & Body"
        ]
    },

    "es": {
        "ingredients": [
            {
                "icon": "🌰",
                "name": "Aceite de Almendras",
                "description": "Ayuda a nutrir la piel y la deja con una sensación suave, tersa y acondicionada."
            },
            {
                "icon": "💧",
                "name": "Glicerina Vegetal",
                "description": "Ayuda a atraer y conservar la humedad para mantener la piel hidratada y confortable."
            },
            {
                "icon": "💛",
                "name": "Vitamina E",
                "description": "Brinda cuidado antioxidante mientras ayuda a nutrir y acondicionar la piel."
            }
        ],
        "benefits": [
            "Ayuda a mantener la hidratación natural de la piel",
            "Deja la piel suave y tersa",
            "Limpia suavemente sin dejar sensación de resequedad o tirantez",
            "Ayuda a reconfortar la piel seca o delicada",
            "Cuidado nutritivo para el uso diario"
        ],
        "perfect_for": [
            "Piel Seca",
            "Piel Delicada",
            "Uso Diario",
            "Rostro y Cuerpo"
        ]
    }
},
"orange-sunrise": {
    "en": {
        "ingredients": [
            {
                "icon": "🍊",
                "name": "Orange Essential Oil / Extract",
                "description": "Adds a fresh citrus character and helps leave the skin feeling clean and refreshed."
            },
            {
                "icon": "🍊",
                "name": "Orange Peel",
                "description": "Provides gentle exfoliation to help remove surface buildup and leave the skin feeling smoother."
            },
            {
                "icon": "💧",
                "name": "Vegetable Glycerin",
                "description": "Helps attract and retain moisture so the skin feels soft and comfortable after cleansing."
            },
            {
                "icon": "💛",
                "name": "Vitamin E",
                "description": "Provides nourishing antioxidant care and helps condition the skin."
            }
        ],
        "benefits": [
            "Refreshing citrus cleansing",
            "Gentle exfoliation",
            "Helps smooth rough-feeling skin",
            "Leaves skin feeling soft and refreshed",
            "Nourishing care for everyday cleansing"
        ],
        "perfect_for": [
            "Normal Skin",
            "Dull-Looking Skin",
            "Daily Use",
            "Face & Body"
        ]
    },

    "es": {
        "ingredients": [
            {
                "icon": "🍊",
                "name": "Aceite Esencial / Extracto de Naranja",
                "description": "Aporta un fresco toque cítrico y ayuda a dejar la piel con una sensación limpia y refrescada."
            },
            {
                "icon": "🍊",
                "name": "Cáscara de Naranja",
                "description": "Proporciona una exfoliación suave que ayuda a eliminar residuos superficiales y deja la piel más tersa."
            },
            {
                "icon": "💧",
                "name": "Glicerina Vegetal",
                "description": "Ayuda a atraer y conservar la humedad para que la piel se sienta suave y confortable después de la limpieza."
            },
            {
                "icon": "💛",
                "name": "Vitamina E",
                "description": "Brinda cuidado antioxidante nutritivo y ayuda a acondicionar la piel."
            }
        ],
        "benefits": [
            "Limpieza cítrica refrescante",
            "Exfoliación suave",
            "Ayuda a suavizar la piel áspera",
            "Deja la piel suave y fresca",
            "Cuidado nutritivo para la limpieza diaria"
        ],
        "perfect_for": [
            "Piel Normal",
            "Piel de Apariencia Opaca",
            "Uso Diario",
            "Rostro y Cuerpo"
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
        gallery_images=gallery_images,
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

def get_product_and_size(cart_key):
    if "::" in cart_key:
        slug, size_id = cart_key.split("::", 1)
    else:
        slug = cart_key
        size_id = "standard"

    product = next(
        (item for item in products if item["slug"] == slug),
        None
    )

    if not product:
        return None, None

    selected_size = next(
        (
            size
            for size in product.get("sizes", [])
            if size["id"] == size_id
        ),
        None
    )

    if not selected_size:
        selected_size = next(
            (
                size
                for size in product.get("sizes", [])
                if size["id"] == "standard"
            ),
            None
        )

    return product, selected_size
@app.route("/add-to-cart/<slug>", methods=["GET", "POST"])
def add_to_cart(slug):
    product = next(
        (item for item in products if item["slug"] == slug),
        None
    )

    if not product:
        abort(404)

    size_id = request.form.get("size", "standard")

    selected_size = next(
        (
            size
            for size in product.get("sizes", [])
            if size["id"] == size_id
        ),
        None
    )

    if not selected_size:
        size_id = "standard"

    cart_key = f"{slug}::{size_id}"
    cart = session.get("cart", {})

    cart[cart_key] = cart.get(cart_key, 0) + 1

    session["cart"] = cart
    session.modified = True

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

    for cart_key, quantity in cart.items():
        product, selected_size = get_product_and_size(cart_key)

        if product and selected_size:
            unit_price = selected_size["price"]
            item_subtotal = unit_price * quantity
            total += item_subtotal

            cart_items.append({
                "cart_key": cart_key,
                "product": product,
                "size": selected_size,
                "unit_price": unit_price,
                "quantity": quantity,
                "subtotal": item_subtotal
            })

    cart_slugs = {
        cart_key.split("::", 1)[0]
        for cart_key in cart.keys()
    }

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
@app.route("/update-cart/<path:cart_key>", methods=["POST"])
def update_cart(cart_key):
    cart = session.get("cart", {})

    if cart_key not in cart:
        return redirect(url_for("cart"))

    action = request.form.get("action")

    if action == "increase":
        cart[cart_key] += 1

    elif action == "decrease":
        cart[cart_key] -= 1

        if cart[cart_key] <= 0:
            cart.pop(cart_key)

    session["cart"] = cart
    session.modified = True

    return redirect(url_for("cart"))
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", {})

    if not cart:
        return redirect(url_for("cart"))

    cart_items = []

    subtotal = 0
    shipping_amount = 0
    tax_amount = 0
    total = 0

    # Build the cart using product and selected size information.
    for cart_key, quantity in cart.items():
        product, selected_size = get_product_and_size(cart_key)

        if not product or not selected_size:
            continue

        unit_price = selected_size["price"]
        item_subtotal = unit_price * quantity
        subtotal += item_subtotal

        cart_items.append({
            "cart_key": cart_key,
            "product": product,
            "size": selected_size,
            "unit_price": unit_price,
            "quantity": quantity,
            "subtotal": item_subtotal
        })

    # Calculate shipping after all products have been added
    shipping_amount = 0 if subtotal >= 60 else 5.99
    tax_amount = 0
    total = subtotal + shipping_amount + tax_amount
    # Prevent checkout when no valid cart items were found.
    if not cart_items:
        session.pop("cart", None)
        flash(
            "Your cart could not be processed. Please add the products again.",
            "error"
        )
        return redirect(url_for("cart"))

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

        try:
            cursor.execute("SELECT COUNT(*) FROM orders")
            order_count = cursor.fetchone()[0] + 1
            order_number = f"PET-{100000 + order_count}"

            cursor.execute("""
                INSERT INTO orders (
                    order_number,
                    first_name,
                    last_name,
                    email,
                    phone,
                    address,
                    city,
                    state,
                    zip_code,
                    notes,
                    subtotal,
                    shipping_amount,  
                    tax_amount,
                    total,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                subtotal,
                shipping_amount,
                tax_amount,
                total,
                "Pending Payment"
            ))

            order_id = cursor.lastrowid

            for item in cart_items:
                product_name = (
                    item["product"].get("name_en")
                    or item["product"].get("name")
                    or item["product"]["slug"]
                )

                size_id = item["size"]["id"]

                if size_id == "mini":
                    size_name = "Discovery Bar - 2 oz"
                else:
                    size_name = "Classic Bar - 4 oz"

                full_product_name = f"{product_name} - {size_name}"

                cursor.execute("""
                    INSERT INTO order_items (
                        order_id,
                        product_name,
                        product_slug,
                        size_code,
                        size_name,
                        quantity,
                        price,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_id,
                    full_product_name,
                    item["product"]["slug"],
                    size_id,
                    size_name,
                    item["quantity"],
                    item["unit_price"],
                    item["subtotal"]
                ))

            conn.commit()
        except Exception as error:
             conn.rollback()

             import traceback
             traceback.print_exc()

             return f"""
             <h2>Checkout Error</h2>
             <pre>{error}</pre>
             """, 500

        finally:
            conn.close()

        session["customer"] = customer
        session["order_number"] = order_number
        session["order_id"] = order_id

        return redirect(url_for("payment"))

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        subtotal=subtotal,
        shipping_amount=shipping_amount,
        tax_amount=tax_amount,
        total=total
    )
@app.route("/payment")
def payment():
    customer = session.get("customer")
    order_number = session.get("order_number")
    cart = session.get("cart", {})

    if not customer or not order_number or not cart:
        return redirect(url_for("checkout"))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT subtotal, shipping_amount, tax_amount, total
        FROM orders
        WHERE order_number = ?
    """, (order_number,))

    order = cursor.fetchone()
    conn.close()

    if not order:
        flash("Order information could not be found.", "error")
        return redirect(url_for("checkout"))

    return render_template(
        "payment.html",
        customer=customer,
        order_number=order_number,
        subtotal=order["subtotal"],
        shipping_amount=order["shipping_amount"],
        tax_amount=order["tax_amount"],
        total=order["total"]
    )
@app.route("/remove-from-cart/<path:cart_key>")
def remove_from_cart(cart_key):
    cart = session.get("cart", {})

    if cart_key in cart:
        del cart[cart_key]

    session["cart"] = cart
    session.modified = True

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
@app.route("/admin/packing-slips")
@login_required
def admin_packing_slips():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            order_number,
            first_name,
            last_name,
            total,
            status,
            created_at
        FROM orders
        ORDER BY created_at DESC, id DESC
    """)

    orders = cursor.fetchall()
    conn.close()

    return render_template(
        "admin_packing_slips.html",
        orders=orders
    )
@app.route("/admin/packing-slips/<int:order_id>")
@login_required
def admin_packing_slip(order_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM orders
        WHERE id = ?
    """, (order_id,))

    order = cursor.fetchone()

    if order is None:
        conn.close()
        abort(404)

    cursor.execute("""
        SELECT *
        FROM order_items
        WHERE order_id = ?
        ORDER BY id ASC
    """, (order_id,))

    items = cursor.fetchall()
    conn.close()

    return render_template(
        "admin_packing_slip.html",
        order=order,
        items=items
    )

@app.route("/admin")
@login_required
def admin_dashboard():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Total Orders
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    # Pending Orders
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE status IN ('Pending Payment', 'Paid', 'Preparing', 'Packed')
        """
    )
    pending_orders = cursor.fetchone()[0]

    # Total Products
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]

    # Low Stock Products
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM products
        WHERE stock <= 2
          AND active = 1
        """
    )
    low_stock_products = cursor.fetchone()[0]

    # Total Customers
    cursor.execute(
        """
        SELECT COUNT(DISTINCT email)
        FROM orders
        """
    )
    total_customers = cursor.fetchone()[0]

    # Total Revenue
    cursor.execute(
        """
        SELECT IFNULL(SUM(total), 0)
        FROM orders
        WHERE status NOT IN ('Cancelled', 'Pending Payment')
        """
    )
    total_revenue = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_orders=total_orders,
        pending_orders=pending_orders,
        total_customers=total_customers,
        total_products=total_products,
        low_stock_products=low_stock_products,
        total_revenue=total_revenue,
    )

@app.route("/admin/customers")
@login_required
def admin_customers():
    return render_template("admin_customers.html")


@app.route("/admin/suppliers")
@login_required
def admin_suppliers():
    return render_template("admin_suppliers.html")


@app.route("/admin/reviews")
@login_required
def admin_reviews():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            product_slug,
            customer_name,
            rating,
            review_text,
            approved,
            created_at
        FROM reviews
        ORDER BY
            approved ASC,
            created_at DESC
        """
    )
    reviews = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM reviews WHERE approved = 0"
    )
    pending_reviews = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM reviews WHERE approved = 1"
    )
    approved_reviews = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COALESCE(AVG(rating), 0)
        FROM reviews
        WHERE approved = 1
        """
    )
    average_rating = round(cursor.fetchone()[0], 1)

    conn.close()

    return render_template(
        "admin_reviews.html",
        reviews=reviews,
        total_reviews=total_reviews,
        pending_reviews=pending_reviews,
        approved_reviews=approved_reviews,
        average_rating=average_rating
    )


@app.route("/admin/reviews/<int:review_id>/approve", methods=["POST"])
@login_required
def admin_approve_review(review_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE reviews
        SET approved = 1
        WHERE id = ?
        """,
        (review_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_reviews"))


@app.route("/admin/reviews/<int:review_id>/hide", methods=["POST"])
@login_required
def admin_hide_review(review_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE reviews
        SET approved = 0
        WHERE id = ?
        """,
        (review_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_reviews"))


@app.route("/admin/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
def admin_delete_review(review_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM reviews
        WHERE id = ?
        """,
        (review_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_reviews"))


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
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart"))

    line_items = []
    subtotal = 0

    for cart_key, quantity in cart.items():
        product, selected_size = get_product_and_size(cart_key)

        if not product or not selected_size:
            continue

        product_name = (
            product.get("name_en")
            or product.get("name")
            or product.get("slug")
            or "Petty's Care Product"
        )

        if selected_size["id"] == "mini":
            size_name = "Discovery Bar - 2 oz"
        else:
            size_name = "Classic Bar - 4 oz"
        subtotal += float(selected_size["price"]) * int(quantity)   
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"{product_name} - {size_name}",
                },
                "unit_amount": int(
                    round(float(selected_size["price"]) * 100)
                ),
            },
            "quantity": int(quantity),
    })
    if subtotal < 60:
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "Shipping"
                },
                "unit_amount": 599,
          },
          "quantity": 1,
       }) 
    if not line_items:
        flash(
            "Your cart could not be processed. Please add the products again.",
            "error"
        )
        return redirect(url_for("cart"))

    domain = os.getenv("DOMAIN", "http://127.0.0.1:5000").rstrip("/")

    print("=== ENTERING STRIPE CHECKOUT ===")
    print("Cart:", cart)
    print("Line items:", line_items)
    print("Stripe key loaded:", bool(stripe.api_key))
    print("Domain:", domain)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=domain + "/payment-success",
            cancel_url=domain + "/cart",
        )

    except Exception as error:
        print("STRIPE ERROR:", repr(error))
        flash(
            "Stripe could not start the payment. Please try again.",
            "error"
        )
        return redirect(url_for("payment"))

    return redirect(checkout_session.url, code=303)
def deduct_inventory(order_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                product_slug,
                size_code,
                quantity
            FROM order_items
            WHERE order_id = ?
        """, (order_id,))

        order_items = cursor.fetchall()

        for product_slug, size_code, quantity in order_items:
            cursor.execute("""
                SELECT id
                FROM products
                WHERE slug = ?
            """, (product_slug,))

            product = cursor.fetchone()

            if not product:
                print(
                    f"Inventory deduction skipped: "
                    f"product not found for slug {product_slug}"
                )
                continue

            product_id = product[0]

            cursor.execute("""
                UPDATE product_sizes
                SET stock = CASE
                    WHEN stock >= ? THEN stock - ?
                    ELSE 0
                END
                WHERE product_id = ?
                  AND size_code = ?
            """, (
                quantity,
                quantity,
                product_id,
                size_code
            ))

            if cursor.rowcount == 0:
                print(
                    f"Inventory deduction skipped: "
                    f"size {size_code} not found for {product_slug}"
                )

        conn.commit()

    except sqlite3.Error as error:
        conn.rollback()
        print(f"Inventory deduction error: {error}")

    finally:
        conn.close()
@app.route("/payment-success")
def payment_success():
    order_id = session.get("order_id")
    order_number = session.get("order_number")

    if order_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status
            FROM orders
            WHERE id = ?
        """, (order_id,))

        order = cursor.fetchone()

        if order and order[0] != "Paid":
            cursor.execute("""
                UPDATE orders
                SET status = ?
                WHERE id = ?
            """, ("Paid", order_id))

            conn.commit()
            conn.close()

            deduct_inventory(order_id)
            send_order_confirmation_email(order_id)

        else:
            conn.close()
            print(
                f"Order {order_id} is already paid. "
                "Inventory deduction skipped."
            )

    session.pop("cart", None)

    return render_template(
        "payment_success.html",
        order_number=order_number
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


# =========================================================
# OUTPUT FILES
# =========================================================

FRONT_OUTPUT = "generated_pdfs/pettys_business_cards_front.pdf"
BACK_OUTPUT = "generated_pdfs/pettys_business_cards_back.pdf"
QR_FILE = "generated_pdfs/pettys_qr.png"


# =========================================================
# ASSETS
# =========================================================

LOGO_FILE = "static/images/branding/official_logo1.png"

BACK_BACKGROUND_FILE = (
    "static/print/business_cards/back_card_only_v1.png"
)

WEBSITE_URL = "https://pettyscare.com"


# =========================================================
# AVERY 5877 LAYOUT
# =========================================================

PAGE_WIDTH, PAGE_HEIGHT = letter

CARD_WIDTH = 3.5 * inch
CARD_HEIGHT = 2 * inch

COLUMNS = 2
ROWS = 5

LEFT_MARGIN = 0.75 * inch
TOP_MARGIN = 0.5 * inch

HORIZONTAL_GAP = 0
VERTICAL_GAP = 0


# =========================================================
# BRAND COLORS
# =========================================================

CREAM = colors.HexColor("#F1DFCF")
QR_CREAM = colors.HexColor("#F4EBDD")
OLIVE = colors.HexColor("#556B2F")
GOLD = colors.HexColor("#B78B43")
BROWN = colors.HexColor("#3B2A1E")


def require_file(file_path: str) -> Path:
    """Confirm that a required image file exists."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Required file was not found: {file_path}"
        )

    return path


def card_position(row: int, column: int) -> tuple[float, float]:
    """Calculate one card's position on the Avery 5877 sheet."""

    x = LEFT_MARGIN + column * (
        CARD_WIDTH + HORIZONTAL_GAP
    )

    y = (
        PAGE_HEIGHT
        - TOP_MARGIN
        - CARD_HEIGHT
        - row * (CARD_HEIGHT + VERTICAL_GAP)
    )

    return x, y


# =========================================================
# REAL QR CODE
# =========================================================

def create_qr_code() -> None:
    """Create a real QR code that opens pettyscare.com."""

    Path("generated_pdfs").mkdir(
        parents=True,
        exist_ok=True,
    )

    qr = qrcode.QRCode(
        version=4,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )

    qr.add_data(WEBSITE_URL)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    image.save(QR_FILE)


# =========================================================
# FRONT OF BUSINESS CARD
# =========================================================

def draw_card_front(
    pdf: canvas.Canvas,
    x: float,
    y: float,
) -> None:

    # Warm cream background
    pdf.setFillColor(CREAM)
    pdf.rect(
        x,
        y,
        CARD_WIDTH,
        CARD_HEIGHT,
        fill=1,
        stroke=0,
    )

    # Gold border
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(0.8)

    pdf.rect(
        x + 0.08 * inch,
        y + 0.08 * inch,
        CARD_WIDTH - 0.16 * inch,
        CARD_HEIGHT - 0.16 * inch,
        fill=0,
        stroke=1,
    )

    # Official logo
    logo_path = require_file(LOGO_FILE)
    logo = ImageReader(str(logo_path))

    logo_width = 1.05 * inch
    logo_height = 0.72 * inch

    logo_x = x + (CARD_WIDTH - logo_width) / 2
    logo_y = y + 1.05 * inch

    pdf.drawImage(
        logo,
        logo_x,
        logo_y,
        width=logo_width,
        height=logo_height,
        preserveAspectRatio=True,
        mask="auto",
    )

    # Tagline
    pdf.setFillColor(BROWN)
    pdf.setFont("Times-Italic", 9.5)

    pdf.drawCentredString(
        x + CARD_WIDTH / 2,
        y + 0.92 * inch,
        "From Our Hands to Your Home",
    )

    # Divider
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(0.6)

    pdf.line(
        x + 0.55 * inch,
        y + 0.82 * inch,
        x + CARD_WIDTH - 0.55 * inch,
        y + 0.82 * inch,
    )

    # Contact information
    pdf.setFillColor(OLIVE)
    pdf.setFont("Helvetica-Bold", 7.8)

    contact_lines = [
        "pettyscare.com",
        "orders@pettyscare.com",
        "(929) 401-1294",
        "Jamaica, New York",
    ]

    start_y = y + 0.64 * inch
    line_spacing = 0.15 * inch

    for index, line in enumerate(contact_lines):
        pdf.drawCentredString(
            x + CARD_WIDTH / 2,
            start_y - index * line_spacing,
            line,
        )


def create_front_sheet() -> None:
    """Create ten identical fronts on Avery 5877."""

    pdf = canvas.Canvas(
        FRONT_OUTPUT,
        pagesize=letter,
    )

    for row in range(ROWS):
        for column in range(COLUMNS):
            x, y = card_position(row, column)
            draw_card_front(pdf, x, y)

    pdf.save()

    print(f"Created front: {FRONT_OUTPUT}")


# =========================================================
# BACK OF BUSINESS CARD
# =========================================================

def draw_card_back(
    pdf: canvas.Canvas,
    x: float,
    y: float,
) -> None:

    background_path = require_file(
        BACK_BACKGROUND_FILE
    )

    background = ImageReader(
        str(background_path)
    )

    # Product-showcase background
    pdf.drawImage(
        background,
        x,
        y,
        width=CARD_WIDTH,
        height=CARD_HEIGHT,
        preserveAspectRatio=False,
        mask="auto",
    )

    # Cover the old decorative QR and website button
    cover_width = 1.28 * inch
    cover_height = 1.10 * inch

    cover_x = x + (
        CARD_WIDTH - cover_width
    ) / 2

    cover_y = y + 0.10 * inch

    pdf.setFillColor(QR_CREAM)

    pdf.roundRect(
        cover_x,
        cover_y,
        cover_width,
        cover_height,
        0.06 * inch,
        fill=1,
        stroke=0,
    )

    # Subtle gold border around the clean QR area
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(0.6)

    pdf.roundRect(
        cover_x,
        cover_y,
        cover_width,
        cover_height,
        0.06 * inch,
        fill=0,
        stroke=1,
    )

    # Real, working QR code
    qr_path = require_file(QR_FILE)
    qr = ImageReader(str(qr_path))

    qr_size = 0.92 * inch

    qr_x = x + (
        CARD_WIDTH - qr_size
    ) / 2

    qr_y = y + 0.24 * inch

    pdf.drawImage(
        qr,
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )


def create_back_sheet() -> None:
    """Create ten identical backs on Avery 5877."""

    pdf = canvas.Canvas(
        BACK_OUTPUT,
        pagesize=letter,
    )

    for row in range(ROWS):
        for column in range(COLUMNS):
            x, y = card_position(row, column)
            draw_card_back(pdf, x, y)

    pdf.save()

    print(f"Created back : {BACK_OUTPUT}")


# =========================================================
# GENERATE BOTH SIDES
# =========================================================

def create_business_cards() -> None:
    Path("generated_pdfs").mkdir(
        parents=True,
        exist_ok=True,
    )

    create_qr_code()
    create_front_sheet()
    create_back_sheet()

    print()
    print("Business card files are ready.")
    print(f"Front: {FRONT_OUTPUT}")
    print(f"Back : {BACK_OUTPUT}")
    print(f"QR   : {QR_FILE}")


if __name__ == "__main__":
    create_business_cards()

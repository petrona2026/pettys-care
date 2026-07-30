from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
CREAM = colors.HexColor("#F4EBDD")

OUTPUT_FILE = "generated_pdfs/pettys_business_cards_back.pdf"
QR_FILE = "generated_pdfs/pettys_qr.png"

BACKGROUND_FILE = "static/print/business_cards/back_card_only_v1.png"
WEBSITE_URL = "https://pettyscare.com"

PAGE_WIDTH, PAGE_HEIGHT = letter

CARD_WIDTH = 3.5 * inch
CARD_HEIGHT = 2 * inch

COLUMNS = 2
ROWS = 5

LEFT_MARGIN = 0.75 * inch
TOP_MARGIN = 0.5 * inch

HORIZONTAL_GAP = 0
VERTICAL_GAP = 0

OLIVE = colors.HexColor("#556B2F")
GOLD = colors.HexColor("#B78B43")
BROWN = colors.HexColor("#3B2A1E")


def create_qr_code() -> None:
    Path("generated_pdfs").mkdir(exist_ok=True)

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


def draw_card_back(pdf: canvas.Canvas, x: float, y: float) -> None:

    # Draw the background artwork
    background = ImageReader(BACKGROUND_FILE)

    pdf.drawImage(
        background,
        x,
        y,
        width=CARD_WIDTH,
        height=CARD_HEIGHT,
        preserveAspectRatio=False,
        mask="auto",
    )
        # Cover the old QR code and old website button
    pdf.setFillColor(CREAM)

    cover_width = 1.28 * inch
    cover_height = 1.10 * inch

    cover_x = x + (CARD_WIDTH - cover_width) / 2
    cover_y = y + 0.10 * inch

    pdf.roundRect(
        cover_x,
        cover_y,
        cover_width,
        cover_height,
        0.06 * inch,
        fill=1,
        stroke=0,
    )
    # Optional decorative border
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

    # Real QR Code
        # Add the real working QR code
    qr = ImageReader(QR_FILE)

    qr_size = 0.92 * inch
    qr_x = x + (CARD_WIDTH - qr_size) / 2
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
    # Website under QR
    pdf.setFillColor(BROWN)
    pdf.setFont("Helvetica-Bold", 8)

    pdf.drawCentredString(
        x + CARD_WIDTH / 2,
        y + 0.16 * inch,
        "pettyscare.com",
    )


def create_back_sheet() -> None:

    create_qr_code()

    pdf = canvas.Canvas(
        OUTPUT_FILE,
        pagesize=letter,
    )

    for row in range(ROWS):
        for column in range(COLUMNS):

            x = (
                LEFT_MARGIN
                + column * (CARD_WIDTH + HORIZONTAL_GAP)
            )

            y = (
                PAGE_HEIGHT
                - TOP_MARGIN
                - CARD_HEIGHT
                - row * (CARD_HEIGHT + VERTICAL_GAP)
            )

            draw_card_back(pdf, x, y)

    pdf.save()

    print(f"Created: {OUTPUT_FILE}")
    print(f"Created: {QR_FILE}")


if __name__ == "__main__":
    create_back_sheet()

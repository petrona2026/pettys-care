from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


OUTPUT_FILE = "generated_pdfs/thank_you_cards/pettys_thank_you_cards.pdf"
LOGO_FILE = "static/images/branding/official_logo1.png"

PAGE_WIDTH, PAGE_HEIGHT = letter

CARD_WIDTH = 4.25 * inch
CARD_HEIGHT = 5.5 * inch

COLUMNS = 2
ROWS = 2

CREAM = colors.HexColor("#F1DFCF")
OLIVE = colors.HexColor("#556B2F")
GOLD = colors.HexColor("#B78B43")
BROWN = colors.HexColor("#3B2A1E")


def draw_thank_you_card(
    pdf: canvas.Canvas,
    x: float,
    y: float,
) -> None:
    pdf.setFillColor(CREAM)
    pdf.rect(
        x,
        y,
        CARD_WIDTH,
        CARD_HEIGHT,
        fill=1,
        stroke=0,
    )

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)

    pdf.rect(
        x + 0.12 * inch,
        y + 0.12 * inch,
        CARD_WIDTH - 0.24 * inch,
        CARD_HEIGHT - 0.24 * inch,
        fill=0,
        stroke=1,
    )

    logo_path = Path(LOGO_FILE)

    if logo_path.exists():
        logo = ImageReader(str(logo_path))

        logo_size = 1.25 * inch

        pdf.drawImage(
            logo,
            x + (CARD_WIDTH - logo_size) / 2,
            y + CARD_HEIGHT - 1.70 * inch,
            width=logo_size,
            height=logo_size,
            preserveAspectRatio=True,
            mask="auto",
        )

    pdf.setFillColor(OLIVE)
    pdf.setFont("Times-Bold", 18)

    pdf.drawCentredString(
        x + CARD_WIDTH / 2,
        y + 3.45 * inch,
        "Thank You for Your Order",
    )

    pdf.setFillColor(BROWN)
    pdf.setFont("Times-Roman", 11)

    message_lines = [
        "Your support means so much to us.",
        "We hope you enjoy your handcrafted products.",
    ]

    message_y = y + 2.85 * inch

    for index, line in enumerate(message_lines):
        pdf.drawCentredString(
            x + CARD_WIDTH / 2,
            message_y - index * 0.22 * inch,
            line,
        )

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(0.7)

    pdf.line(
        x + 0.75 * inch,
        y + 2.15 * inch,
        x + CARD_WIDTH - 0.75 * inch,
        y + 2.15 * inch,
    )

    pdf.setFillColor(GOLD)
    pdf.setFont("Times-Italic", 12)

    pdf.drawCentredString(
        x + CARD_WIDTH / 2,
        y + 1.75 * inch,
        "From Our Hands to Your Home",
    )

    pdf.setFillColor(OLIVE)
    pdf.setFont("Helvetica-Bold", 10)

    pdf.drawCentredString(
        x + CARD_WIDTH / 2,
        y + 1.20 * inch,
        "pettyscare.com",
    )

    pdf.setFillColor(BROWN)
    pdf.setFont("Helvetica", 8.5)

    pdf.drawCentredString(
        x + CARD_WIDTH / 2,
        y + 0.85 * inch,
        "Handcrafted with care in Jamaica, New York",
    )


def create_sheet() -> None:
    output_path = Path(OUTPUT_FILE)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf = canvas.Canvas(
        str(output_path),
        pagesize=letter,
    )

    for row in range(ROWS):
        for column in range(COLUMNS):
            x = column * CARD_WIDTH
            y = (
                PAGE_HEIGHT
                - CARD_HEIGHT
                - row * CARD_HEIGHT
            )

            draw_thank_you_card(
                pdf,
                x,
                y,
            )

    pdf.save()

    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_sheet()

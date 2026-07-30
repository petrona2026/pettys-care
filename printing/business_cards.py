from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


OUTPUT_FILE = "generated_pdfs/pettys_business_cards_front.pdf"
LOGO_FILE = "static/images/branding/official_logo1.png"

PAGE_WIDTH, PAGE_HEIGHT = letter

CARD_WIDTH = 3.5 * inch
CARD_HEIGHT = 2 * inch

COLUMNS = 2
ROWS = 5

LEFT_MARGIN = 0.75 * inch
TOP_MARGIN = 0.5 * inch

HORIZONTAL_GAP = 0
VERTICAL_GAP = 0

CREAM = colors.HexColor("#F1DFCF")
OLIVE = colors.HexColor("#556B2F")
GOLD = colors.HexColor("#B78B43")
BROWN = colors.HexColor("#3B2A1E")


def draw_card_front(pdf: canvas.Canvas, x: float, y: float) -> None:
    # Background
    pdf.setFillColor(CREAM)
    pdf.rect(x, y, CARD_WIDTH, CARD_HEIGHT, fill=1, stroke=0)

    # Thin border
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

    # Logo
    logo_path = Path(LOGO_FILE)

    if logo_path.exists():
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

    lines = [
        "pettyscare.com",
        "orders@pettyscare.com",
        "(929) 401-1294",
        "Jamaica, New York",
    ]

    start_y = y + 0.64 * inch
    line_spacing = 0.15 * inch

    for index, line in enumerate(lines):
        pdf.drawCentredString(
            x + CARD_WIDTH / 2,
            start_y - index * line_spacing,
            line,
        )


def create_front_sheet() -> None:
    Path("generated_pdfs").mkdir(exist_ok=True)

    pdf = canvas.Canvas(OUTPUT_FILE, pagesize=letter)

    for row in range(ROWS):
        for column in range(COLUMNS):
            x = LEFT_MARGIN + column * (CARD_WIDTH + HORIZONTAL_GAP)

            y = (
                PAGE_HEIGHT
                - TOP_MARGIN
                - CARD_HEIGHT
                - row * (CARD_HEIGHT + VERTICAL_GAP)
            )

            draw_card_front(pdf, x, y)

    pdf.save()
    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_front_sheet()

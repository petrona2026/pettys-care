from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


OUTPUT_FILE = Path(
    "generated_pdfs/thank_you_cards/"
    "pettys_thank_you_cards.pdf"
)

BACKGROUND_FILE = Path(
    "static/print/thank_you_cards/"
    "thank_you_card_full_background.png"
)

PAGE_WIDTH, PAGE_HEIGHT = landscape(letter)

# Landscape thank-you card with a 3:2 ratio.
CARD_WIDTH = 5.25 * inch
CARD_HEIGHT = 3.50 * inch

COLUMNS = 2
ROWS = 2

LEFT_MARGIN = 0.25 * inch
TOP_MARGIN = 0.75 * inch


def draw_card(
    pdf: canvas.Canvas,
    background: ImageReader,
    x: float,
    y: float,
) -> None:
    # The card artwork already contains the message,
    # branding, border, and product photograph.
    pdf.drawImage(
        background,
        x,
        y,
        width=CARD_WIDTH,
        height=CARD_HEIGHT,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )

    # Very light cutting guide.
    pdf.setStrokeColor(colors.HexColor("#D8D0C4"))
    pdf.setLineWidth(0.35)

    pdf.rect(
        x,
        y,
        CARD_WIDTH,
        CARD_HEIGHT,
        fill=0,
        stroke=1,
    )


def create_sheet() -> None:
    if not BACKGROUND_FILE.is_file():
        raise FileNotFoundError(
            f"Thank-you card image not found: "
            f"{BACKGROUND_FILE}"
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    background = ImageReader(
        str(BACKGROUND_FILE)
    )

    pdf = canvas.Canvas(
        str(OUTPUT_FILE),
        pagesize=landscape(letter),
    )

    for row in range(ROWS):
        for column in range(COLUMNS):
            x = (
                LEFT_MARGIN
                + column * CARD_WIDTH
            )

            y = (
                PAGE_HEIGHT
                - TOP_MARGIN
                - CARD_HEIGHT
                - row * CARD_HEIGHT
            )

            draw_card(
                pdf=pdf,
                background=background,
                x=x,
                y=y,
            )

    pdf.save()

    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_sheet()

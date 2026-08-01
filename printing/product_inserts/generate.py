import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from product_service import get_product_by_slug


OUTPUT_DIRECTORY = Path("generated_pdfs/product_inserts")
LOGO_FILE = Path("static/images/branding/official_logo1.png")

PAGE_WIDTH, PAGE_HEIGHT = letter

CARD_WIDTH = 4.25 * inch
CARD_HEIGHT = 5.5 * inch

COLUMNS = 2
ROWS = 2

CREAM = colors.HexColor("#F1DFCF")
OLIVE = colors.HexColor("#556B2F")
GOLD = colors.HexColor("#B78B43")
BROWN = colors.HexColor("#3B2A1E")


def draw_wrapped_lines(
    pdf: canvas.Canvas,
    lines: list[str],
    center_x: float,
    start_y: float,
    font_name: str,
    font_size: float,
    line_spacing: float,
    max_items: int,
) -> float:
    pdf.setFont(font_name, font_size)

    current_y = start_y

    for line in lines[:max_items]:
        pdf.drawCentredString(
            center_x,
            current_y,
            f"• {line}",
        )

        current_y -= line_spacing

    return current_y


def draw_product_insert(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    product: dict,
) -> None:
    center_x = x + CARD_WIDTH / 2

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

    if LOGO_FILE.exists():
        logo = ImageReader(str(LOGO_FILE))

        logo_size = 0.78 * inch

        pdf.drawImage(
            logo,
            center_x - logo_size / 2,
            y + CARD_HEIGHT - 1.05 * inch,
            width=logo_size,
            height=logo_size,
            preserveAspectRatio=True,
            mask="auto",
        )

    product_image_value = product.get("image", "").strip()

    if product_image_value:
        product_image_path = Path("static") / product_image_value

        if product_image_path.is_file():
            product_image = ImageReader(str(product_image_path))

            image_size = 1.10 * inch

            pdf.drawImage(
                product_image,
                center_x - image_size / 2,
                y + CARD_HEIGHT - 2.15 * inch,
                width=image_size,
                height=image_size,
                preserveAspectRatio=True,
                mask="auto",
           )

    pdf.setFillColor(OLIVE)
    pdf.setFont("Times-Bold", 16)

    pdf.drawCentredString(
        center_x,
        y + 3.05 * inch,
        product.get("name", "Petty's Care Product"),
    )

       
    short_description = (
        product.get("short", {}).get("en", "")
    )

    pdf.setFillColor(BROWN)
    pdf.setFont("Times-Roman", 8.8)

    description_lines = [
        line.strip()
        for line in short_description.splitlines()
        if line.strip()
    ]

    description_y = y + 2.82 * inch

    for index, line in enumerate(description_lines[:5]):
        pdf.drawCentredString(
        center_x,
        description_y - index * 0.16 * inch,
        line[:78],
    )
    content = product.get("content", {}).get("en", {})

    ingredients = content.get("ingredients", [])
    benefits = content.get("benefits", [])
    perfect_for = content.get("perfect_for", [])

    pdf.setFillColor(OLIVE)
    pdf.setFont("Helvetica-Bold", 9)

    pdf.drawCentredString(
        center_x,
        y + 1.92 * inch,
        "Ingredients",
    )

    pdf.setFillColor(BROWN)

    ingredients_y = draw_wrapped_lines(
        pdf=pdf,
        lines=ingredients,
        center_x=center_x,
        start_y=y + 1.72 * inch,
        font_name="Helvetica",
        font_size=7.5,
        line_spacing=0.14 * inch,
        max_items=5,
    )

    pdf.setFillColor(OLIVE)
    pdf.setFont("Helvetica-Bold", 9)

    pdf.drawCentredString(
        center_x,
        ingredients_y - 0.04 * inch,
        "Benefits",
    )

    pdf.setFillColor(BROWN)

    benefits_y = draw_wrapped_lines(
        pdf=pdf,
        lines=benefits,
        center_x=center_x,
        start_y=ingredients_y - 0.23 * inch,
        font_name="Helvetica",
        font_size=7.5,
        line_spacing=0.14 * inch,
        max_items=4,
    )

    if perfect_for:
        pdf.setFillColor(GOLD)
        pdf.setFont("Times-Italic", 8.5)

        perfect_for_text = ", ".join(perfect_for[:3])

        pdf.drawCentredString(
            center_x,
            benefits_y - 0.03 * inch,
            f"Perfect for: {perfect_for_text}",
        )

    pdf.setFillColor(OLIVE)
    pdf.setFont("Helvetica-Bold", 8)

    pdf.drawCentredString(
        center_x,
        y + 0.55 * inch,
        "pettyscare.com",
    )

    pdf.setFillColor(BROWN)
    pdf.setFont("Helvetica", 7)

    pdf.drawCentredString(
        center_x,
        y + 0.34 * inch,
        "Handcrafted in small batches",
    )


def create_product_insert_sheet(slug: str) -> Path:
    product = get_product_by_slug(slug)

    if product is None:
        raise ValueError(
            f"Product not found or inactive: {slug}"
        )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        OUTPUT_DIRECTORY
        / f"{slug}_product_inserts.pdf"
    )

    pdf = canvas.Canvas(
        str(output_file),
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

            draw_product_insert(
                pdf,
                x,
                y,
                product,
            )

    pdf.save()

    print(f"Created: {output_file}")

    return output_file


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python printing/product_inserts/generate.py <product-slug>"
        )

    create_product_insert_sheet(sys.argv[1])

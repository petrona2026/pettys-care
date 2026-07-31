import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


OUTPUT_FILE = "generated_pdfs/labels/logo_stickers.pdf"
LOGO_FILE = "static/images/branding/official_logo1.png"
CALIBRATION_FILE = Path("printing/calibration.json")

PAGE_WIDTH, PAGE_HEIGHT = letter

# Avery 22877
LABEL_DIAMETER = 2 * inch

COLUMNS = 3
ROWS = 4

LEFT_MARGIN = 0.85 * inch
TOP_MARGIN = 0.60 * inch

HORIZONTAL_GAP = 0.5 * inch
VERTICAL_GAP = 0.5 * inch


def load_calibration() -> tuple[float, float]:
    x_value = 0.0
    y_value = 0.0

    if CALIBRATION_FILE.exists():
        with CALIBRATION_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        settings = data.get("avery_22877", {})
        x_value = float(settings.get("x_offset", 0.0))
        y_value = float(settings.get("y_offset", 0.0))

    return x_value * inch, y_value * inch


def create_logo_sticker_sheet() -> None:
    Path("generated_pdfs/labels").mkdir(
        parents=True,
        exist_ok=True,
    )

    logo_path = Path(LOGO_FILE)

    if not logo_path.exists():
        raise FileNotFoundError(
            f"Logo not found: {LOGO_FILE}"
        )

    x_offset, y_offset = load_calibration()

    pdf = canvas.Canvas(
        OUTPUT_FILE,
        pagesize=letter,
    )

    logo = ImageReader(str(logo_path))

    # Keep a small safe margin inside the 2-inch circle.
    logo_size = 1.72 * inch

    for row in range(ROWS):
        for column in range(COLUMNS):
            x = (
                LEFT_MARGIN
                + x_offset
                + column * (
                    LABEL_DIAMETER + HORIZONTAL_GAP
                )
            )

            y = (
                PAGE_HEIGHT
                - TOP_MARGIN
                - y_offset
                - LABEL_DIAMETER
                - row * (
                    LABEL_DIAMETER + VERTICAL_GAP
                )
            )

            center_x = x + LABEL_DIAMETER / 2
            center_y = y + LABEL_DIAMETER / 2

            logo_x = center_x - logo_size / 2
            logo_y = center_y - logo_size / 2

            pdf.drawImage(
                logo,
                logo_x,
                logo_y,
                width=logo_size,
                height=logo_size,
                preserveAspectRatio=True,
                mask="auto",
            )

    pdf.save()
    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_logo_sticker_sheet()

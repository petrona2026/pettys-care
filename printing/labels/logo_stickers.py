import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


OUTPUT_FILE = "generated_pdfs/labels/logo_stickers_test.pdf"
LOGO_FILE = "static/images/branding/official_logo1.png"
CALIBRATION_FILE = Path("printing/calibration.json")

PAGE_WIDTH, PAGE_HEIGHT = letter

LABEL_DIAMETER = 2 * inch

COLUMNS = ["A", "B", "C"]
ROWS = [1, 2, 3, 4]

LEFT_MARGIN = 0.85 * inch
TOP_MARGIN = 0.60 * inch

HORIZONTAL_GAP = 0.50 * inch
VERTICAL_GAP = 0.50 * inch

LOGO_SIZE = 1.72 * inch


def default_positions() -> dict:
    positions = {}

    for row in ROWS:
        for column in COLUMNS:
            positions[f"{column}{row}"] = {
                "x": 0.0,
                "y": 0.0,
            }

    return positions


def load_calibration() -> tuple[float, float, dict]:
    global_x = 0.0
    global_y = 0.0
    positions = default_positions()

    if not CALIBRATION_FILE.exists():
        return global_x * inch, global_y * inch, positions

    try:
        with CALIBRATION_FILE.open("r", encoding="utf-8") as file:
            calibration_data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return global_x * inch, global_y * inch, positions

    settings = calibration_data.get("avery_22877", {})

    global_x = float(
        settings.get(
            "global_x",
            settings.get("x_offset", 0.0),
        )
    )

    global_y = float(
        settings.get(
            "global_y",
            settings.get("y_offset", 0.0),
        )
    )

    saved_positions = settings.get("positions", {})

    for position_name in positions:
        saved = saved_positions.get(position_name, {})

        positions[position_name]["x"] = float(
            saved.get("x", 0.0)
        )

        positions[position_name]["y"] = float(
            saved.get("y", 0.0)
        )

    return global_x * inch, global_y * inch, positions


def create_logo_sticker_sheet() -> None:
    output_path = Path(OUTPUT_FILE)
    logo_path = Path(LOGO_FILE)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not logo_path.exists():
        raise FileNotFoundError(
            f"Logo file not found: {LOGO_FILE}"
        )

    global_x, global_y, position_offsets = load_calibration()

    print("Global X:", global_x / inch)
    print("Global Y:", global_y / inch)

    pdf = canvas.Canvas(
        str(output_path),
        pagesize=letter,
    )

    logo = ImageReader(str(logo_path))

    for row_index, row_number in enumerate(ROWS):
        for column_index, column_letter in enumerate(COLUMNS):

            position_name = f"{column_letter}{row_number}"

            position_x = (
                position_offsets[position_name]["x"]
                * inch
            )

            position_y = (
                position_offsets[position_name]["y"]
                * inch
            )

            base_x = (
                LEFT_MARGIN
                + global_x
                + column_index
                * (LABEL_DIAMETER + HORIZONTAL_GAP)
            )

            base_y = (
                PAGE_HEIGHT
                - TOP_MARGIN
                - global_y
                - LABEL_DIAMETER
                - row_index
                * (LABEL_DIAMETER + VERTICAL_GAP)
            )

            label_x = base_x + position_x

            # Positive Y moves a label downward.
            label_y = base_y - position_y

            center_x = label_x + LABEL_DIAMETER / 2
            center_y = label_y + LABEL_DIAMETER / 2

            logo_x = center_x - LOGO_SIZE / 2
            logo_y = center_y - LOGO_SIZE / 2

            pdf.drawImage(
                logo,
                logo_x,
                logo_y,
                width=LOGO_SIZE,
                height=LOGO_SIZE,
                preserveAspectRatio=True,
                mask="auto",
            )


    pdf.save()

    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_logo_sticker_sheet()

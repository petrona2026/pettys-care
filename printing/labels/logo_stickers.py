from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import json
from pathlib import Path
OUTPUT_FILE = "generated_pdfs/labels/logo_stickers_test.pdf"

PAGE_WIDTH, PAGE_HEIGHT = letter

# Avery 22877
LABEL_DIAMETER = 2 * inch

COLUMNS = 3
ROWS = 4

LEFT_MARGIN = 0.85 * inch
TOP_MARGIN = 0.60 * inch

CALIBRATION_FILE = Path("printing/calibration.json")

with CALIBRATION_FILE.open("r", encoding="utf-8") as file:
    calibration_data = json.load(file)

label_calibration = calibration_data.get(
    "avery_22877",
    {
        "x_offset": 0.00,
        "y_offset": 0.00,
    },
)

X_OFFSET = label_calibration["x_offset"] * inch
Y_OFFSET = label_calibration["y_offset"] * inch

HORIZONTAL_GAP = 0.5 * inch
VERTICAL_GAP = 0.5 * inch

pdf = canvas.Canvas(OUTPUT_FILE, pagesize=letter)

for row in range(ROWS):
    for col in range(COLUMNS):


        x = (
            LEFT_MARGIN
            + X_OFFSET
            + col * (LABEL_DIAMETER + HORIZONTAL_GAP)
        )
        y = (
            PAGE_HEIGHT
            - TOP_MARGIN
            - Y_OFFSET
            - LABEL_DIAMETER
            - row * (LABEL_DIAMETER + VERTICAL_GAP)
        )

        pdf.circle(
            x + LABEL_DIAMETER / 2,
            y + LABEL_DIAMETER / 2,
            LABEL_DIAMETER / 2,
        )

        pdf.drawCentredString(
            x + LABEL_DIAMETER / 2,
            y + LABEL_DIAMETER / 2,
            "+"
        )

pdf.save()

print("Created:", OUTPUT_FILE)

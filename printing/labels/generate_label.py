from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter

OUTPUT_FILE = "generated_pdfs/labels/orange_sunrise.pdf"

LABEL_WIDTH = 3 * inch
LABEL_HEIGHT = 4 * inch


def create_label():

    Path("generated_pdfs/labels").mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf = canvas.Canvas(
        OUTPUT_FILE,
        pagesize=(LABEL_WIDTH, LABEL_HEIGHT),
    )

    pdf.setFont("Helvetica-Bold", 18)

    pdf.drawCentredString(
        LABEL_WIDTH / 2,
        LABEL_HEIGHT - 0.40 * inch,
        "PETTY'S CARE",
    )

    pdf.setFont("Helvetica", 14)

    pdf.drawCentredString(
        LABEL_WIDTH / 2,
        LABEL_HEIGHT - 0.80 * inch,
        "Orange Sunrise",
    )

    pdf.save()

    print("Created:", OUTPUT_FILE)


if __name__ == "__main__":
    create_label()

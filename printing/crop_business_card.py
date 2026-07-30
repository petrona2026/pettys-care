from pathlib import Path
from PIL import Image


SOURCE_FILE = "static/print/business_cards/back_v1.png"
OUTPUT_FILE = "static/print/business_cards/back_card_only_v1.png"

# Crop coordinates: left, top, right, bottom
CROP_BOX = (516, 139, 995, 414)


def crop_back_card() -> None:
    source = Path(SOURCE_FILE)

    if not source.exists():
        raise FileNotFoundError(f"Image not found: {SOURCE_FILE}")

    image = Image.open(source)

    cropped = image.crop(CROP_BOX)
    cropped.save(OUTPUT_FILE, quality=95)

    print(f"Original size: {image.size}")
    print(f"Cropped size: {cropped.size}")
    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    crop_back_card()

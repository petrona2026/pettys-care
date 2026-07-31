#!/bin/bash

PRINTER="Brother_HL_L3280CDW_series"

FRONT="generated_pdfs/pettys_business_cards_front.pdf"
BACK="generated_pdfs/pettys_business_cards_back.pdf"

echo "Choose what to print:"
echo "1) Front"
echo "2) Back"

read -p "Enter 1 or 2: " choice

case "$choice" in
    1)
        lp -d "$PRINTER" "$FRONT"
        ;;
    2)
        lp -d "$PRINTER" "$BACK"
        ;;
    *)
        echo "Invalid choice."
        exit 1
        ;;
esac

#!/bin/bash
# Script to install OCR system dependencies
# Run this in the deployment environment

echo "Installing OCR system dependencies..."

# Update package list
apt-get update

# Install dependencies
apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng

# Verify installation
echo "Verifying installations..."

if command -v pdfinfo &> /dev/null; then
    echo "✓ poppler-utils installed successfully"
    pdfinfo -v
else
    echo "✗ poppler-utils installation failed"
fi

if command -v tesseract &> /dev/null; then
    echo "✓ tesseract-ocr installed successfully"
    tesseract --version | head -1
    echo "Available languages:"
    tesseract --list-langs
else
    echo "✗ tesseract-ocr installation failed"
fi

echo "Installation complete!"

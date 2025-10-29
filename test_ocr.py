#!/usr/bin/env python3
"""
Test script to verify OCR functionality for PDF page reordering
"""

import sys
import os
sys.path.append('/app/backend')

from PyPDF2 import PdfReader
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

def test_pdf_text_extraction(pdf_path):
    """Test text extraction from PDF with OCR fallback"""
    print(f"Testing PDF: {pdf_path}")
    
    # Try standard text extraction first
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        print(f"Total pages: {total_pages}")
        
        total_text_extracted = 0
        pages_with_text = 0
        
        for page_num in range(min(3, total_pages)):  # Test first 3 pages
            page = reader.pages[page_num]
            text = page.extract_text() or ""
            text = text.strip()
            
            if text and len(text) > 10:
                total_text_extracted += len(text)
                pages_with_text += 1
                print(f"Page {page_num + 1}: Extracted {len(text)} characters")
                print(f"Sample text: {text[:100]}...")
            else:
                print(f"Page {page_num + 1}: No text extracted")
        
        print(f"Standard extraction: {total_text_extracted} characters from {pages_with_text} pages")
        
        # If minimal text, try OCR
        if total_text_extracted < 50:
            print("Attempting OCR...")
            try:
                # Convert first page to image
                images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=200)
                
                if images:
                    # Perform OCR
                    ocr_text = pytesseract.image_to_string(
                        images[0],
                        lang='spa',
                        config='--psm 6'
                    ).strip()
                    
                    if ocr_text and len(ocr_text) > 20:
                        print(f"OCR successful: {len(ocr_text)} characters")
                        print(f"OCR sample: {ocr_text[:100]}...")
                        return True
                    else:
                        print("OCR extracted minimal text")
                        return False
                        
            except Exception as e:
                print(f"OCR failed: {str(e)}")
                return False
        else:
            print("Standard text extraction successful")
            return True
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    # Test with a few PDF files
    test_files = [
        "/app/backend/uploads/00270ec3-1ce6-4110-8b11-7c4ae2c85c57.pdf",
        "/app/backend/uploads/0119ebe0-b2e4-48ad-a34e-e83b311c4dd4.pdf",
        "/app/backend/uploads/pdf_manager_temp/2063ab20-c846-4502-8591-0033ad8cf42d/Test re nombre 181025.pdf"
    ]
    
    success_count = 0
    for pdf_file in test_files:
        if os.path.exists(pdf_file):
            print(f"\n{'='*60}")
            if test_pdf_text_extraction(pdf_file):
                success_count += 1
        else:
            print(f"File not found: {pdf_file}")
    
    print(f"\n{'='*60}")
    print(f"OCR Test Results: {success_count}/{len(test_files)} files processed successfully")
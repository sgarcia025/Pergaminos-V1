#!/usr/bin/env python3
"""Test script to verify OCR functionality"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_text_from_pdf_with_ocr(file_path: str, start_page: int = 0, end_page: int = None, max_pages: int = None) -> str:
    """
    Extract text from PDF with OCR fallback for scanned documents.
    """
    import PyPDF2
    
    pdf_text = ""
    total_text_length = 0
    
    try:
        with open(file_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            total_pdf_pages = len(pdf_reader.pages)
            
            # Determine actual end page
            if end_page is None:
                end_page = total_pdf_pages - 1
            else:
                end_page = min(end_page, total_pdf_pages - 1)
            
            # Apply max_pages limit if specified
            if max_pages is not None:
                end_page = min(start_page + max_pages - 1, end_page)
            
            # First attempt: Extract text using PyPDF2
            pages_processed = 0
            for page_num in range(start_page, end_page + 1):
                page = pdf_reader.pages[page_num]
                pdf_text += f"\n--- PAGE {page_num + 1} ---\n"
                page_text = page.extract_text()
                pdf_text += page_text
                total_text_length += len(page_text.strip())
                pages_processed += 1
            
            logger.info(f"PyPDF2 extracted {total_text_length} characters from {pages_processed} pages")
            
            # If minimal text was extracted, try OCR
            if total_text_length < 50 and pages_processed > 0:
                logger.info(f"Minimal text extracted ({total_text_length} chars). Attempting OCR fallback...")
                
                try:
                    import pytesseract
                    from pdf2image import convert_from_path
                    
                    # Convert PDF pages to images
                    logger.info(f"Converting pages {start_page + 1} to {end_page + 1} to images...")
                    images = convert_from_path(
                        file_path,
                        first_page=start_page + 1,  # pdf2image uses 1-indexed pages
                        last_page=end_page + 1,
                        dpi=200
                    )
                    
                    logger.info(f"Converted {len(images)} pages to images")
                    
                    # Perform OCR on each page
                    pdf_text = ""  # Reset text
                    ocr_success_count = 0
                    
                    for idx, image in enumerate(images):
                        actual_page_num = start_page + idx
                        try:
                            logger.info(f"Running OCR on page {actual_page_num + 1}...")
                            ocr_text = pytesseract.image_to_string(
                                image,
                                lang='spa',
                                config='--psm 6'
                            ).strip()
                            
                            pdf_text += f"\n--- PAGE {actual_page_num + 1} ---\n"
                            pdf_text += ocr_text
                            
                            if ocr_text and len(ocr_text) > 20:
                                ocr_success_count += 1
                                logger.info(f"OCR Page {actual_page_num + 1}: Extracted {len(ocr_text)} characters")
                            else:
                                logger.warning(f"OCR Page {actual_page_num + 1}: Minimal text extracted ({len(ocr_text)} chars)")
                                
                        except Exception as page_ocr_error:
                            logger.error(f"OCR failed for page {actual_page_num + 1}: {str(page_ocr_error)}")
                            pdf_text += f"\n[OCR Error on page {actual_page_num + 1}]\n"
                    
                    logger.info(f"OCR completed: {ocr_success_count}/{pages_processed} pages processed successfully")
                    
                except ImportError as import_error:
                    logger.error(f"OCR libraries not available: {str(import_error)}")
                    pdf_text += "\n[OCR not available - please install pytesseract and pdf2image]\n"
                except Exception as ocr_error:
                    logger.error(f"OCR processing failed: {str(ocr_error)}", exc_info=True)
                    pdf_text += "\n[OCR processing failed]\n"
            
            # Add note if pages were truncated
            if end_page < total_pdf_pages - 1:
                pdf_text += f"\n\n[Note: Document has {total_pdf_pages} total pages, extracted pages {start_page + 1} to {end_page + 1}]"
                    
    except Exception as e:
        logger.error(f"Error extracting PDF text: {str(e)}", exc_info=True)
        pdf_text = f"[Error: Could not extract text from PDF - {str(e)}]"
    
    return pdf_text

if __name__ == "__main__":
    # Find first PDF in uploads directory
    uploads_dir = Path("/app/backend/uploads")
    pdfs = list(uploads_dir.glob("*.pdf"))
    
    if not pdfs:
        print("No PDF files found in uploads directory")
        sys.exit(1)
    
    # Test with first PDF (limited to first 2 pages)
    test_pdf = pdfs[0]
    print(f"Testing OCR with: {test_pdf.name}")
    print(f"File size: {test_pdf.stat().st_size / 1024:.2f} KB")
    print("-" * 80)
    
    text = extract_text_from_pdf_with_ocr(str(test_pdf), max_pages=2)
    
    print("\n" + "="*80)
    print("EXTRACTED TEXT:")
    print("="*80)
    print(text[:1000])  # Print first 1000 characters
    print("\n" + "="*80)
    print(f"Total text length: {len(text)} characters")

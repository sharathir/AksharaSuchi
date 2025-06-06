import os
import json
import pytesseract
from PIL import Image, ImageOps, ImageFilter
import cv2
import numpy as np
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Configure Tesseract path (adjust as needed for your system)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

def preprocess_image(image_path):
    img = Image.open(image_path).convert('RGB')
    gray = ImageOps.grayscale(img)
    opencv_img = np.array(gray)
    thresh = cv2.adaptiveThreshold(opencv_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
    preprocessed_img = Image.fromarray(thresh)
    return preprocessed_img

def perform_ocr_and_extract_hocr(image_path):
    """Performs OCR and returns plain text and hOCR HTML."""
    try:
        preprocessed_img = preprocess_image(image_path)
        full_text = pytesseract.image_to_string(preprocessed_img)
        #hocr_html = pytesseract.image_to_hocr(preprocessed_img)
        #hocr_html = pytesseract.image_to_pdf_or_hocr(preprocessed_img).decode('utf-8')
        #hocr_html = pytesseract.image_to_pdf_or_hocr(preprocessed_img, output_type='pdf').decode('utf-8')
        #hocr_html = pytesseract.image_to_hocr(preprocessed_img, lang='eng', pagesegmode=6)
        #hocr_html = pytesseract.image_to_hocr(preprocessed_img, lang='eng', config='--psm 6')
        hocr_html = pytesseract.image_to_pdf_or_hocr(preprocessed_img, extension='hocr')
        return full_text, hocr_html
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None, None

def extract_metadata(full_text, hocr_html, image_path):
    """Extracts metadata from OCR text, hOCR, and image file."""
    metadata = {
        "filename": os.path.basename(image_path),
        "filepath": os.path.abspath(image_path),
        "processing_timestamp": datetime.now().isoformat()
    }

    # Metadata from full text (simple keyword matching)
    if full_text:
        metadata["full_text_preview"] = full_text[:500] + "..." if len(full_text) > 500 else full_text

        if re.search(r"\binvoice\b", full_text, re.IGNORECASE):
            metadata["document_type"] = "Invoice"
        elif re.search(r"\bcontract\b", full_text, re.IGNORECASE):
            metadata["document_type"] = "Contract"
        elif re.search(r"\breport\b", full_text, re.IGNORECASE):
            metadata["document_type"] = "Report"
        else:
            metadata["document_type"] = "General Document"
        
        date_match = re.search(r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b", full_text)
        if date_match:
            metadata["date_found"] = date_match.group(1)

        # More advanced: try to extract names, addresses using regex or NLP libraries (e.g., spaCy)
        # This is where you'd implement specific extraction logic based on your document types.

    # Metadata from hOCR (for structural info, confidence)
    if hocr_html:
        soup = BeautifulSoup(hocr_html, 'html.parser')
        words = soup.find_all(class_='ocrx_word')
        total_conf = 0
        num_words = 0
        for word_tag in words:
            if 'x_wconf' in word_tag.attrs:
                try:
                    total_conf += int(word_tag['x_wconf'])
                    num_words += 1
                except ValueError:
                    pass
        if num_words > 0:
            metadata["ocr_confidence_avg"] = round(total_conf / num_words, 2)
        
        # You can extract bounding boxes, line by line text, etc. from hOCR if needed
        # metadata["hocr_structure"] = hocr_html # Store full hOCR if desired

    # Metadata from image file (basic EXIF/file properties)
    try:
        with Image.open(image_path) as img:
            metadata["image_format"] = img.format
            metadata["image_width"] = img.width
            metadata["image_height"] = img.height
            
            # EXIF data (if available and relevant for your scanned images)
            if hasattr(img, '_getexif'):
                exifdata = img._getexif()
                if exifdata:
                    for tag_id, value in exifdata.items():
                        tag = TAGS.get(tag_id, tag_id)
                        # Filter for common useful EXIF tags
                        if tag in ['Make', 'Model', 'DateTimeOriginal', 'Software']:
                            metadata[f"exif_{tag.lower()}"] = str(value)
    except Exception as e:
        print(f"Could not extract image file metadata for {image_path}: {e}")

    return metadata

def process_scanned_images(input_dir, output_dir_text, output_dir_metadata):
    """Processes all scanned images in a directory."""
    if not os.path.exists(output_dir_text):
        os.makedirs(output_dir_text)
    if not os.path.exists(output_dir_metadata):
        os.makedirs(output_dir_metadata)

    image_files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.tif'))]
    
    if not image_files:
        print(f"No image files found in {input_dir}. Supported formats: .png, .jpg, .jpeg, .tiff, .tif")
        return

    print(f"Found {len(image_files)} images to process in {input_dir}.")

    for i, image_filename in enumerate(image_files):
        image_path = os.path.join(input_dir, image_filename)
        base_name = os.path.splitext(image_filename)[0]

        print(f"Processing image {i+1}/{len(image_files)}: {image_filename}...")

        full_text, hocr_html = perform_ocr_and_extract_hocr(image_path)
        
        if full_text is None: # OCR failed
            continue

        # Save extracted text
        text_output_path = os.path.join(output_dir_text, f"{base_name}.txt")
        with open(text_output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"  -> Saved OCR text to: {text_output_path}")

        # Extract and save metadata
        metadata = extract_metadata(full_text, hocr_html, image_path)
        metadata_output_path = os.path.join(output_dir_metadata, f"{base_name}.json")
        with open(metadata_output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
        print(f"  -> Saved metadata to: {metadata_output_path}")
        print("-" * 30)

if __name__ == "__main__":
    # Define input and output directories
    input_images_dir = 'scanned_images' # Create this folder and put your scanned images here
    output_texts_dir = 'ocr_texts'
    output_metadata_dir = 'document_metadata'

    # Create dummy image for testing if the directory doesn't exist
    if not os.path.exists(input_images_dir):
        os.makedirs(input_images_dir)
        try:
            # Create a simple image with text for demonstration
            from PIL import ImageDraw, ImageFont
            img = Image.new('RGB', (600, 200), color = 'white')
            d = ImageDraw.Draw(img)
            try:
                # Try to load a default font
                fnt = ImageFont.truetype("arial.ttf", 40)
            except IOError:
                # Fallback to default PIL font if arial.ttf is not found
                fnt = ImageFont.load_default()
            
            d.text((50,50), "Hello, World!", fill=(0,0,0), font=fnt)
            d.text((50,100), "This is a sample document for OCR and tagging. Invoice #12345.", fill=(0,0,0), font=fnt)
            img.save(os.path.join(input_images_dir, 'sample_document_01.png'))
            print(f"Created a sample image '{os.path.join(input_images_dir, 'sample_document_01.png')}' for testing.")
        except Exception as e:
            print(f"Could not create sample image: {e}. Please add some scanned images to '{input_images_dir}' manually.")


    process_scanned_images(input_images_dir, output_texts_dir, output_metadata_dir)
    print("\nProcessing complete.")
    print(f"OCR texts saved in: {output_texts_dir}")
    print(f"Metadata saved in: {output_metadata_dir}")
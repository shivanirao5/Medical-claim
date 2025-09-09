import cv2
import numpy as np
from PIL import Image
import pytesseract
from pdf2image import convert_from_path, convert_from_bytes
import io

# The following module centralizes OCR utilities used by the backend.
# It includes helpers to load images from bytes, preprocess images for
# OCR (denoise, enhance contrast, threshold, deskew) and functions to
# extract text either via direct PDF text extraction or by converting
# PDF pages to images and running OCR on them.

# ---------------------------------------------------------------------------
# Image loading helper
# ---------------------------------------------------------------------------
def load_image_from_bytes(file_bytes: bytes) -> np.ndarray:
    """Load image from raw bytes and convert to OpenCV BGR format.

    Why: The backend accepts uploaded image files (or PDF pages converted
    to images). Pillow is used to open image bytes reliably, then we
    convert to a NumPy array and swap channels to BGR for OpenCV
    processing which is used by subsequent preprocessing steps.
    """
    img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------------------
# Image preprocessing pipeline
# ---------------------------------------------------------------------------
def preprocess_image(img: np.ndarray) -> np.ndarray:
    """Preprocess an OpenCV BGR image for OCR and return a binary image.

    Steps and why they're used:
    - Convert to grayscale: OCR works better on single-channel images.
    - Denoise: Remove camera/scanner noise to improve OCR accuracy.
    - Contrast enhancement (CLAHE): Improve local contrast on unevenly
      lit scans so text is more distinct from background.
    - Thresholding (Otsu): Convert to a clean black-and-white image,
      which generally yields better OCR results than grayscale.
    - Deskew: Detect page rotation and rotate back to horizontal so
      OCR engines don't fail on tilted text.

    Why: These operations together produce a high-quality binary image
    that significantly improves text detection and OCR accuracy on
    scanned documents and photos of pages.
    """
    # Convert to gray
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Denoise - remove salt-and-pepper and other scanning noise
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

    # Contrast enhancement using CLAHE (adaptive histogram equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # Thresholding to a clean B/W image using Otsu's method
    _, th = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Deskew: compute angle of the largest text block and rotate back
    coords = np.column_stack(np.where(th > 0))
    angle = 0.0
    if coords.shape[0] > 0:
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        if angle < -45:
            # Rect returns angle in range [-90, 0); convert to usable
            angle = -(90 + angle)
        else:
            angle = -angle
    (h, w) = th.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    deskewed = cv2.warpAffine(th, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return deskewed


# ---------------------------------------------------------------------------
# OCR wrapper
# ---------------------------------------------------------------------------
def ocr_image(img: np.ndarray, lang: str = 'eng') -> str:
    """Run Tesseract OCR on a preprocessed image.

    Why: This function converts the NumPy array back to a PIL image
    because pytesseract expects a PIL image or filename. Configuration
    sets OCR Engine Mode and Page Segmentation Mode to reasonable defaults
    for page-level OCR.
    """
    pil_img = Image.fromarray(img)
    custom_config = r'--oem 1 --psm 3'
    text = pytesseract.image_to_string(pil_img, lang=lang, config=custom_config)
    return text


# ---------------------------------------------------------------------------
# PDF text extraction with OCR fallback
# ---------------------------------------------------------------------------
def extract_text_from_pdf_bytes(file_bytes: bytes, max_pages: int = None) -> str:
    """Extract readable text from PDF bytes.

    Strategy (and why):
    1. Try text extraction via PyPDF2 first because it is fast and preserves
       layout for text-based PDFs produced digitally.
    2. If text extraction produces little or no output (typical for scanned
       PDFs), fall back to converting PDF pages to images and run OCR on
       each page.
    3. If pdf2image or OCR fails (poppler missing or other error), attempt
       a final pass with PyPDF2 over all pages to salvage any embedded text.

    This layered approach ensures we use the cheapest, most reliable
    method first and only use expensive OCR when necessary.
    """
    # Try text extraction first (faster for text-based PDFs)
    try:
        import PyPDF2
        from io import BytesIO

        pdf_reader = PyPDF2.PdfReader(BytesIO(file_bytes))
        total_pages = len(pdf_reader.pages)

        # Process ALL pages unless max_pages is specified
        pages_to_process = total_pages if max_pages is None else min(max_pages, total_pages)

        print(f"Extracting text from {pages_to_process} pages (total: {total_pages})")

        text_content = []
        pages_with_text = 0

        for page_num in range(pages_to_process):
            try:
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    # Keep page markers so multi-page results can be split later
                    text_content.append(f"=== PAGE {page_num + 1} ===\n{page_text}")
                    pages_with_text += 1
            except Exception as e:
                print(f"Error extracting text from page {page_num + 1}: {e}")
                continue

        extracted_text = '\n\n'.join(text_content).strip()

        # If we got meaningful text, return it to avoid heavy OCR work
        if len(extracted_text) > 100 and pages_with_text > 0:
            print(f"Successfully extracted text from {pages_with_text}/{pages_to_process} pages")
            return extracted_text
        else:
            print(f"Text extraction yielded little content ({len(extracted_text)} chars from {pages_with_text} pages)")

    except Exception as e:
        # If PyPDF2 import or parsing fails, log and continue to OCR
        print(f"Text extraction failed: {e}")

    # Fallback to OCR if text extraction failed or yielded little content
    try:
        print("Falling back to OCR for all pages...")
        # Convert pages to images (either limited by max_pages or all pages)
        pages_to_convert = None if max_pages is None else max_pages

        if pages_to_convert:
            pages = convert_from_bytes(file_bytes, dpi=300, first_page=1, last_page=pages_to_convert)
        else:
            pages = convert_from_bytes(file_bytes, dpi=300)  # Convert ALL pages

        print(f"Converting and OCR processing {len(pages)} pages...")

        texts = []
        for i, page in enumerate(pages):
            try:
                print(f"OCR processing page {i+1}/{len(pages)}...")
                # Convert PIL page to OpenCV BGR image, preprocess, OCR
                img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
                pre = preprocess_image(img)
                page_text = ocr_image(pre)

                if page_text and page_text.strip():
                    texts.append(f"=== PAGE {i+1} (OCR) ===\n{page_text}")

            except Exception as page_error:
                # Keep OCR failure per-page information so caller can see which
                # pages failed and why (useful for debugging scanned docs)
                print(f"OCR failed for page {i+1}: {page_error}")
                texts.append(f"=== PAGE {i+1} (OCR FAILED) ===\nCould not process this page")
                continue

        ocr_result = '\n\n'.join(texts)
        if ocr_result:
            return ocr_result

    except Exception as e:
        # If pdf2image fails (e.g., poppler not installed), we log it and
        # attempt a final best-effort extraction using PyPDF2 over all pages
        print(f"OCR extraction failed: {e}")

        # Final fallback: try to extract any available text without page limits
        try:
            import PyPDF2
            from io import BytesIO

            pdf_reader = PyPDF2.PdfReader(BytesIO(file_bytes))
            text_content = []

            # Extract from ALL pages as final attempt
            for page_num in range(len(pdf_reader.pages)):
                try:
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
                except:
                    continue

            result = '\n'.join(text_content).strip()
            if result:
                return result
            else:
                # Informative message for the caller indicating OCR is needed
                return "No text could be extracted from this PDF. This might be a scanned document that requires OCR with proper image processing setup (pdf2image + pytesseract)."

        except Exception as final_e:
            # If everything fails, provide helpful diagnostic text
            return f"PDF processing failed: {final_e}. Please ensure the PDF is not corrupted and try again."

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Set, Optional
import re

from fastapi.concurrency import run_in_threadpool

from parser import parse_claim
from models import ExtractedClaim, ClaimItem
from medicine_matcher import MedicineMatchingService, analyze_medicine_compliance
from claim_parser import MedicalClaimParser
from enhanced_ocr_utils import HandwrittenPrescriptionOCR, extract_text_from_pdf_bytes, extract_text_from_image_bytes

load_dotenv()

app = FastAPI(title='Medical Claim OCR - Enhanced for Handwritten Prescriptions')
medicine_service = MedicineMatchingService()
claim_parser = MedicalClaimParser()
handwritten_ocr = HandwrittenPrescriptionOCR()


@app.post('/extract')
async def extract(file: UploadFile = File(...), enhance_handwriting: Optional[bool] = Form(True)):
    """API endpoint to receive a file and return structured claim data.
    
    Enhanced with handwritten prescription support:
    - Set enhance_handwriting=True (default) for handwritten prescriptions
    - Uses advanced image preprocessing and ensemble OCR for better accuracy
    - Validates medicine names and provides confidence scores
    - Falls back to standard OCR for printed documents
    
    Behavior and rationale:
    - We read the uploaded file bytes and attempt text extraction first
      using PyPDF2 (fast for digital PDFs).
    - If text extraction doesn't produce meaningful content, the enhanced OCR
      utilities will be invoked with specialized handwriting processing.
    - For handwritten prescriptions, multiple preprocessing techniques are applied
      and results are combined for maximum accuracy.
    """
    try:
        contents = await file.read()
        text = ''
        
        print(f"Processing file: {file.filename}, content_type: {file.content_type}, size: {len(contents)} bytes")

        # Handle text files directly
        if (file.content_type and file.content_type.startswith('text/')) or \
           (file.filename and file.filename.lower().endswith(('.txt', '.md', '.csv'))):
            print("Processing as text file")
            text = contents.decode('utf-8', errors='ignore')
            
        # PDF files - Handle ALL pages with enhanced OCR for handwriting
        elif file.content_type == 'application/pdf' or \
             (file.filename and file.filename.lower().endswith('.pdf')):
            print(f"Processing as PDF file (handwriting enhancement: {enhance_handwriting})")
            if enhance_handwriting:
                text = extract_text_from_pdf_bytes(contents, enhance_handwriting=True)
            else:
                text = await extract_all_pdf_content(contents, file.filename)
                
        # Image files - Use enhanced OCR for handwriting
        elif (file.content_type and file.content_type.startswith('image/')) or \
             (file.filename and file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff'))):
            print(f"Processing as image file (handwriting enhancement: {enhance_handwriting})")
            if enhance_handwriting:
                text = extract_text_from_image_bytes(contents, enhance_handwriting=True)
            else:
                text = await extract_image_content(contents)
                
        # For any other file type, try as text
        else:
            print(f"Unknown file type, trying as text. Content type: {file.content_type}")
            try:
                text = contents.decode('utf-8', errors='ignore')
            except:
                text = f"Could not process file type: {file.content_type}"

        # Ensure we have some text
        if not text or not text.strip():
            print("No text extracted")
            text = f"No readable text found in {file.filename}"
        
        print(f"Successfully extracted {len(text)} characters of text")
        print(f"First 300 chars: {text[:300]}")  # Debug output

        # Parse into structured claim with NEW claim parser
        claim: ExtractedClaim = parse_claim(text)
        claim.text_quality = {'quality': 'Good' if len(text) > 50 else 'Poor', 'score': 75 if len(text) > 50 else 25}
        
        # Parse pages into structured claim items
        if '=== PAGE' in text or re.search(r'===\s*PAGE', text):
            # Robustly split OCR/text output which uses page markers like:
            #   === PAGE 1 (OCR) ===\n<page text>\n\n=== PAGE 2 ===\n...
            # The previous naive split removed the actual page contents. Use a
            # regex that strips the header markers and collects the content
            # between them.
            page_texts = []
            try:
                # Pattern matches the header '=== PAGE ... ===' including any
                # trailing newline. Splitting on it leaves only the page bodies.
                pattern = r'===\s*PAGE\b.*?===(?:\r?\n)'
                parts = re.split(pattern, text, flags=re.IGNORECASE)
                # re.split will include text before the first marker (often empty)
                for part in parts:
                    part = part.strip()
                    if part:
                        page_texts.append(part)

                # If regex splitting found nothing, fall back to treating the
                # whole text as a single page
                if not page_texts:
                    page_texts = [text.strip()]

            except Exception:
                # On any regex error, keep a safe fallback
                page_texts = [text.strip()]

            claim_items = claim_parser.parse_multiple_pages(page_texts)
        else:
            # Single page or unified content
            claim_items = [claim_parser.parse_medical_claim(text)]
        
        claim.claim_items = [item.__dict__ for item in claim_items]  # Convert to dict for JSON
        claim.total_pages = len(claim_items)
        claim.processing_status = "completed"
        
        # Add medicine analysis (backward compatibility)
        medicines = medicine_service.extract_medicine_names(text)
        claim.medicines = medicines

        return JSONResponse(content=claim.dict())
        
    except Exception as e:
        print(f"Overall processing failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'Processing failed: {str(e)}')


async def extract_all_pdf_content(contents: bytes, filename: str) -> str:
    """Extract text from ALL pages of PDF with OCR fallback for scanned PDFs"""
    try:
        import PyPDF2
        from io import BytesIO
        
        pdf_reader = PyPDF2.PdfReader(BytesIO(contents))
        total_pages = len(pdf_reader.pages)
        print(f"PDF has {total_pages} pages - processing ALL pages")
        
        text_content = []
        pages_with_text = 0
        
        # Extract text from ALL pages
        for page_num in range(total_pages):
            try:
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_content.append(f"=== PAGE {page_num + 1} ===\n{page_text}")
                    pages_with_text += 1
                    print(f"Extracted text from page {page_num + 1}: {len(page_text)} chars")
                else:
                    print(f"Page {page_num + 1}: No text found (likely scanned)")
            except Exception as page_error:
                print(f"Error processing page {page_num + 1}: {page_error}")
                continue
        
        extracted_text = '\n\n'.join(text_content).strip()
        
        # If we got very little text, it's likely a scanned PDF - use OCR
        if len(extracted_text) < 100 or pages_with_text < (total_pages * 0.3):
            print(f"PDF appears to be mostly scanned ({pages_with_text}/{total_pages} pages with text)")
            print("Attempting OCR on ALL pages...")
            
            try:
                # Try OCR extraction for all pages
                ocr_text = await extract_pdf_with_ocr_simple(contents, total_pages)
                if len(ocr_text) > len(extracted_text):
                    print(f"OCR produced more text ({len(ocr_text)} vs {len(extracted_text)} chars)")
                    return ocr_text
                else:
                    return extracted_text or ocr_text
                    
            except Exception as ocr_error:
                print(f"OCR failed: {ocr_error}")
                # Return whatever text we managed to extract
                return extracted_text or f"Could not extract text from scanned PDF: {str(ocr_error)}"
        
        return extracted_text
        
    except Exception as pdf_error:
        print(f"PDF processing failed: {pdf_error}")
        return f"Could not extract text from PDF: {str(pdf_error)}"


async def extract_pdf_with_ocr_simple(contents: bytes, total_pages: int) -> str:
    """Simplified OCR extraction that should work"""
    try:
        print("Importing OCR libraries...")
        from pdf2image import convert_from_bytes
        import pytesseract
        import cv2
        import numpy as np
        import os
        
        # Set poppler path for Windows
        poppler_path = os.path.join(os.path.dirname(__file__), "poppler", "poppler-23.01.0", "Library", "bin")
        print(f"Using poppler path: {poppler_path}")
        
        print(f"Converting all {total_pages} pages to images for OCR...")
        
        # Convert ALL pages to images with high DPI for better OCR
        pages = convert_from_bytes(contents, dpi=200, first_page=1, last_page=total_pages, poppler_path=poppler_path)
        print(f"Successfully converted {len(pages)} pages to images")
        
        texts = []
        for i, page in enumerate(pages):
            try:
                print(f"Processing page {i+1}/{len(pages)} with OCR...")
                
                # Convert PIL image to numpy array for OpenCV
                img_array = np.array(page)
                
                # Convert RGB to BGR for OpenCV
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # Convert to grayscale for better OCR
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                
                # Apply thresholding to get better text
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Extract text with OCR
                page_text = pytesseract.image_to_string(thresh, config='--psm 6')
                
                if page_text and page_text.strip():
                    clean_text = page_text.strip()
                    texts.append(f"=== PAGE {i+1} (OCR) ===\n{clean_text}")
                    print(f"OCR page {i+1}: extracted {len(clean_text)} characters")
                else:
                    print(f"OCR page {i+1}: no text found")
                    texts.append(f"=== PAGE {i+1} (OCR) ===\nNo text detected on this page")
                    
            except Exception as page_error:
                print(f"OCR failed for page {i+1}: {page_error}")
                texts.append(f"=== PAGE {i+1} (OCR FAILED) ===\nError: {str(page_error)}")
                continue
        
        result = '\n\n'.join(texts)
        print(f"OCR completed. Total extracted text: {len(result)} characters")
        return result
        
    except Exception as ocr_error:
        import traceback
        error_details = traceback.format_exc()
        print(f"OCR processing failed: {ocr_error}")
        print(f"Error details: {error_details}")
        return f"OCR processing failed: {str(ocr_error)}"


async def extract_image_content(contents: bytes) -> str:
    """Extract text from image using OCR"""
    try:
        # Import inside function to avoid startup issues
        from PIL import Image
        import cv2
        import numpy as np
        import pytesseract
        from io import BytesIO
        
        print("Loading and preprocessing image...")
        
        # Load image
        img = Image.open(BytesIO(contents)).convert('RGB')
        img_array = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Simple preprocessing
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Extract text
        text = pytesseract.image_to_string(thresh, config='--psm 6')
        
        print(f"OCR extracted {len(text)} characters from image")
        return text
        
    except ImportError:
        return "Image OCR is not available. Please install OpenCV and pytesseract."
    except Exception as ocr_error:
        print(f"Image OCR failed: {ocr_error}")
        return f"Could not extract text from image: {str(ocr_error)}"


@app.post('/compare-medicines')
async def compare_medicines(bill_file: UploadFile = File(...), prescription_file: UploadFile = File(...)):
    """Compare medicines between bill and prescription"""
    try:
        # Extract text from both files
        bill_content = await bill_file.read()
        prescription_content = await prescription_file.read()
        
        bill_text = bill_content.decode('utf-8', errors='ignore')
        prescription_text = prescription_content.decode('utf-8', errors='ignore')
        
        # Analyze compliance
        analysis = analyze_medicine_compliance(bill_text, prescription_text)
        
        return JSONResponse(content=analysis)
        
    except Exception as e:
        print(f"Medicine comparison failed: {e}")
        raise HTTPException(status_code=500, detail=f'Medicine comparison failed: {str(e)}')


@app.post('/compare')
async def compare_files(files: List[UploadFile] = File(...)) -> JSONResponse:
    """Compare multiple uploaded files by extracting full text from each and
    returning pairwise similarity metrics.

    How it works:
    - For each uploaded file we perform the same robust extraction used by
      `/extract`: text-first extraction for PDFs, OCR fallback for scanned
      pages, and image OCR for image files.
    - We normalize text and compute a token set per file. Pairwise Jaccard
      similarity is computed between token sets as a simple measure of
      overlap. We also return small samples of common tokens/lines and
      unique tokens to help surface differences.

    This endpoint helps checking whether two or more documents contain the
    same or overlapping content (useful for comparing bills, prescriptions,
    or multi-page extractions).
    """
    try:
        if not files or len(files) < 2:
            raise HTTPException(status_code=400, detail='Please upload two or more files to compare')

        extracted = []  # list of dicts: {filename, text}

        # Helper: tokenize text to set of words
        def tokenize(text: str) -> Set[str]:
            toks = re.findall(r"\w+", text.lower())
            return set([t for t in toks if len(t) > 1])

        # Extract text from each file using existing extraction helpers
        for f in files:
            contents = await f.read()
            fname = f.filename or 'uploaded'
            text = ''

            # Text-like files
            if (f.content_type and f.content_type.startswith('text/')) or (fname.lower().endswith(('.txt', '.md', '.csv'))):
                text = contents.decode('utf-8', errors='ignore')

            # PDF files
            elif f.content_type == 'application/pdf' or fname.lower().endswith('.pdf'):
                # reuse extract_all_pdf_content which handles page-level OCR fallback
                text = await extract_all_pdf_content(contents, fname)

            # Images
            elif (f.content_type and f.content_type.startswith('image/')) or fname.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
                text = await extract_image_content(contents)

            else:
                # Try decode, otherwise best-effort PDF OCR via threadpool
                try:
                    text = contents.decode('utf-8', errors='ignore')
                except Exception:
                    # fall back to OCR library in threadpool (sync helper)
                    try:
                        from backend import ocr_utils

                        text = await run_in_threadpool(ocr_utils.extract_text_from_pdf_bytes, contents)
                    except Exception:
                        text = ''

            extracted.append({'filename': fname, 'text': text or ''})

        # Build token sets and line sets
        for e in extracted:
            e['tokens'] = tokenize(e['text'])
            # Normalized non-empty lines
            e['lines'] = [ln.strip() for ln in e['text'].splitlines() if ln.strip()]

        # Pairwise comparisons
        comparisons: List[Dict[str, Any]] = []
        n = len(extracted)
        for i in range(n):
            for j in range(i + 1, n):
                a = extracted[i]
                b = extracted[j]
                tokens_a = a['tokens']
                tokens_b = b['tokens']
                union = tokens_a.union(tokens_b)
                inter = tokens_a.intersection(tokens_b)
                jaccard = len(inter) / len(union) if union else 0.0

                # lines overlap (exact line matches)
                set_lines_a = set(a['lines'])
                set_lines_b = set(b['lines'])
                common_lines = list(set_lines_a.intersection(set_lines_b))

                comparisons.append({
                    'file_a': a['filename'],
                    'file_b': b['filename'],
                    'jaccard_similarity': round(jaccard, 4),
                    'common_tokens_count': len(inter),
                    'common_tokens_sample': list(inter)[:20],
                    'unique_to_a_sample': list(tokens_a - tokens_b)[:20],
                    'unique_to_b_sample': list(tokens_b - tokens_a)[:20],
                    'common_lines_sample': common_lines[:10]
                })

        # Prepare response with short previews
        files_summary = []
        for e in extracted:
            files_summary.append({
                'filename': e['filename'],
                'text_preview': e['text'][:1000],
                'tokens_count': len(e['tokens'])
            })

        response = {
            'files': files_summary,
            'comparisons': comparisons,
            'note': 'Jaccard similarity computed on token sets (lowercased words). Use comparisons to find overlapping content.'
        }

        return JSONResponse(content=response)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Compare endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f'Compare failed: {str(e)}')


@app.post('/extract-handwritten')
async def extract_handwritten_prescription(file: UploadFile = File(...)):
    """
    Specialized endpoint for handwritten prescription processing
    Uses advanced OCR techniques optimized for handwriting recognition
    """
    try:
        contents = await file.read()
        print(f"Processing handwritten prescription: {file.filename}, size: {len(contents)} bytes")
        
        # Force handwritten enhancement
        if (file.content_type and file.content_type.startswith('image/')) or \
           (file.filename and file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff'))):
            
            # Use enhanced handwritten OCR
            result = handwritten_ocr.process_prescription_image(contents)
            text = result['text']
            
            # Create enhanced response with OCR metadata
            enhanced_result = {
                'text': text,
                'confidence': result.get('confidence', 0),
                'ocr_method': result.get('method', 'unknown'),
                'preprocessing_used': result.get('preprocessing_used', 0),
                'alternative_texts': result.get('alternative_texts', []),
                'medicine_mentions': result.get('medicine_mentions', []),
                'ensemble_size': result.get('ensemble_size', 1),
                'processing_pipeline': 'handwritten_prescription_enhanced'
            }
            
        elif file.content_type == 'application/pdf' or \
             (file.filename and file.filename.lower().endswith('.pdf')):
            
            # Use enhanced PDF processing for handwriting
            text = extract_text_from_pdf_bytes(contents, enhance_handwriting=True)
            enhanced_result = {
                'text': text,
                'confidence': 85,  # Reasonable default for PDF processing
                'processing_pipeline': 'handwritten_pdf_enhanced'
            }
            
        else:
            raise HTTPException(status_code=400, detail="Only image and PDF files are supported for handwritten prescription processing")
        
        # Parse the extracted text
        if text and text.strip():
            claim: ExtractedClaim = parse_claim(text)
            claim.text_quality = {
                'quality': 'Enhanced Handwriting OCR',
                'confidence': enhanced_result.get('confidence', 0),
                'method': enhanced_result.get('ocr_method', 'enhanced')
            }
            
            # Add OCR-specific metadata
            claim.raw_text = text
            claim.processing_status = "completed_handwritten"
            
            # Medicine analysis with enhanced detection
            medicines = medicine_service.extract_medicine_names(text)
            if enhanced_result.get('medicine_mentions'):
                # Combine detected medicines with OCR medicine mentions
                all_medicines = medicines + [{'name': med, 'confidence': 0.8, 'source': 'ocr_validation'} 
                                           for med in enhanced_result['medicine_mentions']]
                claim.medicines = all_medicines
            else:
                claim.medicines = medicines
            
            # Prepare response
            response_data = claim.dict()
            response_data.update({
                'ocr_metadata': enhanced_result,
                'handwritten_processing': True
            })
            
            return JSONResponse(content=response_data)
        else:
            return JSONResponse(content={
                'error': 'No text could be extracted from the handwritten prescription',
                'ocr_metadata': enhanced_result,
                'suggestion': 'Try uploading a clearer image with better lighting'
            }, status_code=422)
            
    except Exception as e:
        print(f"Handwritten prescription processing failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'Handwritten prescription processing failed: {str(e)}')


@app.get('/health')
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0", "features": ["handwritten_prescriptions", "file_comparison", "enhanced_ocr"]}

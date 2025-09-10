"""Advanced OCR service for handwritten content extraction.

This service converts PDFs to high-resolution images and uses multiple OCR engines
to extract handwritten text from medical documents, receipts, and bills.
"""
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from typing import List, Dict, Any, Tuple, Optional
import io
import logging
import importlib
from types import ModuleType

# Dynamically import PyMuPDF (fitz) to avoid static analysis / unresolved-import errors
# in environments where the package is not installed.
try:
    fitz = importlib.import_module("fitz")
    if not isinstance(fitz, ModuleType):
        fitz = None
except Exception:
    fitz = None

logger = logging.getLogger(__name__)

class AdvancedOCRService:
    """Advanced OCR with PDF-to-image conversion and handwriting recognition."""
    
    def __init__(self):
        # Configure Tesseract for better handwriting recognition
        self.handwriting_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,₹Rs/-() '
        self.standard_config = r'--oem 3 --psm 6'
        
    def convert_pdf_to_images(self, pdf_bytes: bytes, dpi: int = 300) -> List[np.ndarray]:
        """Convert PDF to high-resolution images for better OCR with fallback options."""
        try:
            # Try pdf2image first (better quality when Poppler is available)
            from pdf2image import convert_from_bytes
            
            pil_images = convert_from_bytes(
                pdf_bytes,
                dpi=dpi,
                fmt='RGB',
                thread_count=1
            )
            
            # Convert PIL images to numpy arrays for OpenCV processing
            cv_images = []
            for pil_img in pil_images:
                cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                cv_images.append(cv_img)
                
            logger.info(f"Converted PDF to {len(cv_images)} images at {dpi} DPI using pdf2image")
            return cv_images
            
        except Exception as e:
            logger.warning(f"pdf2image failed: {e}, trying PyMuPDF fallback")
            
            # Fallback to PyMuPDF
            if fitz is not None:
                try:
                    import io
                    
                    # Open PDF from bytes
                    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    cv_images = []
                    
                    for page_num in range(pdf_doc.page_count):
                        page = pdf_doc[page_num]
                        # Render page to image at specified DPI
                        mat = fitz.Matrix(dpi/72, dpi/72)  # DPI transformation matrix
                        pix = page.get_pixmap(matrix=mat)
                        
                        # Convert to numpy array for OpenCV
                        img_data = pix.tobytes("png")
                        pil_img = Image.open(io.BytesIO(img_data))
                        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                        cv_images.append(cv_img)
                        
                    pdf_doc.close()
                    logger.info(f"Converted PDF to {len(cv_images)} images at {dpi} DPI using PyMuPDF fallback")
                    return cv_images
                except Exception as fallback_error:
                    logger.error(f"Both pdf2image and PyMuPDF failed: {fallback_error}")
                    return []
            else:
                logger.error("pdf2image failed and PyMuPDF is not available as a fallback")
                return []
    
    def preprocess_for_handwriting(self, image: np.ndarray) -> np.ndarray:
        """Enhanced preprocessing specifically for handwritten text."""
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Adaptive thresholding for varying lighting conditions
            adaptive_thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Morphological operations to connect broken text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            morphed = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_CLOSE, kernel)
            
            # Enhance contrast
            enhanced = cv2.convertScaleAbs(morphed, alpha=1.2, beta=10)
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Handwriting preprocessing failed: {e}")
            return image
    
    def preprocess_for_standard_text(self, image: np.ndarray) -> np.ndarray:
        """Standard preprocessing for printed text."""
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Apply bilateral filter to reduce noise while preserving edges
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # Apply OTSU thresholding for clear black/white separation
            _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Dilate to make text thicker
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            dilated = cv2.dilate(thresh, kernel, iterations=1)
            
            return dilated
            
        except Exception as e:
            logger.error(f"Standard preprocessing failed: {e}")
            return image
    
    def extract_text_with_confidence(self, image: np.ndarray, config: str) -> Dict[str, Any]:
        """Extract text with confidence scores and bounding boxes."""
        try:
            # Get detailed OCR data including confidence
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            
            # Filter out low confidence detections
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 30]
            texts = [data['text'][i] for i, conf in enumerate(data['conf']) if int(conf) > 30 and data['text'][i].strip()]
            
            # Combine into full text
            full_text = ' '.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'text': full_text,
                'confidence': avg_confidence,
                'word_count': len(texts),
                'individual_words': texts
            }
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {
                'text': '',
                'confidence': 0,
                'word_count': 0,
                'individual_words': []
            }
    
    def detect_handwriting_regions(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect regions likely to contain handwriting."""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            
            # Use edge detection to find handwritten areas
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours by size and aspect ratio (typical for handwriting)
            handwriting_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter based on size and aspect ratio
                if w > 20 and h > 10 and w < image.shape[1] * 0.8:
                    aspect_ratio = w / h
                    if 0.1 < aspect_ratio < 10:  # Reasonable aspect ratio for text
                        handwriting_regions.append((x, y, w, h))
            
            return handwriting_regions
            
        except Exception as e:
            logger.error(f"Handwriting detection failed: {e}")
            return []
    
    def process_pdf_for_handwriting(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """Complete pipeline for processing PDF with handwriting extraction."""
        try:
            # Convert PDF to images
            images = self.convert_pdf_to_images(pdf_bytes, dpi=300)
            
            if not images:
                return {'error': 'Failed to convert PDF to images'}
            
            all_results = []
            total_text = []
            avg_confidence = 0
            
            for page_num, image in enumerate(images):
                logger.info(f"Processing page {page_num + 1}/{len(images)}")
                
                # Try both handwriting and standard preprocessing
                handwriting_processed = self.preprocess_for_handwriting(image)
                standard_processed = self.preprocess_for_standard_text(image)
                
                # Extract text using both methods
                handwriting_result = self.extract_text_with_confidence(
                    handwriting_processed, self.handwriting_config
                )
                standard_result = self.extract_text_with_confidence(
                    standard_processed, self.standard_config
                )
                
                # Choose the result with higher confidence or longer text
                if handwriting_result['confidence'] > standard_result['confidence']:
                    page_result = handwriting_result
                    ocr_method = 'handwriting_optimized'
                elif len(handwriting_result['text']) > len(standard_result['text']):
                    page_result = handwriting_result
                    ocr_method = 'handwriting_optimized'
                else:
                    page_result = standard_result
                    ocr_method = 'standard'
                
                page_result['page'] = page_num + 1
                page_result['ocr_method'] = ocr_method
                all_results.append(page_result)
                
                if page_result['text'].strip():
                    total_text.append(f"=== Page {page_num + 1} ===")
                    total_text.append(page_result['text'])
                    total_text.append("")
            
            # Calculate overall confidence
            confidences = [r['confidence'] for r in all_results if r['confidence'] > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'text': '\n'.join(total_text),
                'confidence': avg_confidence,
                'pages_processed': len(images),
                'page_results': all_results,
                'extraction_method': 'advanced_pdf_to_image_ocr'
            }
            
        except Exception as e:
            logger.error(f"PDF handwriting processing failed: {e}")
            return {'error': f'PDF processing failed: {str(e)}'}
    
    def process_image_for_handwriting(self, image_bytes: bytes) -> Dict[str, Any]:
        """Process image with advanced handwriting recognition."""
        try:
            # Load image
            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            
            if image is None:
                return {'error': 'Failed to load image'}
            
            # Detect handwriting regions
            handwriting_regions = self.detect_handwriting_regions(image)
            
            # Process full image with both methods
            handwriting_processed = self.preprocess_for_handwriting(image)
            standard_processed = self.preprocess_for_standard_text(image)
            
            handwriting_result = self.extract_text_with_confidence(
                handwriting_processed, self.handwriting_config
            )
            standard_result = self.extract_text_with_confidence(
                standard_processed, self.standard_config
            )
            
            # Process individual handwriting regions
            region_texts = []
            for i, (x, y, w, h) in enumerate(handwriting_regions[:10]):  # Limit to 10 regions
                roi = image[y:y+h, x:x+w]
                roi_processed = self.preprocess_for_handwriting(roi)
                roi_result = self.extract_text_with_confidence(
                    roi_processed, self.handwriting_config
                )
                if roi_result['text'].strip():
                    region_texts.append(f"Region {i+1}: {roi_result['text']}")
            
            # Combine results
            combined_text = []
            
            # Use the better of the two full-image results
            if handwriting_result['confidence'] > standard_result['confidence']:
                main_result = handwriting_result
                method = 'handwriting_optimized'
            else:
                main_result = standard_result
                method = 'standard'
            
            if main_result['text'].strip():
                combined_text.append("=== Full Image Text ===")
                combined_text.append(main_result['text'])
            
            if region_texts:
                combined_text.append("\n=== Handwriting Regions ===")
                combined_text.extend(region_texts)
            
            return {
                'text': '\n'.join(combined_text),
                'confidence': main_result['confidence'],
                'handwriting_regions_found': len(handwriting_regions),
                'extraction_method': f'{method}_with_region_detection',
                'full_image_result': main_result,
                'region_results': region_texts
            }
            
        except Exception as e:
            logger.error(f"Image handwriting processing failed: {e}")
            return {'error': f'Image processing failed: {str(e)}'}
    
    def process_file_advanced(self, file_bytes: bytes, filename: str = None, content_type: str = None) -> Dict[str, Any]:
        """Main entry point for advanced OCR processing with automatic mode detection."""
        try:
            logger.info(f"Processing file: {filename} ({content_type}) with automatic OCR mode detection")
            
            if content_type == 'application/pdf' or (filename and filename.lower().endswith('.pdf')):
                # Always use enhanced processing for PDFs to capture both printed and handwritten content
                return self.process_pdf_for_handwriting(file_bytes)
            
            elif content_type and content_type.startswith('image/') or (filename and any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff'])):
                # Use advanced image processing that handles both printed and handwritten content
                return self.process_image_comprehensive(file_bytes)
            
            else:
                # Try to decode as text file
                try:
                    text = file_bytes.decode('utf-8', errors='ignore')
                    return {
                        'text': text,
                        'confidence': 100,
                        'extraction_method': 'text_file'
                    }
                except Exception:
                    return {'error': 'Unsupported file format'}
            
        except Exception as e:
            logger.error(f"Advanced OCR processing failed: {e}")
            return {'error': f'Processing failed: {str(e)}'}
    
    def process_image_comprehensive(self, image_bytes: bytes) -> Dict[str, Any]:
        """Comprehensive image processing that handles both printed and handwritten content."""
        try:
            # Load image
            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            
            if image is None:
                return {'error': 'Failed to load image'}
            
            # Try multiple processing approaches
            results = []
            
            # Approach 1: Standard OCR
            standard_processed = self.preprocess_for_standard_text(image)
            standard_result = self.extract_text_with_confidence(standard_processed, self.standard_config)
            standard_result['method'] = 'standard_ocr'
            results.append(standard_result)
            
            # Approach 2: Handwriting-optimized OCR
            handwriting_processed = self.preprocess_for_handwriting(image)
            handwriting_result = self.extract_text_with_confidence(handwriting_processed, self.handwriting_config)
            handwriting_result['method'] = 'handwriting_ocr'
            results.append(handwriting_result)
            
            # Approach 3: Region-based processing
            regions = self.detect_handwriting_regions(image)
            region_texts = []
            for i, (x, y, w, h) in enumerate(regions[:5]):  # Process top 5 regions
                roi = image[y:y+h, x:x+w]
                roi_processed = self.preprocess_for_handwriting(roi)
                roi_result = self.extract_text_with_confidence(roi_processed, self.handwriting_config)
                if roi_result['text'].strip():
                    region_texts.append(roi_result['text'])
            
            # Choose the best result based on confidence and text length
            best_result = max(results, key=lambda x: (x['confidence'], len(x['text'])))
            
            # Combine all extracted text
            combined_text = []
            if best_result['text'].strip():
                combined_text.append(best_result['text'])
            
            if region_texts:
                combined_text.extend(region_texts)
            
            final_text = '\n'.join(combined_text)
            
            return {
                'text': final_text,
                'confidence': best_result['confidence'],
                'extraction_method': f"comprehensive_{best_result['method']}",
                'handwriting_regions_found': len(regions),
                'processing_approaches': len(results)
            }
            
        except Exception as e:
            logger.error(f"Comprehensive image processing failed: {e}")
            return {'error': f'Image processing failed: {str(e)}'}

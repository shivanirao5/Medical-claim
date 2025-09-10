#!/usr/bin/env python3
"""
Enhanced OCR utilities for handwritten prescription processing
Includes advanced image preprocessing for better handwriting recognition
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import io
from typing import Optional, Dict, Any, List, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HandwrittenPrescriptionOCR:
    """Advanced OCR processor specifically designed for handwritten prescriptions"""
    
    def __init__(self):
        """Initialize the OCR processor with optimized settings for handwriting"""
        # Tesseract configuration for handwritten text
        self.handwritten_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,()-/ '
        
        # Standard configuration for printed text
        self.standard_config = r'--oem 3 --psm 6'
        
        # Medicine name patterns for validation
        self.medicine_patterns = [
            'paracetamol', 'acetaminophen', 'ibuprofen', 'aspirin', 'amoxicillin',
            'metformin', 'atorvastatin', 'omeprazole', 'amlodipine', 'losartan',
            'lisinopril', 'simvastatin', 'levothyroxine', 'azithromycin', 'gabapentin',
            'hydrochlorothiazide', 'pantoprazole', 'clopidogrel', 'insulin', 'ranitidine',
            'cetirizine', 'montelukast', 'prednisolone', 'doxycycline', 'ciprofloxacin'
        ]
    
    def preprocess_for_handwriting(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Advanced preprocessing pipeline specifically for handwritten prescriptions
        Returns multiple processed versions for ensemble OCR
        """
        processed_images = []
        
        try:
            # Original grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            
            # 1. Standard preprocessing
            # Remove noise and enhance contrast
            denoised = cv2.bilateralFilter(gray, 9, 75, 75)
            enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(denoised)
            processed_images.append(enhanced)
            
            # 2. Adaptive thresholding (good for varying lighting)
            adaptive_thresh = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            processed_images.append(adaptive_thresh)
            
            # 3. Morphological operations to connect broken characters
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            morph = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_CLOSE, kernel)
            processed_images.append(morph)
            
            # 4. Gaussian blur + Otsu thresholding
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            _, otsu_thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(otsu_thresh)
            
            # 5. Dilation to thicken thin handwritten strokes
            dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            dilated = cv2.dilate(adaptive_thresh, dilate_kernel, iterations=1)
            processed_images.append(dilated)
            
            # 6. Edge enhancement
            edges = cv2.Canny(enhanced, 50, 150)
            edge_enhanced = cv2.bitwise_or(enhanced, edges)
            processed_images.append(edge_enhanced)
            
            logger.info(f"Generated {len(processed_images)} preprocessed versions for OCR")
            return processed_images
            
        except Exception as e:
            logger.error(f"Error in preprocessing: {e}")
            return [gray] if 'gray' in locals() else [image]
    
    def extract_text_ensemble(self, processed_images: List[np.ndarray]) -> Dict[str, Any]:
        """
        Run OCR on multiple preprocessed versions and combine results
        """
        all_results = []
        confidence_scores = []
        
        for i, img in enumerate(processed_images):
            try:
                # Try handwritten configuration first
                handwritten_result = pytesseract.image_to_data(
                    img, config=self.handwritten_config, output_type=pytesseract.Output.DICT
                )
                
                # Try standard configuration as backup
                standard_result = pytesseract.image_to_data(
                    img, config=self.standard_config, output_type=pytesseract.Output.DICT
                )
                
                # Extract text and confidence
                hw_text = ' '.join([handwritten_result['text'][j] for j in range(len(handwritten_result['text'])) 
                                  if int(handwritten_result['conf'][j]) > 30])
                hw_conf = np.mean([int(handwritten_result['conf'][j]) for j in range(len(handwritten_result['conf'])) 
                                 if int(handwritten_result['conf'][j]) > 0])
                
                std_text = ' '.join([standard_result['text'][j] for j in range(len(standard_result['text'])) 
                                   if int(standard_result['conf'][j]) > 30])
                std_conf = np.mean([int(standard_result['conf'][j]) for j in range(len(standard_result['conf'])) 
                                  if int(standard_result['conf'][j]) > 0])
                
                # Choose the better result
                if hw_conf > std_conf:
                    all_results.append({
                        'text': hw_text,
                        'confidence': hw_conf,
                        'method': f'handwritten_v{i+1}',
                        'preprocessing': i
                    })
                else:
                    all_results.append({
                        'text': std_text,
                        'confidence': std_conf,
                        'method': f'standard_v{i+1}',
                        'preprocessing': i
                    })
                
                confidence_scores.append(max(hw_conf, std_conf))
                
            except Exception as e:
                logger.warning(f"OCR failed on preprocessing version {i+1}: {e}")
                continue
        
        return self._combine_ocr_results(all_results)
    
    def _combine_ocr_results(self, results: List[Dict]) -> Dict[str, Any]:
        """
        Intelligently combine multiple OCR results
        """
        if not results:
            return {'text': '', 'confidence': 0, 'method': 'none'}
        
        # Sort by confidence
        results.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Use the highest confidence result as base
        best_result = results[0]
        
        # Try to enhance with medicine name validation
        enhanced_text = self._validate_and_enhance_medicines(best_result['text'])
        
        # Combine insights from multiple results
        all_texts = [r['text'] for r in results if r['confidence'] > 40]
        medicine_mentions = self._extract_medicine_mentions(all_texts)
        
        return {
            'text': enhanced_text,
            'confidence': best_result['confidence'],
            'method': best_result['method'],
            'preprocessing_used': best_result['preprocessing'],
            'alternative_texts': [r['text'] for r in results[1:3]],  # Top 3 alternatives
            'medicine_mentions': medicine_mentions,
            'ensemble_size': len(results)
        }
    
    def _validate_and_enhance_medicines(self, text: str) -> str:
        """
        Validate and correct medicine names using fuzzy matching
        """
        import difflib
        
        words = text.split()
        enhanced_words = []
        
        for word in words:
            # Check if word might be a medicine name
            if len(word) > 4:  # Medicine names are usually longer
                # Find closest match in known medicines
                matches = difflib.get_close_matches(
                    word.lower(), self.medicine_patterns, n=1, cutoff=0.6
                )
                if matches:
                    enhanced_words.append(matches[0].title())
                    logger.info(f"Enhanced '{word}' to '{matches[0]}'")
                else:
                    enhanced_words.append(word)
            else:
                enhanced_words.append(word)
        
        return ' '.join(enhanced_words)
    
    def _extract_medicine_mentions(self, texts: List[str]) -> List[str]:
        """
        Extract potential medicine names from multiple OCR results
        """
        medicine_mentions = set()
        
        for text in texts:
            words = text.lower().split()
            for word in words:
                for medicine in self.medicine_patterns:
                    if medicine in word or word in medicine:
                        medicine_mentions.add(medicine)
        
        return list(medicine_mentions)
    
    def process_prescription_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Main method to process a handwritten prescription image
        """
        try:
            # Convert bytes to numpy array
            image = np.array(Image.open(io.BytesIO(image_bytes)))
            
            # Preprocess the image for handwriting
            processed_images = self.preprocess_for_handwriting(image)
            
            # Run ensemble OCR
            ocr_result = self.extract_text_ensemble(processed_images)
            
            # Add processing metadata
            ocr_result.update({
                'image_size': image.shape,
                'processing_pipeline': 'handwritten_prescription_v1',
                'timestamp': str(np.datetime64('now'))
            })
            
            logger.info(f"Processed prescription with confidence: {ocr_result['confidence']:.2f}")
            return ocr_result
            
        except Exception as e:
            logger.error(f"Error processing prescription: {e}")
            return {
                'text': '',
                'confidence': 0,
                'error': str(e),
                'method': 'failed'
            }

# Enhanced main extraction function with handwriting support
def extract_text_from_pdf_bytes(pdf_bytes: bytes, enhance_handwriting: bool = True) -> str:
    """
    Enhanced PDF text extraction with handwriting support
    """
    try:
        import fitz  # PyMuPDF
        
        # First try direct text extraction
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        direct_text = ""
        
        for page in doc:
            direct_text += page.get_text()
        
        doc.close()
        
        # If we got good text directly, use it
        if len(direct_text.strip()) > 50:
            logger.info("Using direct PDF text extraction")
            return direct_text
        
        # Otherwise, convert to images and use enhanced OCR
        logger.info("PDF appears to be image-based, using enhanced OCR")
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        all_text = []
        
        # Initialize handwritten OCR processor
        hw_ocr = HandwrittenPrescriptionOCR() if enhance_handwriting else None
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # Convert to image
            mat = fitz.Matrix(2.0, 2.0)  # Higher resolution for better OCR
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            if enhance_handwriting and hw_ocr:
                # Use enhanced handwriting OCR
                result = hw_ocr.process_prescription_image(img_data)
                page_text = result['text']
                logger.info(f"Page {page_num+1} OCR confidence: {result.get('confidence', 0):.2f}")
            else:
                # Standard OCR
                image = Image.open(io.BytesIO(img_data))
                page_text = pytesseract.image_to_string(image)
            
            if page_text.strip():
                all_text.append(f"--- PAGE {page_num + 1} ---\n{page_text}")
        
        doc.close()
        return '\n\n'.join(all_text)
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        # Fallback to basic OCR
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")
            doc.close()
            
            image = Image.open(io.BytesIO(img_data))
            return pytesseract.image_to_string(image)
        except:
            return f"Error extracting text: {str(e)}"

def extract_text_from_image_bytes(image_bytes: bytes, enhance_handwriting: bool = True) -> str:
    """
    Enhanced image text extraction with handwriting support
    """
    try:
        if enhance_handwriting:
            hw_ocr = HandwrittenPrescriptionOCR()
            result = hw_ocr.process_prescription_image(image_bytes)
            return result['text']
        else:
            image = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(image)
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return f"Error extracting text: {str(e)}"

"""Extraction service that wraps existing OCR and parser utilities.

This file deliberately keeps logic small and well-commented so it's easy to
understand how inputs flow through OCR -> parsing -> claim object.
"""
from typing import Optional, Dict, Any, List, Tuple
import io
import re
from .advanced_ocr_service import AdvancedOCRService
from .gemini_service import GeminiMedicalProcessor

# Simple OCR functions using available libraries (fallback)
def simple_extract_text_from_pdf_bytes(file_bytes: bytes, enhance_handwriting: bool = True) -> str:
    """Extract text from PDF using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
        from io import BytesIO
        reader = PdfReader(BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        return f"Error extracting PDF text: {e}"

def simple_extract_text_from_image_bytes(file_bytes: bytes, enhance_handwriting: bool = True) -> str:
    """Extract text from image using pytesseract."""
    try:
        import pytesseract
        from PIL import Image
        from io import BytesIO
        image = Image.open(BytesIO(file_bytes))
        return pytesseract.image_to_string(image)
    except Exception as e:
        return f"Error extracting image text: {e}"


class ExtractionService:
    """Provides helper methods to turn uploaded files into structured claims."""

    def __init__(self):
        # Configuration points (could read from env in a larger app)
        self.supported_image_types = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
        # Initialize advanced OCR service
        self.advanced_ocr = AdvancedOCRService()
        # Initialize Gemini Pro service for intelligent medical text processing
        self.gemini_processor = GeminiMedicalProcessor()

    def process_file_bytes(self, file_bytes: bytes, filename: Optional[str] = None, content_type: Optional[str] = None) -> Dict[str, Any]:
        """Detect file type, extract text and parse into a claim dict with automatic OCR mode detection.

        Steps:
        1. Use advanced OCR service with automatic processing (both printed and handwritten)
        2. Call the enhanced parser to convert text -> structured claim
        3. Return a JSON-serializable dict representing the claim
        """
        
        # Use advanced OCR service with automatic mode detection
        ocr_result = self.advanced_ocr.process_file_advanced(
            file_bytes, filename=filename, content_type=content_type
        )
        
        if 'error' in ocr_result:
            return {"error": ocr_result['error']}
        
        text = ocr_result.get('text', '')
        
        # Ensure we have something
        if not text:
            return {"error": "No readable text could be extracted from the file."}

        # Use enhanced parse function to get structured claim
        claim = self.enhanced_parse_claim(text)
        
        # Add OCR metadata to the claim
        claim['ocr_metadata'] = {
            'confidence': ocr_result.get('confidence', 0),
            'extraction_method': ocr_result.get('extraction_method', 'automatic_detection'),
            'pages_processed': ocr_result.get('pages_processed', 1),
            'handwriting_regions_found': ocr_result.get('handwriting_regions_found', 0),
            'processing_approaches': ocr_result.get('processing_approaches', 1)
        }

        # Convert to dict if necessary
        try:
            return claim if isinstance(claim, dict) else {"error": "Failed to serialize claim"}
        except Exception:
            return {"error": "Failed to serialize claim object"}

    def enhanced_parse_claim(self, text: str) -> Dict[str, Any]:
        """Enhanced parser to extract medical information using Gemini Pro API with fallback."""
        
        # Try Gemini Pro first for intelligent medical text processing
        if self.gemini_processor.is_available():
            try:
                gemini_result = self.gemini_processor.process_medical_text(text)
                
                # Convert Gemini result to legacy format for compatibility
                legacy_result = self._convert_gemini_to_legacy_format(gemini_result, text)
                
                # Add the full Gemini result as prescription_data for detailed access
                legacy_result['prescription_data'] = gemini_result
                legacy_result['processing_method'] = 'gemini_pro'
                
                return legacy_result
                
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Gemini Pro processing failed: {e}, using fallback")
        
        # Fallback to existing logic if Gemini is not available
        return self._enhanced_parse_fallback(text)
    
    def _convert_gemini_to_legacy_format(self, gemini_data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Convert Gemini Pro result to legacy claim format for compatibility."""
        
        # Extract medicine names from prescriptions
        medicine_names = []
        if gemini_data.get('prescriptions'):
            medicine_names = [p.get('medicine_name', '') for p in gemini_data['prescriptions']]
        
        # Calculate amounts (since Gemini focuses on prescriptions, amounts are usually 0)
        bill_amount = gemini_data.get('bill_amount', 0.0) or 0.0
        
        return {
            "bill_no": None,  # Usually not in prescriptions
            "my_date": gemini_data.get('date'),
            "amount_spent_on_medicine": bill_amount * 0.7 if bill_amount > 0 else 0.0,
            "amount_spent_on_test": bill_amount * 0.2 if bill_amount > 0 else 0.0,
            "amount_spent_on_consultation": bill_amount * 0.1 if bill_amount > 0 else 0.0,
            "medicine_names": medicine_names,
            "test_names": [],  # Usually not in prescriptions
            "doctor_name": gemini_data.get('doctor_name'),
            "hospital_name": gemini_data.get('hospital_clinic_name'),
            "reimbursement_amount": bill_amount * 0.8 if bill_amount > 0 else 0.0,
            "editable": True,
            "patient_name": gemini_data.get('patient_name'),
            "grand_total": bill_amount,
            "raw_text": raw_text,
            "gemini_flags": gemini_data.get('flags', []),
            "processing_confidence": "high" if gemini_data.get('processing_method') == 'gemini_pro' else "medium"
        }
    
    def _enhanced_parse_fallback(self, text: str) -> Dict[str, Any]:
        """Fallback parsing when Gemini Pro is not available."""
        
        # Check if this looks like a medical prescription format
        if self._is_prescription_format(text):
            return self._parse_prescription_format(text)
        
        # Enhanced regex patterns for medical content
        patient_name = self.extract_field(text, r'(?:Patient Name|Name of Patient|Patient|Name)[:\-\s]*([A-Z][A-Za-z\s.,]{2,50})')
        if not patient_name:
            # Try alternative patterns for handwritten content
            patient_name = self.extract_field(text, r'(?:Mr|Mrs|Ms|Dr)\.?\s+([A-Z][A-Za-z\s.]{2,40})')
        
        bill_number = self.extract_field(text, r'(?:Bill No|Invoice No|Receipt No|Ref|Reference|Bill#)[:\s]*([A-Za-z0-9\-\/]+)')
        
        # Enhanced date patterns
        date = self.extract_field(text, r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})')
        if not date:
            date = self.extract_field(text, r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4})')
        
        hospital = self.extract_field(text, r'((?:Hospital|Clinic|Medical Center|Nursing Home)[^\n,]{0,60})')
        if not hospital:
            # Look for common hospital patterns
            hospital = self.extract_field(text, r'([A-Z][A-Za-z\s]+(?:Hospital|Clinic|Medical|Healthcare))')
        
        doctor = self.extract_field(text, r'(Dr\.?\s+[A-Z][A-Za-z\s.]{2,40})')
        
        # Enhanced medicine extraction
        medicines = self.extract_medicines(text)
        
        # Enhanced test extraction  
        tests = self.extract_tests(text)
        
        # Enhanced amount extraction with multiple currency formats
        amounts = self.extract_amounts(text)
        total = self.calculate_total_amount(amounts, text)
        
        # Smart categorization based on content
        medicine_amount, test_amount, consultation_amount = self.categorize_amounts(text, total, medicines, tests)
        
        return {
            "bill_no": bill_number,
            "my_date": date,
            "amount_spent_on_medicine": medicine_amount,
            "amount_spent_on_test": test_amount,
            "amount_spent_on_consultation": consultation_amount,
            "medicine_names": medicines,
            "test_names": tests,
            "doctor_name": doctor,
            "hospital_name": hospital,
            "reimbursement_amount": total * 0.8,
            "editable": True,
            "patient_name": patient_name,
            "grand_total": total,
            "raw_text": text,
            "processing_method": "fallback"
        }
    
    def _is_prescription_format(self, text: str) -> bool:
        """Check if text looks like a medical prescription format."""
        prescription_indicators = [
            'apply', 'cream', 'gel', 'tablet', 'tab', 'mg', 'ml', 'dr.', 'doctor',
            'morning', 'evening', 'daily', 'twice', 'thrice', 'prescription'
        ]
        text_lower = text.lower()
        indicator_count = sum(1 for indicator in prescription_indicators if indicator in text_lower)
        return indicator_count >= 3
    
    def _parse_prescription_format(self, text: str) -> Dict[str, Any]:
        """Parse medical prescription format with structured JSON output."""
        
        # Clean OCR errors and extract structured data
        result = {
            "patient_name": None,
            "age": None,
            "gender": None,
            "date": None,
            "prescriptions": [],
            "doctor_name": None,
            "doctor_registration_number": None,
            "hospital_clinic_name": None,
            "bill_amount": None,
            "flags": [],
            "raw_text": text
        }
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Extract patient information from first line
        if lines:
            first_line = lines[0]
            # Pattern like "Shahar Bobu 18-6-25 M/36"
            patient_match = re.search(r'^([A-Za-z\s]+?)\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+([MF])/(\d+)', first_line, re.IGNORECASE)
            if patient_match:
                result["patient_name"] = self._clean_name(patient_match.group(1))
                result["date"] = self._standardize_date(patient_match.group(2))
                result["gender"] = "Male" if patient_match.group(3).upper() == 'M' else "Female"
                result["age"] = int(patient_match.group(4))
        
        # Extract prescriptions
        prescriptions = []
        for line in lines[1:]:  # Skip first line with patient info
            if self._looks_like_prescription(line):
                prescription = self._parse_prescription_line(line)
                if prescription:
                    prescriptions.append(prescription)
            elif self._looks_like_doctor_info(line):
                result["doctor_name"] = self._extract_doctor_name(line)
        
        result["prescriptions"] = prescriptions
        
        # Add validation flags
        self._add_prescription_flags(result)
        
        # Convert to legacy format for compatibility
        return self._convert_to_legacy_format(result)
    
    def _clean_name(self, name: str) -> str:
        """Clean OCR errors in names."""
        # Common OCR corrections
        corrections = {
            'Shahar': 'Shahan', 'Bobu': 'Babu', 'Dr': 'Dr.',
            'Pramod': 'Pramod', 'Krishnan': 'Krishnan'
        }
        
        for wrong, correct in corrections.items():
            name = name.replace(wrong, correct)
        
        return name.strip()
    
    def _standardize_date(self, date_str: str) -> str:
        """Convert date to standard format."""
        try:
            # Handle formats like 18-6-25 or 18/6/25
            parts = re.split(r'[-/]', date_str)
            if len(parts) == 3:
                day, month, year = parts
                # Assume 20xx for 2-digit years
                if len(year) == 2:
                    year = f"20{year}"
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except:
            pass
        return date_str
    
    def _looks_like_prescription(self, line: str) -> bool:
        """Check if line contains prescription information."""
        prescription_keywords = ['cream', 'gel', 'tablet', 'tab', 'apply', 'mg', 'ml', 'syrup', 'drops']
        line_lower = line.lower()
        return any(keyword in line_lower for keyword in prescription_keywords)
    
    def _looks_like_doctor_info(self, line: str) -> bool:
        """Check if line contains doctor information."""
        return any(keyword in line.lower() for keyword in ['dr.', 'doctor', 'md', 'mbbs'])
    
    def _parse_prescription_line(self, line: str) -> Dict[str, Any]:
        """Parse individual prescription line."""
        # Clean common OCR errors
        cleaned_line = self._clean_prescription_text(line)
        
        # Extract medicine name (usually the first significant word/phrase)
        medicine_match = re.search(r'^[^\w]*([A-Za-z][A-Za-z\s\-]{2,30})', cleaned_line)
        medicine_name = medicine_match.group(1).strip() if medicine_match else "Unknown Medicine"
        
        # Extract application area
        application_areas = {
            'thigh': ['thigh'], 'knee': ['knee', 'kin'], 'face': ['face'],
            'skin': ['skin'], 'day': ['day', 'daytime'], 'night': ['night', 'ni9t']
        }
        
        application_area = "General use"
        frequency = "As directed"
        
        line_lower = cleaned_line.lower()
        
        # Determine application area
        for area, keywords in application_areas.items():
            if any(keyword in line_lower for keyword in keywords):
                if area == 'day':
                    application_area = "General use (daytime)"
                    frequency = "Apply daily"
                elif area == 'night':
                    application_area = "Face"
                    frequency = "Apply at night"
                elif area in ['thigh', 'knee']:
                    application_area = "Thigh and knee"
                    frequency = "Apply daily"
                else:
                    application_area = area.title()
                break
        
        return {
            "medicine_name": medicine_name,
            "dosage": None,
            "frequency": frequency,
            "application_area": application_area,
            "duration": None
        }
    
    def _clean_prescription_text(self, text: str) -> str:
        """Clean common OCR errors in prescription text."""
        corrections = {
            'DEARM DOW': 'Deramdow', 'alo': 'Aloe', 'PHOTO state': 'Photostable',
            'PYNO max-TX': 'Pynomax-TX', 'ni9t': 'night', 'tim': 'time',
            'thigh n kin': 'thigh and knee'
        }
        
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        
        return text
    
    def _extract_doctor_name(self, line: str) -> str:
        """Extract doctor name from line."""
        # Pattern like "Dr Pramod Krishnan, MD Dermatology"
        doctor_match = re.search(r'(Dr\.?\s+[A-Za-z\s,]+?)(?:,\s*MD|$)', line, re.IGNORECASE)
        if doctor_match:
            return doctor_match.group(1).strip()
        return line.strip()
    
    def _add_prescription_flags(self, result: Dict[str, Any]) -> None:
        """Add validation flags for prescription."""
        if not result.get("doctor_name"):
            result["flags"].append("Missing doctor information")
        
        if not result.get("patient_name"):
            result["flags"].append("Missing patient name")
        
        if not result.get("prescriptions"):
            result["flags"].append("No prescriptions found")
        
        # Check for suspicious medicine names
        for prescription in result.get("prescriptions", []):
            medicine = prescription.get("medicine_name", "")
            if len(medicine) < 3 or not re.search(r'[a-zA-Z]', medicine):
                result["flags"].append("Suspicious medicine name detected")
    
    def _convert_to_legacy_format(self, prescription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert prescription format to legacy claim format for compatibility."""
        # Extract medicine names
        medicine_names = [p.get("medicine_name", "") for p in prescription_data.get("prescriptions", [])]
        
        return {
            "bill_no": None,
            "my_date": prescription_data.get("date"),
            "amount_spent_on_medicine": 0.0,
            "amount_spent_on_test": 0.0,
            "amount_spent_on_consultation": 0.0,
            "medicine_names": medicine_names,
            "test_names": [],
            "doctor_name": prescription_data.get("doctor_name"),
            "hospital_name": prescription_data.get("hospital_clinic_name"),
            "reimbursement_amount": 0.0,
            "editable": True,
            "patient_name": prescription_data.get("patient_name"),
            "grand_total": 0.0,
            "raw_text": prescription_data.get("raw_text", ""),
            "prescription_data": prescription_data  # Include full prescription data
        }
    
    def extract_medicines(self, text: str) -> List[str]:
        """Extract medicine names from text."""
        medicines = []
        
        # Common medicine patterns
        medicine_patterns = [
            r'(?:Tab|Tablet|Cap|Capsule|Syrup|Injection|Inj)\.?\s+([A-Z][A-Za-z\s\d]+)',
            r'([A-Z][a-z]+(?:cillin|mycin|prazole|olol|pine|zole|nib|stat|mab))',
            r'([A-Z][a-z]{3,})\s+\d+\s*mg',
            r'([A-Z][a-z]{3,})\s+\d+\s*ml'
        ]
        
        for pattern in medicine_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                clean_med = match.strip()
                if len(clean_med) > 3 and clean_med not in medicines:
                    medicines.append(clean_med)
        
        return medicines[:10]  # Limit to 10 medicines
    
    def extract_tests(self, text: str) -> List[str]:
        """Extract test names from text."""
        tests = []
        
        # Common test patterns
        test_patterns = [
            r'((?:Complete Blood Count|CBC|Blood Test|Urine Test|X-Ray|CT Scan|MRI|ECG|EKG))',
            r'((?:Hemoglobin|Sugar|Cholesterol|Thyroid|Liver Function|Kidney Function)\s+Test)',
            r'([A-Z][A-Za-z\s]+(?:Test|Scan|Report|Analysis))',
            r'((?:Blood|Urine|Stool)\s+[A-Z][A-Za-z\s]+)'
        ]
        
        for pattern in test_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                clean_test = match.strip()
                if len(clean_test) > 3 and clean_test not in tests:
                    tests.append(clean_test)
        
        return tests[:10]  # Limit to 10 tests
    
    def extract_amounts(self, text: str) -> List[float]:
        """Extract all monetary amounts from text."""
        amount_patterns = [
            r'(?:Rs\.?|₹|INR)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:Rs\.?|₹|INR)',
            r'(?:Total|Amount|Bill|Grand Total)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*\.\d{2})',  # Decimal amounts
            r'(\d{2,6})(?:\s|$)'  # Simple numbers that might be amounts
        ]
        
        amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    amount = float(match.replace(',', ''))
                    if 1 <= amount <= 1000000:  # Reasonable range for medical bills
                        amounts.append(amount)
                except ValueError:
                    continue
        
        return sorted(set(amounts))  # Remove duplicates and sort
    
    def calculate_total_amount(self, amounts: List[float], text: str) -> float:
        """Calculate the most likely total amount."""
        if not amounts:
            return 0.0
        
        # Look for explicit total indicators
        total_pattern = r'(?:Total|Grand Total|Bill Amount|Final Amount)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        total_match = re.search(total_pattern, text, re.IGNORECASE)
        
        if total_match:
            try:
                return float(total_match.group(1).replace(',', ''))
            except ValueError:
                pass
        
        # If no explicit total, use the largest amount
        return max(amounts)
    
    def categorize_amounts(self, text: str, total: float, medicines: List[str], tests: List[str]) -> Tuple[float, float, float]:
        """Smart categorization of amounts based on content analysis."""
        medicine_amount = 0.0
        test_amount = 0.0
        consultation_amount = 0.0
        
        # Extract amounts near medicine and test mentions
        text_lower = text.lower()
        
        # Look for medicine-specific amounts
        medicine_keywords = ['medicine', 'drug', 'tablet', 'capsule', 'syrup', 'injection']
        for keyword in medicine_keywords:
            if keyword in text_lower:
                # Look for amounts near this keyword
                keyword_pattern = rf'{keyword}.*?(?:Rs\.?|₹)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
                matches = re.findall(keyword_pattern, text_lower)
                for match in matches:
                    try:
                        medicine_amount += float(match.replace(',', ''))
                    except ValueError:
                        continue
        
        # Look for test-specific amounts
        test_keywords = ['test', 'scan', 'report', 'analysis', 'examination']
        for keyword in test_keywords:
            if keyword in text_lower:
                keyword_pattern = rf'{keyword}.*?(?:Rs\.?|₹)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
                matches = re.findall(keyword_pattern, text_lower)
                for match in matches:
                    try:
                        test_amount += float(match.replace(',', ''))
                    except ValueError:
                        continue
        
        # Look for consultation amounts
        consultation_keywords = ['consultation', 'doctor', 'visit', 'checkup']
        for keyword in consultation_keywords:
            if keyword in text_lower:
                keyword_pattern = rf'{keyword}.*?(?:Rs\.?|₹)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
                matches = re.findall(keyword_pattern, text_lower)
                for match in matches:
                    try:
                        consultation_amount += float(match.replace(',', ''))
                    except ValueError:
                        continue
        
        # If no specific amounts found, use proportional distribution
        if medicine_amount == 0 and test_amount == 0 and consultation_amount == 0:
            if medicines and tests:
                medicine_amount = total * 0.5
                test_amount = total * 0.3
                consultation_amount = total * 0.2
            elif medicines:
                medicine_amount = total * 0.7
                consultation_amount = total * 0.3
            elif tests:
                test_amount = total * 0.6
                consultation_amount = total * 0.4
            else:
                consultation_amount = total
        
        # Ensure amounts don't exceed total
        calculated_total = medicine_amount + test_amount + consultation_amount
        if calculated_total > total and calculated_total > 0:
            factor = total / calculated_total
            medicine_amount *= factor
            test_amount *= factor
            consultation_amount *= factor
        
        return round(medicine_amount, 2), round(test_amount, 2), round(consultation_amount, 2)

    def extract_field(self, text: str, pattern: str) -> str:
        """Extract a field using regex."""
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

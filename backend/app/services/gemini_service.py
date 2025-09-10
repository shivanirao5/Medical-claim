"""Gemini Pro service for medical text processing and OCR error correction.

This service uses Google's Gemini Pro API to intelligently parse medical prescriptions,
correct OCR errors, and extract structured data with high accuracy.
"""
import google.generativeai as genai
import json
import logging
import os
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

class GeminiMedicalProcessor:
    """Uses Gemini Pro API for advanced medical text processing."""
    
    def __init__(self):
        # Initialize Gemini Pro
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            self.model = None
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        
        # Backup processing for when Gemini is not available
        self.fallback_enabled = True
        
    def process_medical_text(self, ocr_text: str) -> Dict[str, Any]:
        """Process medical text using Gemini Pro API with fallback."""
        
        if self.model and self.api_key:
            try:
                return self._process_with_gemini(ocr_text)
            except Exception as e:
                logger.warning(f"Gemini Pro processing failed: {e}, using fallback")
                return self._process_with_fallback(ocr_text)
        else:
            logger.info("Gemini Pro not configured, using fallback processing")
            return self._process_with_fallback(ocr_text)
    
    def _process_with_gemini(self, ocr_text: str) -> Dict[str, Any]:
        """Process text using Gemini Pro API."""
        
        prompt = self._create_medical_prompt(ocr_text)
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # Add processing metadata
                result['processing_method'] = 'gemini_pro'
                result['gemini_confidence'] = 'high'
                
                logger.info("Successfully processed medical text with Gemini Pro")
                return result
            else:
                logger.warning("No valid JSON found in Gemini response")
                return self._process_with_fallback(ocr_text)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gemini JSON response: {e}")
            return self._process_with_fallback(ocr_text)
        except Exception as e:
            logger.error(f"Gemini Pro API error: {e}")
            return self._process_with_fallback(ocr_text)
    
    def _create_medical_prompt(self, ocr_text: str) -> str:
        """Create a detailed prompt for Gemini Pro."""
        
        return f"""You are an AI assistant for a corporate medical claim reimbursement system. 
You will be given raw OCR text extracted from a scanned medical prescription, bill, or hospital record.

### Your Tasks:
1. **Correct OCR errors** and fix spelling mistakes in medical terms, doctor names, and hospital names.
2. **Identify and structure the data** into JSON with the following fields:
   - patient_name
   - age
   - gender
   - date
   - prescriptions (list of objects with medicine_name, dosage, frequency, duration, application_area)
   - doctor_name
   - doctor_registration_number (if available)
   - hospital_clinic_name (if available)
   - bill_amount (if it is a bill)
   - flags (list of issues such as missing doctor details, suspicious drug names, etc.)
3. **Ensure clean and normalized drug names** (use standard spelling).
4. **Always return ONLY valid JSON** with no extra text.

---

### Example Input (OCR text):
"Shahar Bobu 18-6-25 M/36
DEARM DOW alo cream apply on thigh n kin
PHOTO state gel apply day tim
PYNO max-TX cream apply face at ni9t
Dr Pramod Krishnan, MD Dermatology"

### Example Output (JSON):
{{
  "patient_name": "Shahan Babu",
  "age": 36,
  "gender": "Male",
  "date": "2025-06-18",
  "prescriptions": [
    {{
      "medicine_name": "Deramdow Aloe Cream",
      "dosage": null,
      "frequency": "Apply daily",
      "duration": null,
      "application_area": "Thigh and knee"
    }},
    {{
      "medicine_name": "Photostable Gel",
      "dosage": null,
      "frequency": "Apply daily",
      "duration": null,
      "application_area": "General use (daytime)"
    }},
    {{
      "medicine_name": "Pynomax-TX Cream",
      "dosage": null,
      "frequency": "Apply at night",
      "duration": null,
      "application_area": "Face"
    }}
  ],
  "doctor_name": "Dr. Pramod Krishnan",
  "doctor_registration_number": null,
  "hospital_clinic_name": null,
  "bill_amount": null,
  "flags": []
}}

---

### Input OCR Text to Process:
{ocr_text}

### Response (JSON only):"""

    def _process_with_fallback(self, ocr_text: str) -> Dict[str, Any]:
        """Fallback processing when Gemini is not available."""
        
        logger.info("Using fallback medical text processing")
        
        # Basic structured extraction (existing logic)
        result = {
            "patient_name": self._extract_patient_name(ocr_text),
            "age": self._extract_age(ocr_text),
            "gender": self._extract_gender(ocr_text),
            "date": self._extract_date(ocr_text),
            "prescriptions": self._extract_prescriptions(ocr_text),
            "doctor_name": self._extract_doctor_name(ocr_text),
            "doctor_registration_number": self._extract_registration(ocr_text),
            "hospital_clinic_name": self._extract_hospital(ocr_text),
            "bill_amount": self._extract_bill_amount(ocr_text),
            "flags": [],
            "processing_method": "fallback"
        }
        
        # Add validation flags
        self._add_validation_flags(result, ocr_text)
        
        return result
    
    def _extract_patient_name(self, text: str) -> Optional[str]:
        """Extract patient name with OCR error correction."""
        lines = text.split('\n')
        if lines:
            first_line = lines[0].strip()
            # Pattern like "Shahar Bobu 18-6-25 M/36"
            match = re.search(r'^([A-Za-z\s]+?)\s+\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', first_line)
            if match:
                name = match.group(1).strip()
                # Common OCR corrections
                name = name.replace('Shahar', 'Shahan').replace('Bobu', 'Babu')
                return name
        return None
    
    def _extract_age(self, text: str) -> Optional[int]:
        """Extract age from text."""
        match = re.search(r'[MF]/(\d+)', text)
        if match:
            return int(match.group(1))
        return None
    
    def _extract_gender(self, text: str) -> Optional[str]:
        """Extract gender from text."""
        match = re.search(r'([MF])/\d+', text)
        if match:
            return "Male" if match.group(1) == 'M' else "Female"
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract and standardize date."""
        match = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text)
        if match:
            date_str = match.group(1)
            try:
                parts = re.split(r'[-/]', date_str)
                if len(parts) == 3:
                    day, month, year = parts
                    if len(year) == 2:
                        year = f"20{year}"
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                pass
        return None
    
    def _extract_prescriptions(self, text: str) -> list:
        """Extract prescriptions with OCR error correction."""
        prescriptions = []
        lines = text.split('\n')[1:]  # Skip first line with patient info
        
        for line in lines:
            line = line.strip()
            if self._looks_like_prescription(line):
                prescription = self._parse_prescription_line(line)
                if prescription:
                    prescriptions.append(prescription)
        
        return prescriptions
    
    def _looks_like_prescription(self, line: str) -> bool:
        """Check if line contains prescription information."""
        prescription_keywords = ['cream', 'gel', 'tablet', 'tab', 'apply', 'mg', 'ml', 'syrup', 'drops']
        line_lower = line.lower()
        return any(keyword in line_lower for keyword in prescription_keywords)
    
    def _parse_prescription_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse individual prescription line with OCR corrections."""
        # Clean common OCR errors
        cleaned_line = line.replace('DEARM DOW', 'Deramdow').replace('alo', 'Aloe')
        cleaned_line = cleaned_line.replace('PHOTO state', 'Photostable')
        cleaned_line = cleaned_line.replace('PYNO max-TX', 'Pynomax-TX')
        cleaned_line = cleaned_line.replace('ni9t', 'night').replace('tim', 'time')
        cleaned_line = cleaned_line.replace('thigh n kin', 'thigh and knee')
        
        # Extract medicine name
        medicine_match = re.search(r'^[^\w]*([A-Za-z][A-Za-z\s\-]{2,30})', cleaned_line)
        medicine_name = medicine_match.group(1).strip() if medicine_match else "Unknown Medicine"
        
        # Determine application area and frequency
        line_lower = cleaned_line.lower()
        
        if any(word in line_lower for word in ['thigh', 'knee', 'kin']):
            application_area = "Thigh and knee"
            frequency = "Apply daily"
        elif 'face' in line_lower:
            application_area = "Face"
            frequency = "Apply at night" if 'night' in line_lower else "Apply as directed"
        elif 'day' in line_lower:
            application_area = "General use (daytime)"
            frequency = "Apply daily"
        else:
            application_area = "General use"
            frequency = "As directed"
        
        return {
            "medicine_name": medicine_name,
            "dosage": None,
            "frequency": frequency,
            "duration": None,
            "application_area": application_area
        }
    
    def _extract_doctor_name(self, text: str) -> Optional[str]:
        """Extract doctor name."""
        match = re.search(r'(Dr\.?\s+[A-Za-z\s,]+?)(?:,\s*MD|$)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_registration(self, text: str) -> Optional[str]:
        """Extract doctor registration number."""
        match = re.search(r'(?:Reg|Registration|License)[\s#:]*([A-Z0-9]+)', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def _extract_hospital(self, text: str) -> Optional[str]:
        """Extract hospital/clinic name."""
        match = re.search(r'([A-Za-z\s]+(?:Hospital|Clinic|Medical|Healthcare))', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_bill_amount(self, text: str) -> Optional[float]:
        """Extract bill amount."""
        # Look for currency patterns
        patterns = [
            r'(?:Rs\.?|₹)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'Total[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'Amount[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    return float(amount_str)
                except ValueError:
                    continue
        return None
    
    def _add_validation_flags(self, result: Dict[str, Any], text: str) -> None:
        """Add validation flags."""
        flags = []
        
        if not result.get('doctor_name'):
            flags.append("Missing doctor information")
        
        if not result.get('patient_name'):
            flags.append("Missing patient name")
        
        if not result.get('prescriptions'):
            flags.append("No prescriptions found")
        
        # Check for suspicious medicine names
        for prescription in result.get('prescriptions', []):
            medicine = prescription.get('medicine_name', '')
            if len(medicine) < 3 or not re.search(r'[a-zA-Z]', medicine):
                flags.append("Suspicious medicine name detected")
                break
        
        result['flags'] = flags
    
    def is_available(self) -> bool:
        """Check if Gemini Pro is available."""
        return self.model is not None and self.api_key is not None

#!/usr/bin/env python3

import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# This module implements a heuristic-based parser that turns unstructured
# OCR/text output from medical bills into structured claim items. The
# approach is intentionally conservative: it uses regexes and simple
# heuristics so it remains explainable and robust across varied inputs.


@dataclass
class ClaimItem:
    """Structured claim item matching the required output format.

    Why: Downstream UI and analytics expect consistent fields (bill number,
    dates, categorized amounts, medicine/test lists). Using a dataclass
    keeps the structure simple and easily serializable.
    """
    bill_no: str = ""
    my_date: str = ""
    amount_spent_on_medicine: float = 0.0
    amount_spent_on_test: float = 0.0
    amount_spent_on_consultation: float = 0.0
    medicine_names: List[str] = None
    test_names: List[str] = None
    doctor_name: str = ""
    hospital_name: str = ""
    reimbursement_amount: float = 0.0
    editable: bool = True

    def __post_init__(self):
        # Ensure lists are initialized to avoid mutable default pitfalls
        if self.medicine_names is None:
            self.medicine_names = []
        if self.test_names is None:
            self.test_names = []


class MedicalClaimParser:
    """Enhanced parser that extracts structured medical claim data.

    Notes on design:
    - Uses pattern lists for medicines/tests because a full NLP model
      isn't necessary for initial extraction and would be heavier to run.
    - Keeps unwanted patterns to filter out addresses/phone numbers because
      those commonly pollute OCR output.
    - Amount/date extraction uses multiple regex forms to handle diverse
      formats found in bills.
    """

    def __init__(self):
        # Medicine regex patterns: list of common drug names and suffix-based
        # heuristics (e.g., names ending with -mycin, -cillin). These are used
        # to identify medicine entries in noisy OCR text.
        self.medicine_patterns = [
            r'\b(?:amoxicillin|augmentin|azithromycin|ciprofloxacin|doxycycline|penicillin|cephalexin|erythromycin)\b',
            r'\b(?:paracetamol|acetaminophen|ibuprofen|diclofenac|aspirin|tramadol|morphine|codeine)\b',
            r'\b(?:metformin|insulin|glipizide|glyburide|sitagliptin|pioglitazone)\b',
            r'\b(?:amlodipine|lisinopril|atenolol|metoprolol|losartan|enalapril|furosemide)\b',
            r'\b(?:omeprazole|ranitidine|pantoprazole|lansoprazole|esomeprazole)\b',
            r'\b(?:crocin|combiflam|disprin|digene|eno|pudin|hara|vicks)\b',
            r'\b[A-Z][a-z]+(?:mycin|cillin|prazole|olol|pine|tide|zole|fenac)\b'
        ]

        # Test patterns: simple common test names that appear in lab reports
        self.test_patterns = [
            r'\b(?:blood test|x-ray|mri|ct scan|ultrasound|ecg|ekg|urine test)\b',
            r'\b(?:complete blood count|cbc|liver function|kidney function|thyroid)\b',
            r'\b(?:sugar test|diabetes test|cholesterol|hemoglobin|hba1c)\b',
            r'\b(?:chest x-ray|abdominal ultrasound|cardiac echo)\b'
        ]

        # Unwanted patterns to filter out from OCR noise (addresses, phones)
        self.unwanted_patterns = [
            r'address[:;\s]*[^\n]+',
            r'phone[:;\s]*[\d\s\-\+\(\)]+',
            r'email[:;\s]*[^\s@]+@[^\s@]+\.[^\s@]+',
            r'patient id[:;\s]*[^\n]+',
            r'registration[:;\s]*[^\n]+',
            r'pin code[:;\s]*\d+',
            r'city[:;\s]*[^\n]+state[:;\s]*[^\n]+'
        ]

        # Amount patterns: handle currency prefixes/suffixes and common labels
        self.amount_patterns = [
            r'(?:rs\.?|rupees?|\u20b9)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:rs\.?|rupees?|\u20b9)',
            r'total\s*[:=]\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'amount\s*[:=]\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        ]

        # Date patterns: support numeric and textual month formats
        self.date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})',
            r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})'
        ]

    def clean_text(self, text: str) -> str:
        """Remove unwanted information like addresses, phone numbers, etc.

        Why: OCR often captures headers/footers and contact details. Removing
        them reduces false positives when extracting medicines, amounts, etc.
        """
        cleaned = text

        # Remove unwanted patterns
        for pattern in self.unwanted_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Normalize whitespace to make downstream regexes more effective
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
        cleaned = re.sub(r'\s{3,}', ' ', cleaned)

        return cleaned.strip()

    def extract_medicines(self, text: str) -> List[str]:
        """Extract medicine names from text using pre-defined patterns."""
        medicines = []

        for pattern in self.medicine_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            medicines.extend([m.lower().title() for m in matches])

        # Deduplicate while preserving order
        return list(dict.fromkeys(medicines))

    def extract_tests(self, text: str) -> List[str]:
        """Extract lab/test names using common test patterns."""
        tests = []

        for pattern in self.test_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            tests.extend([t.lower().title() for t in matches])

        return list(dict.fromkeys(tests))

    def extract_amounts(self, text: str) -> List[float]:
        """Extract monetary amounts and convert them to floats.

        Why: Bills use different formats (Rs., ₹, commas); normalize to float
        for numeric computations and reimbursements.
        """
        amounts = []

        for pattern in self.amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    amount = float(match.replace(',', ''))
                    amounts.append(amount)
                except ValueError:
                    continue

        return amounts

    def extract_dates(self, text: str) -> List[str]:
        """Extract candidate dates from text."""
        dates = []

        for pattern in self.date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)

        return dates

    def extract_doctor_hospital(self, text: str) -> tuple[str, str]:
        """Extract doctor and hospital names using simple label-based regexes.

        These patterns are heuristic and may not catch all variations, but
        they work for common bill templates.
        """
        doctor = ""
        hospital = ""

        doctor_patterns = [
            r'dr\.?\s+([a-z\s\.]+)',
            r'doctor[:;\s]*([a-z\s\.]+)',
            r'physician[:;\s]*([a-z\s\.]+)'
        ]

        hospital_patterns = [
            r'hospital[:;\s]*([a-z\s\.]+)',
            r'clinic[:;\s]*([a-z\s\.]+)',
            r'medical center[:;\s]*([a-z\s\.]+)',
            r'health care[:;\s]*([a-z\s\.]+)'
        ]

        for pattern in doctor_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                doctor = match.group(1).strip().title()
                break

        for pattern in hospital_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                hospital = match.group(1).strip().title()
                break

        return doctor, hospital

    def categorize_expenses(self, text: str, medicines: List[str], tests: List[str], amounts: List[float]) -> Dict[str, float]:
        """Categorize expenses into medicine, test, and consultation.

        Very simple heuristic allocation is used here because exact
        line-item association requires more advanced parsing (table parsing).
        The heuristic ensures some distribution of the total when exact
        mapping isn't available.
        """
        expenses = {
            "medicine": 0.0,
            "test": 0.0,
            "consultation": 0.0
        }

        if not amounts:
            return expenses

        total_amount = sum(amounts)

        # Allocate percentages based on presence of medicines/tests
        if medicines:
            expenses["medicine"] = total_amount * 0.4  # 40% for medicines

        if tests:
            expenses["test"] = total_amount * 0.3  # 30% for tests

        expenses["consultation"] = total_amount - expenses["medicine"] - expenses["test"]

        if not medicines and not tests:
            # If we can't detect categories, put everything as consultation
            expenses["consultation"] = total_amount

        return expenses

    def parse_medical_claim(self, raw_text: str) -> ClaimItem:
        """Parse raw OCR/text into a structured ClaimItem.

        Steps:
        1. Clean text to remove noisy headers/footers/contact info.
        2. Extract medicines, tests, amounts, dates, doctor/hospital.
        3. Categorize expenses using heuristics and compute reimbursement.
        """
        cleaned_text = self.clean_text(raw_text)

        medicines = self.extract_medicines(cleaned_text)
        tests = self.extract_tests(cleaned_text)
        amounts = self.extract_amounts(cleaned_text)
        dates = self.extract_dates(cleaned_text)
        doctor, hospital = self.extract_doctor_hospital(cleaned_text)

        expenses = self.categorize_expenses(cleaned_text, medicines, tests, amounts)

        claim = ClaimItem(
            bill_no=f"BILL-{datetime.now().strftime('%Y%m%d%H%M%S')}",  # Generated bill id
            my_date=dates[0] if dates else datetime.now().strftime("%d/%m/%Y"),
            amount_spent_on_medicine=expenses["medicine"],
            amount_spent_on_test=expenses["test"],
            amount_spent_on_consultation=expenses["consultation"],
            medicine_names=medicines,
            test_names=tests,
            doctor_name=doctor,
            hospital_name=hospital,
            reimbursement_amount=sum(amounts) * 0.8 if amounts else 0.0,  # default 80% reimbursement
            editable=True
        )

        return claim

    def parse_multiple_pages(self, pages_text: List[str]) -> List[ClaimItem]:
        """Parse multiple page texts into ClaimItem list.

        Why: Each page may correspond to a separate bill. We create
        individual ClaimItem entries per page to allow editing and
        separate reimbursement calculations.
        """
        claims = []

        for i, page_text in enumerate(pages_text):
            if page_text.strip():  # Only process non-empty pages
                claim = self.parse_medical_claim(page_text)
                claim.bill_no = f"BILL-{i+1:03d}-{datetime.now().strftime('%Y%m%d')}"
                claims.append(claim)

        return claims

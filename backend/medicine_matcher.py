from typing import List, Dict, Set
import re
from difflib import SequenceMatcher

class MedicineMatchingService:
    """Service for matching medicine names across bills and prescriptions"""
    
    def __init__(self):
        self.medicine_database = [
            # Common generic names
            'paracetamol', 'acetaminophen', 'ibuprofen', 'aspirin', 'amoxicillin',
            'metformin', 'atorvastatin', 'omeprazole', 'amlodipine', 'losartan',
            'lisinopril', 'simvastatin', 'levothyroxine', 'azithromycin', 'gabapentin',
            'hydrochlorothiazide', 'pantoprazole', 'clopidogrel', 'insulin', 'ranitidine',
            'cetirizine', 'montelukast', 'prednisolone', 'doxycycline', 'ciprofloxacin',
            
            # Common brand names (Indian market)
            'crocin', 'dolo', 'combiflam', 'disprin', 'augmentin', 'azithral',
            'glycomet', 'lipitor', 'omez', 'norvasc', 'cozaar', 'prinivil',
            'zocor', 'synthroid', 'neurontin', 'microzide', 'protonix',
            'plavix', 'novolin', 'zantac', 'zyrtec', 'singulair', 'deltasone',
            'vibramycin', 'cipro',
        ]
        
        # Medicine form indicators
        self.medicine_forms = [
            'tablet', 'tab', 'capsule', 'cap', 'syrup', 'syp', 'injection', 'inj',
            'drops', 'cream', 'ointment', 'gel', 'lotion', 'spray', 'inhaler'
        ]
        
        # Dosage patterns
        self.dosage_patterns = [
            r'\d+\s*mg', r'\d+\s*ml', r'\d+\s*mcg', r'\d+\s*g',
            r'\d+\s*iu', r'\d+\s*units'
        ]
    
    def extract_medicine_names(self, text: str) -> List[Dict[str, str]]:
        """Extract medicine names from text with confidence scores"""
        medicines = []
        lines = text.lower().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for medicine indicators
            has_medicine_form = any(form in line for form in self.medicine_forms)
            has_known_medicine = any(med in line for med in self.medicine_database)
            has_dosage = any(re.search(pattern, line) for pattern in self.dosage_patterns)
            
            if has_medicine_form or has_known_medicine or has_dosage:
                # Extract the medicine name
                medicine_name = self._clean_medicine_name(line)
                if medicine_name:
                    confidence = self._calculate_confidence(line, has_medicine_form, has_known_medicine, has_dosage)
                    medicines.append({
                        'name': medicine_name,
                        'original_text': line,
                        'confidence': confidence
                    })
        
        return medicines
    
    def _clean_medicine_name(self, text: str) -> str:
        """Clean and extract the actual medicine name from a line"""
        # Remove price patterns
        text = re.sub(r'(?:rs\.?|₹|inr)?\s*\d+(?:,\d+)*(?:\.\d+)?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d+\.00', '', text)
        text = re.sub(r'\d+\s*/-', '', text)
        
        # Remove quantity patterns
        text = re.sub(r'\b\d+\s*(?:strips?|boxes?|bottles?|pcs?|pieces?)\b', '', text)
        
        # Clean up
        text = re.sub(r'[^\w\s.-]', ' ', text)
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _calculate_confidence(self, text: str, has_form: bool, has_known: bool, has_dosage: bool) -> float:
        """Calculate confidence score for medicine identification"""
        score = 0.0
        
        if has_known:
            score += 0.5
        if has_form:
            score += 0.3
        if has_dosage:
            score += 0.2
            
        # Bonus for multiple indicators
        indicators = sum([has_form, has_known, has_dosage])
        if indicators >= 2:
            score += 0.1
            
        return min(score, 1.0)
    
    def match_medicines_across_documents(self, doc1_medicines: List[Dict], doc2_medicines: List[Dict]) -> List[Dict]:
        """Find matching medicines between two documents"""
        matches = []
        
        for med1 in doc1_medicines:
            for med2 in doc2_medicines:
                similarity = self._calculate_similarity(med1['name'], med2['name'])
                if similarity > 0.7:  # Threshold for considering a match
                    matches.append({
                        'medicine1': med1,
                        'medicine2': med2,
                        'similarity': similarity,
                        'match_type': 'exact' if similarity > 0.9 else 'similar'
                    })
        
        return matches
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two medicine names"""
        # Direct string similarity
        direct_sim = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
        
        # Check for common words
        words1 = set(name1.lower().split())
        words2 = set(name2.lower().split())
        
        if words1 and words2:
            word_overlap = len(words1.intersection(words2)) / max(len(words1), len(words2))
        else:
            word_overlap = 0
        
        # Combined score
        return max(direct_sim, word_overlap)
    
    def find_price_discrepancies(self, bill_medicines: List[Dict], prescription_medicines: List[Dict]) -> List[Dict]:
        """Find medicines that appear in prescription but not in bill or with different prices"""
        discrepancies = []
        
        # Extract medicine names from both lists
        bill_names = {med['name'].lower() for med in bill_medicines}
        prescription_names = {med['name'].lower() for med in prescription_medicines}
        
        # Find medicines in prescription but not in bill
        missing_in_bill = prescription_names - bill_names
        
        for missing in missing_in_bill:
            discrepancies.append({
                'type': 'missing_from_bill',
                'medicine': missing,
                'issue': 'Medicine prescribed but not found in bill'
            })
        
        return discrepancies

# Example usage
def analyze_medicine_compliance(bill_text: str, prescription_text: str) -> Dict:
    """Analyze compliance between prescription and bill"""
    service = MedicineMatchingService()
    
    bill_medicines = service.extract_medicine_names(bill_text)
    prescription_medicines = service.extract_medicine_names(prescription_text)
    
    matches = service.match_medicines_across_documents(bill_medicines, prescription_medicines)
    discrepancies = service.find_price_discrepancies(bill_medicines, prescription_medicines)
    
    return {
        'bill_medicines': bill_medicines,
        'prescription_medicines': prescription_medicines,
        'matches': matches,
        'discrepancies': discrepancies,
        'compliance_score': len(matches) / max(len(prescription_medicines), 1)
    }

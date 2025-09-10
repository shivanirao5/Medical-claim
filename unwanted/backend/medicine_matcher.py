from typing import List, Dict, Set, Tuple, Optional
import re
from difflib import SequenceMatcher
import json

class MedicineMatchingService:
    """Enhanced service for matching medicine names and determining admissibility"""
    
    def __init__(self):
        # Comprehensive medicine database with categories
        self.medicine_database = {
            "antibiotics": [
                'amoxicillin', 'augmentin', 'azithromycin', 'ciprofloxacin', 'doxycycline',
                'penicillin', 'cephalexin', 'erythromycin', 'levofloxacin', 'metronidazole',
                'clindamycin', 'ampicillin', 'tetracycline', 'norfloxacin', 'ofloxacin'
            ],
            "painkillers": [
                'paracetamol', 'acetaminophen', 'ibuprofen', 'aspirin', 'diclofenac',
                'naproxen', 'tramadol', 'morphine', 'codeine', 'ketorolac', 'indomethacin'
            ],
            "diabetes": [
                'metformin', 'insulin', 'glipizide', 'glyburide', 'sitagliptin',
                'pioglitazone', 'glimepiride', 'acarbose', 'repaglinide', 'januvia'
            ],
            "cardiovascular": [
                'amlodipine', 'lisinopril', 'atenolol', 'metoprolol', 'losartan',
                'enalapril', 'furosemide', 'hydrochlorothiazide', 'ramipril', 'bisoprolol',
                'valsartan', 'carvedilol', 'propranolol', 'diltiazem', 'verapamil'
            ],
            "gastrointestinal": [
                'omeprazole', 'ranitidine', 'pantoprazole', 'lansoprazole', 'esomeprazole',
                'famotidine', 'domperidone', 'ondansetron', 'metoclopramide', 'sucralfate'
            ],
            "respiratory": [
                'salbutamol', 'budesonide', 'montelukast', 'cetirizine', 'loratadine',
                'fexofenadine', 'theophylline', 'ipratropium', 'formoterol', 'tiotropium'
            ],
            "vitamins_supplements": [
                'vitamin a', 'vitamin b', 'vitamin c', 'vitamin d', 'vitamin e',
                'calcium', 'iron', 'folic acid', 'zinc', 'magnesium', 'omega 3'
            ],
            "psychiatric": [
                'alprazolam', 'diazepam', 'lorazepam', 'sertraline', 'fluoxetine',
                'escitalopram', 'paroxetine', 'venlafaxine', 'duloxetine', 'mirtazapine'
            ],
            "thyroid": [
                'levothyroxine', 'synthroid', 'carbimazole', 'methimazole', 'propylthiouracil'
            ],
            "cholesterol": [
                'atorvastatin', 'simvastatin', 'rosuvastatin', 'pravastatin', 'lovastatin'
            ]
        }
        
        # Brand name to generic mapping (Indian market focus)
        self.brand_to_generic = {
            'crocin': 'paracetamol',
            'dolo': 'paracetamol',
            'metacin': 'paracetamol',
            'combiflam': 'ibuprofen+paracetamol',
            'brufen': 'ibuprofen',
            'disprin': 'aspirin',
            'ecosprin': 'aspirin',
            'augmentin': 'amoxicillin+clavulanic acid',
            'azithral': 'azithromycin',
            'glycomet': 'metformin',
            'glucophage': 'metformin',
            'lipitor': 'atorvastatin',
            'crestor': 'rosuvastatin',
            'omez': 'omeprazole',
            'pan': 'pantoprazole',
            'norvasc': 'amlodipine',
            'tenormin': 'atenolol',
            'lopressor': 'metoprolol',
            'cozaar': 'losartan',
            'vasotec': 'enalapril',
            'lasix': 'furosemide',
            'microzide': 'hydrochlorothiazide',
            'zocor': 'simvastatin',
            'synthroid': 'levothyroxine',
            'zithromax': 'azithromycin',
            'neurontin': 'gabapentin',
            'prilosec': 'omeprazole',
            'nexium': 'esomeprazole',
            'plavix': 'clopidogrel',
            'singulair': 'montelukast',
            'zyrtec': 'cetirizine',
            'allegra': 'fexofenadine',
            'claritin': 'loratadine'
        }
        
        # Medicine form indicators
        self.medicine_forms = [
            'tablet', 'tab', 'capsule', 'cap', 'syrup', 'syp', 'injection', 'inj',
            'drops', 'cream', 'ointment', 'gel', 'lotion', 'spray', 'inhaler',
            'suspension', 'solution', 'powder', 'sachet', 'patch'
        ]
        
        # Dosage patterns
        self.dosage_patterns = [
            r'\d+\s*mg', r'\d+\s*ml', r'\d+\s*mcg', r'\d+\s*g',
            r'\d+\s*iu', r'\d+\s*units', r'\d+\s*gm', r'\d+\s*cc'
        ]
        
        # Create a flat list of all known medicines for quick lookup
        self.all_medicines = set()
        for category_medicines in self.medicine_database.values():
            self.all_medicines.update(category_medicines)
        self.all_medicines.update(self.brand_to_generic.keys())
    
    def extract_medicine_names(self, text: str) -> List[Dict[str, str]]:
        """Extract medicine names from text with enhanced accuracy"""
        medicines = []
        seen_medicines = set()  # Avoid duplicates
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Clean line for processing
            clean_line = self._clean_text_for_extraction(line)
            
            # Look for medicine indicators
            has_medicine_form = self._has_medicine_form(clean_line)
            known_medicine = self._find_known_medicine(clean_line)
            has_dosage = self._has_dosage(clean_line)
            
            # Calculate confidence based on multiple factors
            confidence = 0.0
            reasons = []
            
            if known_medicine:
                confidence += 0.5
                reasons.append("known medicine")
            
            if has_medicine_form:
                confidence += 0.3
                reasons.append("has form indicator")
            
            if has_dosage:
                confidence += 0.2
                reasons.append("has dosage")
            
            # Extract if confidence is sufficient
            if confidence >= 0.3:
                medicine_name = known_medicine if known_medicine else self._extract_medicine_name(clean_line)
                
                if medicine_name and medicine_name.lower() not in seen_medicines:
                    seen_medicines.add(medicine_name.lower())
                    
                    # Check if it's a brand name and get generic
                    generic_name = self.brand_to_generic.get(medicine_name.lower())
                    
                    medicines.append({
                        'name': medicine_name,
                        'generic_name': generic_name if generic_name else medicine_name,
                        'original_text': line,
                        'confidence': min(confidence, 1.0),
                        'extraction_reasons': ', '.join(reasons),
                        'has_dosage': has_dosage,
                        'has_form': has_medicine_form
                    })
        
        return medicines
    
    def _clean_text_for_extraction(self, text: str) -> str:
        """Clean text for medicine extraction"""
        # Remove common non-medicine elements
        text = re.sub(r'(?:rs\.?|₹|inr)?\s*\d+(?:,\d+)*(?:\.\d+)?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d+\s*(?:strips?|boxes?|bottles?|pcs?|pieces?|nos?|quantity)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'[^\w\s\.\-\+]', ' ', text)
        text = ' '.join(text.split())
        return text.lower()
    
    def _has_medicine_form(self, text: str) -> bool:
        """Check if text contains medicine form indicators"""
        text_lower = text.lower()
        return any(form in text_lower for form in self.medicine_forms)
    
    def _find_known_medicine(self, text: str) -> Optional[str]:
        """Find known medicine in text"""
        text_lower = text.lower()
        
        # Check for exact matches first
        for medicine in self.all_medicines:
            if medicine in text_lower:
                return medicine.title()
        
        # Check for brand names
        for brand, generic in self.brand_to_generic.items():
            if brand in text_lower:
                return brand.title()
        
        return None
    
    def _has_dosage(self, text: str) -> bool:
        """Check if text contains dosage information"""
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.dosage_patterns)
    
    def _extract_medicine_name(self, text: str) -> str:
        """Extract medicine name from text line"""
        # Remove form indicators and dosages to isolate medicine name
        for form in self.medicine_forms:
            text = re.sub(f'\\b{form}\\b', '', text, flags=re.IGNORECASE)
        
        for pattern in self.dosage_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Clean up and return
        text = ' '.join(text.split())
        return text.strip().title() if text.strip() else ''
    
    def match_medicines_across_documents(
        self,
        bill_medicines: List[Dict],
        prescription_medicines: List[Dict]
    ) -> Dict[str, Any]:
        """
        Enhanced matching with admissibility determination
        Returns detailed comparison with admissible and non-admissible lists
        """
        matches = []
        admissible = []
        non_admissible = []
        unmatched_bill = []
        unmatched_prescription = []
        
        # Track which prescription medicines have been matched
        matched_prescription_indices = set()
        
        for bill_med in bill_medicines:
            bill_name = bill_med.get('generic_name', bill_med['name']).lower()
            best_match = None
            best_similarity = 0
            best_index = -1
            
            # Try to match with prescription medicines
            for idx, presc_med in enumerate(prescription_medicines):
                presc_name = presc_med.get('generic_name', presc_med['name']).lower()
                
                # Calculate similarity
                similarity = self._calculate_enhanced_similarity(bill_name, presc_name)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = presc_med
                    best_index = idx
            
            # Determine if match is sufficient for admissibility
            if best_similarity >= 0.8:  # High confidence match
                matched_prescription_indices.add(best_index)
                match_info = {
                    'bill_medicine': bill_med,
                    'prescription_medicine': best_match,
                    'similarity': best_similarity,
                    'match_type': 'exact' if best_similarity > 0.95 else 'high_confidence',
                    'is_admissible': True,
                    'reason': 'Matched with prescription'
                }
                matches.append(match_info)
                admissible.append(bill_med)
                
            elif best_similarity >= 0.6:  # Moderate confidence - needs review
                matched_prescription_indices.add(best_index)
                match_info = {
                    'bill_medicine': bill_med,
                    'prescription_medicine': best_match,
                    'similarity': best_similarity,
                    'match_type': 'moderate_confidence',
                    'is_admissible': True,  # Give benefit of doubt
                    'reason': 'Fuzzy match with prescription (review recommended)'
                }
                matches.append(match_info)
                admissible.append(bill_med)
                
            else:  # No good match found
                # Check if it's an OTC medicine that might be admissible
                if self._is_common_otc(bill_med['name']):
                    match_info = {
                        'bill_medicine': bill_med,
                        'prescription_medicine': None,
                        'similarity': 0,
                        'match_type': 'otc',
                        'is_admissible': True,  # OTC medicines may be admissible based on policy
                        'reason': 'Common OTC medicine'
                    }
                    admissible.append(bill_med)
                else:
                    match_info = {
                        'bill_medicine': bill_med,
                        'prescription_medicine': None,
                        'similarity': best_similarity,
                        'match_type': 'no_match',
                        'is_admissible': False,
                        'reason': 'Not found in prescription'
                    }
                    non_admissible.append(bill_med)
                    unmatched_bill.append(bill_med)
                
                matches.append(match_info)
        
        # Find prescription medicines that weren't matched (patient didn't buy)
        for idx, presc_med in enumerate(prescription_medicines):
            if idx not in matched_prescription_indices:
                unmatched_prescription.append(presc_med)
        
        # Calculate compliance metrics
        total_bill_items = len(bill_medicines) if bill_medicines else 1
        admissible_count = len(admissible)
        compliance_percentage = (admissible_count / total_bill_items) * 100
        
        return {
            'matches': matches,
            'admissible_medicines': admissible,
            'non_admissible_medicines': non_admissible,
            'unmatched_in_bill': unmatched_bill,
            'prescribed_but_not_purchased': unmatched_prescription,
            'statistics': {
                'total_bill_medicines': len(bill_medicines),
                'total_prescribed_medicines': len(prescription_medicines),
                'admissible_count': admissible_count,
                'non_admissible_count': len(non_admissible),
                'compliance_percentage': compliance_percentage,
                'medicines_not_purchased': len(unmatched_prescription)
            }
        }
    
    def _calculate_enhanced_similarity(self, name1: str, name2: str) -> float:
        """Enhanced similarity calculation considering medical naming conventions"""
        # Direct string similarity
        direct_sim = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
        
        # Check for common medicine name patterns
        # Sometimes medicines have salt combinations like "paracetamol+caffeine"
        parts1 = set(re.split(r'[+\s,]', name1.lower()))
        parts2 = set(re.split(r'[+\s,]', name2.lower()))
        
        # Calculate Jaccard similarity for parts
        intersection = parts1.intersection(parts2)
        union = parts1.union(parts2)
        jaccard_sim = len(intersection) / len(union) if union else 0
        
        # Check for common abbreviations
        abbrev_sim = self._check_abbreviation_match(name1, name2)
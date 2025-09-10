import re
from typing import List, Dict
from models import ExtractedClaim, Item

# Common medicine names for pattern matching
COMMON_MEDICINES = [
    'paracetamol', 'acetaminophen', 'ibuprofen', 'aspirin', 'amoxicillin', 
    'metformin', 'atorvastatin', 'omeprazole', 'amlodipine', 'losartan',
    'lisinopril', 'simvastatin', 'levothyroxine', 'azithromycin', 'gabapentin',
    'hydrochlorothiazide', 'pantoprazole', 'clopidogrel', 'insulin', 'ranitidine',
    'cetirizine', 'montelukast', 'prednisolone', 'doxycycline', 'ciprofloxacin',
    'vitamin', 'tablet', 'capsule', 'syrup', 'injection', 'drops'
]

def find_medicines_and_prices(text: str) -> List[Item]:
    """Extract medicines with their prices from text"""
    items = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Enhanced price pattern for Indian currency
    price_pattern = r'(?:Rs\.?\s*|₹\s*|INR\s*)?([0-9]{1,4}(?:,[0-9]{3})*(?:\.[0-9]{2})?)'
    
    for line in lines:
        line_lower = line.lower()
        
        # Check if line contains medicine keywords
        has_medicine = any(med in line_lower for med in COMMON_MEDICINES)
        has_medical_term = any(term in line_lower for term in ['tab.', 'cap.', 'syp.', 'inj.', 'tablet', 'capsule', 'syrup', 'injection', 'mg', 'ml'])
        
        if has_medicine or has_medical_term:
            # Look for price in this line
            price_matches = list(re.finditer(price_pattern, line))
            if price_matches:
                # Take the last (rightmost) price match as it's usually the total
                last_match = price_matches[-1]
                try:
                    price = float(last_match.group(1).replace(',', ''))
                    # Clean description by removing the price part
                    desc = line[:last_match.start()].strip()
                    # Remove Rs./₹ symbols from description if any
                    desc = re.sub(r'(?:Rs\.?\s*|₹\s*|INR\s*)', '', desc, flags=re.IGNORECASE)
                    desc = desc.strip(' -:\t')
                    
                    if desc and len(desc) > 2:  # Avoid empty descriptions
                        items.append(Item(description=desc, total=price))
                except ValueError:
                    continue
    
    return items

def find_patient_info(text: str) -> dict:
    out = {}
    # Name
    m = re.search(r'(?:Patient Name|Name of Patient|Patient)[:\-\s]*([A-Z][A-Za-z\s.,]{2,50})', text, re.I)
    if m:
        out['patient_name'] = m.group(1).strip()

    # Age
    m = re.search(r'Age[:\s]*([0-9]{1,3})\b', text, re.I)
    if m:
        out['patient_age'] = int(m.group(1))

    # Relation
    m = re.search(r'Relation[:\s]*(Self|Spouse|Wife|Husband|Son|Daughter|Child|Father|Mother)', text, re.I)
    if m:
        out['patient_relation'] = m.group(1)

    # IDs
    m = re.search(r'(?:Bill No|Invoice No|Ref|Reference)[:\s]*([A-Za-z0-9\-\/]+)', text, re.I)
    if m:
        out['bill_number'] = m.group(1)

    return out


def find_hospital_info(text: str) -> dict:
    out = {}
    # Hospital/clinic name heuristics
    m = re.search(r'((?:Hospital|Clinic|Medical Center|Health Center|Nursing Home)[^\n,]{0,60})', text, re.I)
    if m:
        out['hospital_name'] = m.group(1).strip()

    # Doctor
    m = re.search(r'(Dr\.?\s+[A-Z][A-Za-z\s.]{2,40})', text)
    if m:
        out['doctor_name'] = m.group(1).strip()

    return out


def find_items(text: str) -> List[Item]:
    """Enhanced item extraction focusing on medicines"""
    # Try medicine-specific extraction first
    medicine_items = find_medicines_and_prices(text)
    if medicine_items:
        return medicine_items
    
    # Fallback to general item extraction
    items: List[Item] = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    price_re = re.compile(r'(?:Rs\.?|₹|INR)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)')

    for line in lines:
        # look for lines with a price
        m = price_re.search(line)
        if m:
            try:
                price = float(m.group(1).replace(',', ''))
                # description = line without the price
                desc = price_re.sub('', line).strip(' -:\t')
                if desc and len(desc) > 2:
                    items.append(Item(description=desc, total=price))
            except ValueError:
                continue

    return items


def parse_claim(text: str) -> ExtractedClaim:
    extracted = ExtractedClaim()
    extracted.raw_text = text

    extracted_data = {}
    extracted_data.update(find_patient_info(text))
    extracted_data.update(find_hospital_info(text))

    items = find_items(text)
    extracted.items = items

    # totals
    m = re.search(r'(?:Grand Total|Total Amount|Amount Due|Net Amount)[:\s]*Rs\.?\s*([0-9,]+(?:\.[0-9]{2})?)', text, re.I)
    if m:
        extracted.grand_total = float(m.group(1).replace(',', ''))

    # basic fields
    for k, v in extracted_data.items():
        if hasattr(extracted, k):
            setattr(extracted, k, v)

    return extracted

"""Matching service that wraps `MedicineMatchingService` with a small
adapter interface so the rest of the app sees a compact response shape.
"""
from typing import Dict, Any

# Simple matching functions (since original matcher is moved)
def simple_match_medicines(bill_meds: list, rx_meds: list) -> Dict[str, Any]:
    """Simple medicine matching logic."""
    # Placeholder: in real implementation, use fuzzy matching
    admissible = []
    non_admissible = []
    
    for med in bill_meds:
        if med in rx_meds:
            admissible.append({"medicine": med, "status": "admissible"})
        else:
            non_admissible.append({"medicine": med, "status": "non_admissible"})
    
    return {
        "admissible": admissible,
        "non_admissible": non_admissible,
        "compliance_score": len(admissible) / max(len(bill_meds), 1) * 100
    }


class MatchingService:
    def __init__(self):
        pass

    def compare_bill_and_prescription(self, bill_claim: Dict, prescription_claim: Dict, policy_type: str = 'standard') -> Dict[str, Any]:
        """Compare medicines found in bill and prescription and return analysis."""
        bill_meds = bill_claim.get('medicine_names') or []
        rx_meds = prescription_claim.get('medicine_names') or []

        result = simple_match_medicines(bill_meds, rx_meds)

        # Simple summary returned to the API
        return {
            'medicine_comparison': result.get('admissible', []) + result.get('non_admissible', []),
            'admissible_medicines': result.get('admissible', []),
            'non_admissible_medicines': result.get('non_admissible', []),
            'statistics': {
                'compliance_score': result.get('compliance_score', 0)
            },
            'policy_applied': policy_type,
            'warnings': []
        }

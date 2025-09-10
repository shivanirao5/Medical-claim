#!/usr/bin/env python3
"""
Reimbursement Engine for Medical Claims
Determines admissible and non-admissible medicines based on prescription matching
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from datetime import datetime

@dataclass
class ReimbursementPolicy:
    """Defines reimbursement rules and limits"""
    name: str
    medicine_coverage_percent: float
    test_coverage_percent: float
    consultation_coverage_percent: float
    max_claim_amount: float
    requires_prescription: bool
    allows_otc_medicines: bool
    max_days_from_prescription: int


class ReimbursementEngine:
    """
    Core engine for determining reimbursement eligibility and amounts.
    Compares bills with prescriptions to identify admissible items.
    """
    
    def __init__(self):
        # Define reimbursement policies
        self.policies = {
            "standard": ReimbursementPolicy(
                name="Standard",
                medicine_coverage_percent=80.0,
                test_coverage_percent=70.0,
                consultation_coverage_percent=50.0,
                max_claim_amount=100000.0,
                requires_prescription=True,
                allows_otc_medicines=False,
                max_days_from_prescription=30
            ),
            "premium": ReimbursementPolicy(
                name="Premium",
                medicine_coverage_percent=100.0,
                test_coverage_percent=90.0,
                consultation_coverage_percent=80.0,
                max_claim_amount=500000.0,
                requires_prescription=True,
                allows_otc_medicines=True,
                max_days_from_prescription=45
            ),
            "basic": ReimbursementPolicy(
                name="Basic",
                medicine_coverage_percent=60.0,
                test_coverage_percent=50.0,
                consultation_coverage_percent=30.0,
                max_claim_amount=50000.0,
                requires_prescription=True,
                allows_otc_medicines=False,
                max_days_from_prescription=15
            )
        }
        
        # OTC (Over-the-counter) medicines that might not need prescription
        self.otc_medicines = {
            'paracetamol', 'acetaminophen', 'aspirin', 'ibuprofen',
            'antacid', 'vitamin', 'calcium', 'iron', 'folic acid',
            'cough syrup', 'throat lozenges', 'bandage', 'antiseptic',
            'ointment', 'cream', 'lotion', 'drops'
        }
        
        # Non-reimbursable items (cosmetic, lifestyle, etc.)
        self.non_reimbursable = {
            'cosmetic', 'beauty', 'fairness', 'whitening', 'anti-aging',
            'hair growth', 'weight loss', 'protein powder', 'supplement',
            'energy drink', 'viagra', 'cialis', 'levitra'
        }
    
    def analyze_reimbursement(
        self,
        bill_text: str,
        prescription_text: str,
        bill_claim: Any,
        policy_type: str = "standard"
    ) -> Dict[str, Any]:
        """
        Main method to analyze reimbursement eligibility.
        Compares bill with prescription and determines admissible items.
        """
        policy = self.policies.get(policy_type, self.policies["standard"])
        
        # Extract medicines from both documents
        from medicine_matcher import MedicineMatchingService
        medicine_service = MedicineMatchingService()
        
        bill_medicines = medicine_service.extract_medicine_names(bill_text)
        prescription_medicines = medicine_service.extract_medicine_names(prescription_text)
        
        # Perform medicine comparison
        comparison_result = self._compare_medicines(
            bill_medicines,
            prescription_medicines,
            policy
        )
        
        # Calculate reimbursement amounts
        reimbursement_summary = self._calculate_reimbursement(
            bill_claim,
            comparison_result,
            policy
        )
        
        # Generate warnings and recommendations
        warnings = self._generate_warnings(comparison_result, reimbursement_summary)
        recommendations = self._generate_recommendations(comparison_result, policy)
        
        return {
            "medicine_comparison": comparison_result["comparison_details"],
            "admissible_medicines": comparison_result["admissible"],
            "non_admissible_medicines": comparison_result["non_admissible"],
            "reimbursement_summary": reimbursement_summary,
            "compliance_score": comparison_result["compliance_score"],
            "warnings": warnings,
            "recommendations": recommendations
        }
    
    def _compare_medicines(
        self,
        bill_medicines: List[Dict],
        prescription_medicines: List[Dict],
        policy: ReimbursementPolicy
    ) -> Dict[str, Any]:
        """
        Compare medicines from bill against prescription.
        Determine which are admissible for reimbursement.
        """
        admissible = []
        non_admissible = []
        comparison_details = []
        
        # Extract medicine names for easier comparison
        prescribed_names = {med['name'].lower() for med in prescription_medicines}
        prescribed_names_list = list(prescribed_names)
        
        for bill_med in bill_medicines:
            med_name = bill_med['name'].lower()
            med_info = {
                "medicine": bill_med['name'],
                "original_text": bill_med.get('original_text', ''),
                "confidence": bill_med.get('confidence', 0)
            }
            
            # Check for exact match in prescription
            if med_name in prescribed_names:
                med_info["status"] = "admissible"
                med_info["reason"] = "Exact match found in prescription"
                med_info["match_type"] = "exact"
                admissible.append(med_info)
                comparison_details.append(med_info)
                continue
            
            # Check for fuzzy match (similar names, typos)
            fuzzy_match = self._find_fuzzy_match(med_name, prescribed_names_list)
            if fuzzy_match and fuzzy_match['similarity'] > 0.8:
                med_info["status"] = "admissible"
                med_info["reason"] = f"Fuzzy match with '{fuzzy_match['match']}' (similarity: {fuzzy_match['similarity']:.2f})"
                med_info["match_type"] = "fuzzy"
                med_info["matched_with"] = fuzzy_match['match']
                admissible.append(med_info)
                comparison_details.append(med_info)
                continue
            
            # Check if it's an OTC medicine (policy-dependent)
            if policy.allows_otc_medicines and self._is_otc_medicine(med_name):
                med_info["status"] = "admissible"
                med_info["reason"] = "OTC medicine allowed under policy"
                med_info["match_type"] = "otc"
                admissible.append(med_info)
                comparison_details.append(med_info)
                continue
            
            # Check if it's a non-reimbursable item
            if self._is_non_reimbursable(med_name):
                med_info["status"] = "non_admissible"
                med_info["reason"] = "Non-reimbursable item (cosmetic/lifestyle)"
                med_info["match_type"] = "excluded"
                non_admissible.append(med_info)
                comparison_details.append(med_info)
                continue
            
            # No match found - not admissible
            med_info["status"] = "non_admissible"
            med_info["reason"] = "Not found in prescription"
            med_info["match_type"] = "no_match"
            non_admissible.append(med_info)
            comparison_details.append(med_info)
        
        # Calculate compliance score
        total_items = len(bill_medicines) if bill_medicines else 1
        admissible_count = len(admissible)
        compliance_score = (admissible_count / total_items) * 100
        
        # Check for prescribed medicines not in bill (potential missing items)
        bill_names = {med['name'].lower() for med in bill_medicines}
        missing_prescribed = []
        
        for presc_med in prescription_medicines:
            presc_name = presc_med['name'].lower()
            if presc_name not in bill_names:
                # Check fuzzy match with bill items
                fuzzy_in_bill = any(
                    self._calculate_similarity(presc_name, bill_name) > 0.8
                    for bill_name in bill_names
                )
                if not fuzzy_in_bill:
                    missing_prescribed.append({
                        "medicine": presc_med['name'],
                        "status": "prescribed_but_not_purchased",
                        "reason": "Medicine was prescribed but not found in bill"
                    })
        
        return {
            "admissible": admissible,
            "non_admissible": non_admissible,
            "comparison_details": comparison_details,
            "missing_prescribed": missing_prescribed,
            "compliance_score": compliance_score,
            "total_bill_items": len(bill_medicines),
            "total_prescribed_items": len(prescription_medicines),
            "admissible_count": admissible_count,
            "non_admissible_count": len(non_admissible)
        }
    
    def _calculate_reimbursement(
        self,
        bill_claim: Any,
        comparison_result: Dict,
        policy: ReimbursementPolicy
    ) -> Dict[str, Any]:
        """
        Calculate reimbursement amounts based on admissible items and policy.
        """
        # Get total amounts from bill
        medicine_amount = bill_claim.amount_spent_on_medicine
        test_amount = bill_claim.amount_spent_on_test
        consultation_amount = bill_claim.amount_spent_on_consultation
        total_bill = medicine_amount + test_amount + consultation_amount
        
        # Calculate admissible percentage for medicines
        admissible_ratio = (
            comparison_result["admissible_count"] / 
            max(comparison_result["total_bill_items"], 1)
        )
        
        # Adjust medicine amount based on admissible ratio
        admissible_medicine_amount = medicine_amount * admissible_ratio
        
        # Calculate reimbursements based on policy
        medicine_reimbursement = (
            admissible_medicine_amount * 
            (policy.medicine_coverage_percent / 100)
        )
        test_reimbursement = test_amount * (policy.test_coverage_percent / 100)
        consultation_reimbursement = (
            consultation_amount * 
            (policy.consultation_coverage_percent / 100)
        )
        
        # Total reimbursement
        total_reimbursement = (
            medicine_reimbursement + 
            test_reimbursement + 
            consultation_reimbursement
        )
        
        # Apply policy maximum limit
        if total_reimbursement > policy.max_claim_amount:
            total_reimbursement = policy.max_claim_amount
            capped = True
        else:
            capped = False
        
        # Calculate non-admissible amount
        non_admissible_amount = medicine_amount * (1 - admissible_ratio)
        
        return {
            "total_bill_amount": total_bill,
            "admissible_medicine_amount": admissible_medicine_amount,
            "non_admissible_medicine_amount": non_admissible_amount,
            "test_amount": test_amount,
            "consultation_amount": consultation_amount,
            "medicine_reimbursement": medicine_reimbursement,
            "test_reimbursement": test_reimbursement,
            "consultation_reimbursement": consultation_reimbursement,
            "total_reimbursement": total_reimbursement,
            "policy_max_limit": policy.max_claim_amount,
            "reimbursement_capped": capped,
            "reimbursement_percentage": (total_reimbursement / total_bill * 100) if total_bill > 0 else 0,
            "policy_applied": policy.name
        }
    
    def _find_fuzzy_match(self, medicine_name: str, prescribed_list: List[str]) -> Optional[Dict]:
        """Find best fuzzy match for a medicine name in prescribed list"""
        best_match = None
        best_similarity = 0
        
        for prescribed in prescribed_list:
            similarity = self._calculate_similarity(medicine_name, prescribed)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = prescribed
        
        if best_match and best_similarity > 0.7:
            return {
                "match": best_match,
                "similarity": best_similarity
            }
        return None
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def _is_otc_medicine(self, medicine_name: str) -> bool:
        """Check if medicine is an OTC (over-the-counter) medicine"""
        med_lower = medicine_name.lower()
        return any(otc in med_lower for otc in self.otc_medicines)
    
    def _is_non_reimbursable(self, medicine_name: str) -> bool:
        """Check if medicine is non-reimbursable (cosmetic, lifestyle, etc.)"""
        med_lower = medicine_name.lower()
        return any(excluded in med_lower for excluded in self.non_reimbursable)
    
    def _generate_warnings(
        self,
        comparison_result: Dict,
        reimbursement_summary: Dict
    ) -> List[str]:
        """Generate warnings based on analysis results"""
        warnings = []
        
        # Low compliance score warning
        if comparison_result["compliance_score"] < 50:
            warnings.append(
                f"Low compliance score ({comparison_result['compliance_score']:.1f}%). "
                f"Many items in bill are not found in prescription."
            )
        
        # High non-admissible amount
        if reimbursement_summary["non_admissible_medicine_amount"] > 5000:
            warnings.append(
                f"High non-admissible amount: ₹{reimbursement_summary['non_admissible_medicine_amount']:.2f}. "
                "These medicines will not be reimbursed."
            )
        
        # Reimbursement capped
        if reimbursement_summary["reimbursement_capped"]:
            warnings.append(
                f"Reimbursement capped at policy limit of ₹{reimbursement_summary['policy_max_limit']:.2f}"
            )
        
        # Missing prescribed medicines
        if comparison_result.get("missing_prescribed"):
            missing_count = len(comparison_result["missing_prescribed"])
            warnings.append(
                f"{missing_count} prescribed medicine(s) not found in bill. "
                "Patient may not have purchased all prescribed medicines."
            )
        
        # Many non-admissible items
        if comparison_result["non_admissible_count"] > 5:
            warnings.append(
                f"{comparison_result['non_admissible_count']} non-admissible items found. "
                "Consider reviewing prescription compliance."
            )
        
        return warnings
    
    def _generate_recommendations(
        self,
        comparison_result: Dict,
        policy: ReimbursementPolicy
    ) -> List[str]:
        """Generate recommendations for claim processing"""
        recommendations = []
        
        # High compliance
        if comparison_result["compliance_score"] >= 90:
            recommendations.append(
                "High compliance with prescription. Recommend automatic approval."
            )
        elif comparison_result["compliance_score"] >= 70:
            recommendations.append(
                "Good compliance with prescription. Standard processing recommended."
            )
        else:
            recommendations.append(
                "Low compliance with prescription. Manual review recommended."
            )
        
        # OTC medicines
        if not policy.allows_otc_medicines:
            otc_found = any(
                item.get("match_type") == "otc" 
                for item in comparison_result.get("non_admissible", [])
            )
            if otc_found:
                recommendations.append(
                    "OTC medicines found but not covered under current policy. "
                    "Consider upgrading to Premium policy for OTC coverage."
                )
        
        # Missing prescribed items
        if comparison_result.get("missing_prescribed"):
            recommendations.append(
                "Some prescribed medicines not purchased. "
                "Verify with patient if additional bills are pending."
            )
        
        # Fuzzy matches found
        fuzzy_matches = [
            item for item in comparison_result.get("admissible", [])
            if item.get("match_type") == "fuzzy"
        ]
        if fuzzy_matches:
            recommendations.append(
                f"{len(fuzzy_matches)} medicine(s) matched using fuzzy matching. "
                "Manual verification recommended for these items."
            )
        
        return recommendations
    
    def get_policy_details(self) -> Dict[str, Any]:
        """Get details of all available reimbursement policies"""
        policy_details = {}
        
        for name, policy in self.policies.items():
            policy_details[name] = {
                "name": policy.name,
                "medicine_coverage": f"{policy.medicine_coverage_percent}%",
                "test_coverage": f"{policy.test_coverage_percent}%",
                "consultation_coverage": f"{policy.consultation_coverage_percent}%",
                "max_claim_amount": f"₹{policy.max_claim_amount:,.2f}",
                "requires_prescription": policy.requires_prescription,
                "allows_otc": policy.allows_otc_medicines,
                "prescription_validity_days": policy.max_days_from_prescription
            }
        
        return {
            "policies": policy_details,
            "default_policy": "standard",
            "otc_medicines_list": list(self.otc_medicines),
            "non_reimbursable_categories": list(self.non_reimbursable)
        }
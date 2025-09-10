from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Enhanced Pydantic models for API responses including reimbursement analysis


class Item(BaseModel):
    description: str
    quantity: Optional[str] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


class Medicine(BaseModel):
    """Medicine entry with confidence score and admissibility status"""
    name: str
    original_text: str
    confidence: float
    is_admissible: Optional[bool] = None
    match_type: Optional[str] = None  # exact, fuzzy, otc, no_match
    matched_with: Optional[str] = None
    reason: Optional[str] = None


class ClaimItem(BaseModel):
    """Structured claim item matching the required output format"""
    bill_no: str
    my_date: str
    amount_spent_on_medicine: float
    amount_spent_on_test: float
    amount_spent_on_consultation: float
    medicine_names: List[str]
    test_names: List[str]
    doctor_name: str
    hospital_name: str
    reimbursement_amount: float
    editable: bool = True


class MedicineComparisonResult(BaseModel):
    """Result of comparing a medicine between bill and prescription"""
    medicine: str
    original_text: Optional[str] = None
    status: str  # admissible, non_admissible, prescribed_but_not_purchased
    reason: str
    match_type: str  # exact, fuzzy, otc, no_match, excluded
    confidence: float = 0.0
    matched_with: Optional[str] = None


class ReimbursementSummary(BaseModel):
    """Summary of reimbursement calculation"""
    total_bill_amount: float
    admissible_medicine_amount: float
    non_admissible_medicine_amount: float
    test_amount: float
    consultation_amount: float
    medicine_reimbursement: float
    test_reimbursement: float
    consultation_reimbursement: float
    total_reimbursement: float
    policy_max_limit: float
    reimbursement_capped: bool
    reimbursement_percentage: float
    policy_applied: str


class ReimbursementAnalysis(BaseModel):
    """Complete reimbursement analysis result"""
    bill_details: Dict[str, Any]
    prescription_details: Dict[str, Any]
    medicine_comparison: List[MedicineComparisonResult]
    admissible_medicines: List[Dict[str, Any]]
    non_admissible_medicines: List[Dict[str, Any]]
    missing_prescribed_medicines: List[Dict[str, Any]] = Field(default_factory=list)
    reimbursement_summary: ReimbursementSummary
    compliance_score: float
    warnings: List[str]
    recommendations: List[str]
    policy_applied: str
    processing_timestamp: datetime = Field(default_factory=datetime.now)


class ValidationResult(BaseModel):
    """Result of claim validation"""
    is_valid: bool
    validation_checks: List[Dict[str, Any]]
    missing_requirements: List[str]
    fraud_indicators: List[str]
    recommendation: str


class BulkProcessingResult(BaseModel):
    """Result of bulk claim processing"""
    total_files: int
    successfully_processed: int
    failed: int
    total_claim_amount: float
    total_reimbursement: float
    results: List[Dict[str, Any]]


class ExtractedClaim(BaseModel):
    """Enhanced extracted claim with reimbursement fields"""
    # Patient information
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_relation: Optional[str] = None
    patient_id: Optional[str] = None
    
    # Hospital/Doctor information
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_license: Optional[str] = None
    
    # Bill information
    bill_number: Optional[str] = None
    invoice_number: Optional[str] = None
    reference_id: Optional[str] = None
    date_of_service: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    
    # Medical information
    diagnosis: Optional[str] = None
    items: List[Item] = Field(default_factory=list)
    medicines: List[Dict] = Field(default_factory=list)
    claim_items: List[Dict] = Field(default_factory=list)
    
    # Financial information
    subtotal: Optional[float] = None
    taxes: Optional[float] = None
    discounts: Optional[float] = None
    grand_total: Optional[float] = None
    
    # Reimbursement information
    admissible_amount: Optional[float] = None
    non_admissible_amount: Optional[float] = None
    approved_reimbursement: Optional[float] = None
    reimbursement_status: Optional[str] = None  # pending, approved, rejected, partial
    
    # Document verification
    signature_present: Optional[bool] = None
    stamps_present: Optional[bool] = None
    prescription_attached: Optional[bool] = None
    
    # Processing information
    raw_text: Optional[str] = None
    text_quality: Optional[dict] = None
    total_pages: int = 0
    processing_status: str = "completed"
    ocr_confidence: Optional[float] = None
    extraction_method: Optional[str] = None  # direct, ocr, handwritten_ocr


class PolicyDetails(BaseModel):
    """Reimbursement policy details"""
    name: str
    medicine_coverage: str
    test_coverage: str
    consultation_coverage: str
    max_claim_amount: str
    requires_prescription: bool
    allows_otc: bool
    prescription_validity_days: int


class ComparisonRequest(BaseModel):
    """Request model for comparing bill and prescription"""
    bill_text: str
    prescription_text: str
    policy_type: str = "standard"
    strict_matching: bool = False
    include_otc: bool = False


class ComparisonResponse(BaseModel):
    """Response model for bill-prescription comparison"""
    admissible_medicines: List[MedicineComparisonResult]
    non_admissible_medicines: List[MedicineComparisonResult]
    missing_prescribed: List[MedicineComparisonResult]
    compliance_score: float
    total_admissible_amount: float
    total_non_admissible_amount: float
    recommended_action: str  # approve, review, reject
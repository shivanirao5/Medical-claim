from pydantic import BaseModel, Field
from typing import List, Optional, Dict

# Simple Pydantic models used for API responses. These models provide
# validation and a stable JSON schema for the frontend to consume.


class Item(BaseModel):
    description: str
    quantity: Optional[str] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


class Medicine(BaseModel):
    # Medicine entry with optional confidence score if available from
    # the extraction pipeline (useful when multiple extraction strategies
    # or ML models are combined).
    name: str
    original_text: str
    confidence: float


class ClaimItem(BaseModel):
    """Structured claim item matching the required output format.

    Note: This mirrors the dataclass used in the parser but as a Pydantic
    model so it serializes cleanly for API responses.
    """
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


class ExtractedClaim(BaseModel):
    # Top-level object returned by the /extract API. It contains optional
    # metadata about the patient and the raw text, plus structured lists
    # such as `claim_items` and `medicines` which the frontend displays.
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_relation: Optional[str] = None
    patient_id: Optional[str] = None
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_license: Optional[str] = None
    bill_number: Optional[str] = None
    invoice_number: Optional[str] = None
    reference_id: Optional[str] = None
    date_of_service: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    diagnosis: Optional[str] = None
    items: List[Item] = Field(default_factory=list)
    medicines: List[Dict] = Field(default_factory=list)  # Extracted medicines with confidence scores
    claim_items: List[ClaimItem] = Field(default_factory=list)  # Structured claim items
    subtotal: Optional[float] = None
    taxes: Optional[float] = None
    discounts: Optional[float] = None
    grand_total: Optional[float] = None
    signature_present: Optional[bool] = None
    stamps_present: Optional[bool] = None
    raw_text: Optional[str] = None
    text_quality: Optional[dict] = None
    total_pages: int = 0
    processing_status: str = "completed"

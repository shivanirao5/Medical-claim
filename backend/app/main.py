"""Simple backend facade for the medical-claims-ai project.

This module exposes two clear endpoints:
- /extract : extract structured claim data from a single file
- /compare-and-reimburse : compare bill and prescription and return reimbursement analysis

It reuses the existing parsers and services in the repository but provides
an easier-to-read entrypoint and clearer comments for learning and extension.
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime

# Import lightweight services from this app that wrap the original backend
from app.services.extraction_service import ExtractionService
from app.services.matching_service import MatchingService
from app.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="medical-claims-ai - simplified backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
extraction = ExtractionService()
matching = MatchingService()


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Receive a file and return structured claim data with automatic OCR mode detection.

    The endpoint handles plain text, PDFs and common image formats.
    It automatically detects and processes both printed and handwritten content.
    """
    try:
        contents = await file.read()
        logger.info(f"Received file: {file.filename} ({file.content_type}) size={len(contents)}")

        claim = extraction.process_file_bytes(contents, filename=file.filename, content_type=file.content_type)
        
        # Format response to match frontend expectations
        response = {
            "claim_items": [claim] if "error" not in claim else [],
            "total_pages": claim.get("ocr_metadata", {}).get("pages_processed", 1),
            "processing_status": "completed",
            "raw_text": claim.get("raw_text", ""),
            "processing_timestamp": datetime.now().isoformat()
        }
        
        # Add detailed OCR metadata
        ocr_metadata = claim.get("ocr_metadata", {})
        response["ocr_metadata"] = {
            "confidence": ocr_metadata.get("confidence", 85.0),
            "ocr_method": ocr_metadata.get("extraction_method", "Automatic AI Detection"),
            "pages_processed": ocr_metadata.get("pages_processed", 1),
            "handwriting_regions_found": ocr_metadata.get("handwriting_regions_found", 0),
            "processing_approaches": ocr_metadata.get("processing_approaches", 1),
            "automatic_mode": True
        }
        
        return JSONResponse(content=response)

    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare-and-reimburse")
async def compare_and_reimburse(
    bill_file: UploadFile = File(...),
    prescription_file: UploadFile = File(...),
    policy_type: Optional[str] = Form("standard")
):
    """Compare a bill and prescription and return reimbursement analysis.

    This high-level endpoint uses the `ExtractionService` to obtain structured
    text with automatic OCR mode detection and the `MatchingService` to compute 
    admissibility and reimbursement.
    """
    try:
        bill_bytes = await bill_file.read()
        rx_bytes = await prescription_file.read()

        bill_claim = extraction.process_file_bytes(bill_bytes, filename=bill_file.filename, content_type=bill_file.content_type)
        rx_claim = extraction.process_file_bytes(rx_bytes, filename=prescription_file.filename, content_type=prescription_file.content_type)

        analysis = matching.compare_bill_and_prescription(bill_claim, rx_claim, policy_type=policy_type)
        analysis['processing_timestamp'] = datetime.now().isoformat()
        return JSONResponse(content=analysis)

    except Exception as e:
        logger.exception("Compare and reimburse failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract")
async def api_extract(file: UploadFile = File(...)):
    """API endpoint for file extraction - matches frontend expectations with automatic OCR."""
    return await extract(file)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}

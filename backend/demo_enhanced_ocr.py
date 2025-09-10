"""Demo script to showcase enhanced OCR capabilities for handwritten content extraction."""

import requests
import os
import json
from pathlib import Path

def test_pdf_extraction(pdf_path: str, enhance_handwriting: bool = True):
    """Test PDF extraction with enhanced OCR."""
    print(f"\n🔍 Testing PDF: {Path(pdf_path).name}")
    print(f"🖊️ Handwriting enhancement: {'ON' if enhance_handwriting else 'OFF'}")
    print("-" * 60)
    
    try:
        endpoint = '/api/extract-handwritten' if enhance_handwriting else '/api/extract'
        
        with open(pdf_path, 'rb') as f:
            files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
            if not enhance_handwriting:
                data = {'enhance_handwriting': 'false'}
                response = requests.post(f'http://localhost:8000/api/extract', files=files, data=data)
            else:
                response = requests.post(f'http://localhost:8000{endpoint}', files=files)
        
        if response.status_code == 200:
            result = response.json()
            
            print("✅ Extraction successful!")
            print(f"📄 Pages processed: {result.get('total_pages', 0)}")
            
            # OCR Metadata
            ocr_meta = result.get('ocr_metadata', {})
            print(f"🔍 OCR Confidence: {ocr_meta.get('confidence', 0):.1f}%")
            print(f"⚙️ OCR Method: {ocr_meta.get('ocr_method', 'Unknown')}")
            print(f"✋ Handwriting regions: {ocr_meta.get('handwriting_regions_found', 0)}")
            
            # Extracted claim data
            claims = result.get('claim_items', [])
            if claims:
                claim = claims[0]
                print(f"\n📋 EXTRACTED INFORMATION:")
                print(f"👤 Patient: {claim.get('patient_name', 'Not found')}")
                print(f"🏥 Hospital: {claim.get('hospital_name', 'Not found')}")
                print(f"👨‍⚕️ Doctor: {claim.get('doctor_name', 'Not found')}")
                print(f"📅 Date: {claim.get('my_date', 'Not found')}")
                print(f"🏷️ Bill No: {claim.get('bill_no', 'Not found')}")
                
                print(f"\n💰 FINANCIAL BREAKDOWN:")
                print(f"💊 Medicine cost: Rs. {claim.get('amount_spent_on_medicine', 0):.2f}")
                print(f"🧪 Test cost: Rs. {claim.get('amount_spent_on_test', 0):.2f}")
                print(f"👨‍⚕️ Consultation: Rs. {claim.get('amount_spent_on_consultation', 0):.2f}")
                print(f"💵 Grand Total: Rs. {claim.get('grand_total', 0):.2f}")
                print(f"💳 Reimbursement: Rs. {claim.get('reimbursement_amount', 0):.2f}")
                
                medicines = claim.get('medicine_names', [])
                tests = claim.get('test_names', [])
                
                if medicines:
                    print(f"\n💊 MEDICINES DETECTED ({len(medicines)}):")
                    for i, med in enumerate(medicines[:5], 1):
                        print(f"  {i}. {med}")
                
                if tests:
                    print(f"\n🧪 TESTS DETECTED ({len(tests)}):")
                    for i, test in enumerate(tests[:5], 1):
                        print(f"  {i}. {test}")
                
                # Show first 200 chars of raw text
                raw_text = claim.get('raw_text', '')
                if raw_text:
                    print(f"\n📝 RAW TEXT PREVIEW:")
                    print(f"'{raw_text[:200]}...'")
            else:
                print("❌ No claims extracted from the document")
                
        else:
            print(f"❌ Extraction failed: {response.status_code}")
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")

def main():
    """Main demo function."""
    print("🚀 ENHANCED OCR FOR MEDICAL DOCUMENTS")
    print("=" * 80)
    print("📌 Features:")
    print("  • PDF to high-resolution image conversion")
    print("  • Advanced handwriting recognition")
    print("  • Smart medicine & test name extraction")
    print("  • Intelligent amount categorization")
    print("  • Multi-page document processing")
    print("=" * 80)
    
    # Check if server is running
    try:
        health_response = requests.get('http://localhost:8000/health', timeout=5)
        if health_response.status_code == 200:
            print("✅ Backend server is running")
        else:
            print("❌ Backend server health check failed")
            return
    except Exception as e:
        print(f"❌ Cannot connect to backend server: {e}")
        print("💡 Make sure to run: uvicorn app.main:app --reload --port 8000")
        return
    
    # Test with available PDFs
    test_pdfs = [
        "test_inputs/Bill sample copy.pdf",
        "test_inputs/Bill sample -2.pdf", 
        "test_inputs/Bill sample -3.pdf"
    ]
    
    for pdf_path in test_pdfs:
        if os.path.exists(pdf_path):
            # Test both modes
            test_pdf_extraction(pdf_path, enhance_handwriting=True)
            print("\n" + "="*60)
            test_pdf_extraction(pdf_path, enhance_handwriting=False)
            print("\n" + "🔄 " + "="*58 + " 🔄\n")
        else:
            print(f"⚠️ PDF not found: {pdf_path}")
    
    print("✨ Demo completed!")
    print("\n💡 To test your own documents:")
    print("  1. Start the frontend: npm run dev")
    print("  2. Open http://localhost:8082")
    print("  3. Upload PDF/image files")
    print("  4. Toggle 'Handwritten Mode' for prescriptions")

if __name__ == "__main__":
    main()

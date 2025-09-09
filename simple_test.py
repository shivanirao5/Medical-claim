import requests
import json

# Test direct backend endpoint
try:
    # Create a simple text file to test with instead of PDF
    test_content = b"Patient Name: John Doe\nAge: 35\nDiagnosis: Headache\nMedicines:\nParacetamol 500mg - Rs. 25\nConsultation Fee - Rs. 200\nTotal Amount: Rs. 225"
    
    files = {'file': ('test_bill.txt', test_content, 'text/plain')}
    response = requests.post('http://127.0.0.1:8000/extract', files=files, timeout=10)
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("✓ Backend extract works!")
        print(f"Raw text length: {len(result.get('raw_text', ''))}")
        print(f"Patient name: {result.get('patient_name', 'Not found')}")
        print(f"Items found: {len(result.get('items', []))}")
    else:
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"Test failed: {e}")

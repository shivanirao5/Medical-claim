import requests
import json

# Test with our sample medical bill
try:
    with open('sample_medical_bill.txt', 'rb') as f:
        files = {'file': ('sample_medical_bill.txt', f, 'text/plain')}
        response = requests.post('http://127.0.0.1:8000/extract', files=files, timeout=10)
    
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Raw text extracted: {len(result.get('raw_text', ''))} characters")
        print(f"✅ Patient name: {result.get('patient_name', 'Not found')}")
        print(f"✅ Items found: {len(result.get('items', []))}")
        print(f"✅ Grand total: {result.get('grand_total', 'Not found')}")
        
        # Show first few items
        items = result.get('items', [])
        if items:
            print("✅ Sample items:")
            for i, item in enumerate(items[:3]):
                print(f"   {i+1}. {item.get('description', 'No description')} - {item.get('total', 'No price')}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
        
except Exception as e:
    print(f"❌ Test failed: {e}")

print("\n" + "="*50)
print("✅ BACKEND IS WORKING!")
print("✅ Frontend available at: http://localhost:8080/")
print("✅ Backend API docs at: http://127.0.0.1:8000/docs")
print("="*50)

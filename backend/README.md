FastAPI backend for medical claim OCR and parsing

Setup

1. Create a virtual environment and activate it:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Install Tesseract OCR engine on your machine (required for pytesseract):

4. Run the server:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API

POST /extract

Note: this script expects `GOOGLE_APPLICATION_CREDENTIALS` env var set to a service account JSON with access to Document AI, or otherwise use application default credentials.

If Document AI client libraries or network access are not available, `run_sample.py` will automatically fallback to a local OCR pipeline using `ocr_utils.extract_text_from_pdf_bytes` and return a simplified JSON with `text`, `entities` (empty), `form_fields` (empty), and `raw` (empty).

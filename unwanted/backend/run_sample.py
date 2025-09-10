import os
import sys
import json
from typing import Optional


def _call_docai_if_available(file_bytes: bytes, mime_type: str = 'application/pdf') -> Optional[dict]:
    try:
        # Import here to allow fallback when google libs are not installed
        from document_ai import process_document_with_docai
        return process_document_with_docai(file_bytes, mime_type=mime_type)
    except Exception as e:
        print(f"Document AI call failed or not available: {e}")
        return None


def _fallback_local_ocr(file_bytes: bytes) -> dict:
    try:
        from ocr_utils import extract_text_from_pdf_bytes
        text = extract_text_from_pdf_bytes(file_bytes)
        return {
            'text': text,
            'entities': [],
            'form_fields': [],
            'raw': {}
        }
    except Exception as e:
        print(f"Local OCR fallback failed: {e}")
        return {
            'text': '',
            'entities': [],
            'form_fields': [],
            'raw': {}
        }


def process_document_sample(project_id: str, location: str, processor_id: str, file_path: str, mime_type: str = 'application/pdf') -> dict:
    """Helper to run Document AI processor for a local file and return JSON output."""
    # Temporarily set env vars expected by document_ai wrapper
    os.environ['DOCUMENT_AI_PROJECT_ID'] = project_id
    os.environ['DOCUMENT_AI_LOCATION'] = location
    os.environ['DOCUMENT_AI_PROCESSOR_ID'] = processor_id

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, 'rb') as f:
        file_bytes = f.read()

    # Try Document AI first (if available). If it fails, fallback to local OCR pipeline.
    docai_result = _call_docai_if_available(file_bytes, mime_type=mime_type)
    if docai_result is not None:
        return docai_result

    print('Falling back to local OCR pipeline...')
    return _fallback_local_ocr(file_bytes)


def _cli():
    # Simple CLI: expects 4 args: project_id location processor_id file_path [mime_type]
    if len(sys.argv) < 5:
        print("Usage: python run_sample.py <project_id> <location> <processor_id> <file_path> [mime_type]")
        sys.exit(2)

    project_id = sys.argv[1]
    location = sys.argv[2]
    processor_id = sys.argv[3]
    file_path = sys.argv[4]
    mime_type = sys.argv[5] if len(sys.argv) > 5 else 'application/pdf'

    print(f"Running Document AI processor {processor_id} in {location} for project {project_id} on file {file_path}")

    out = process_document_sample(project_id=project_id, location=location, processor_id=processor_id, file_path=file_path, mime_type=mime_type)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    _cli()

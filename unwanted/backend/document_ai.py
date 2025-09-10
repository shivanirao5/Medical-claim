import os
import json
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account


def process_document_with_docai(file_bytes: bytes, mime_type: str = 'application/pdf') -> dict:
    """Call Google Document AI processor and return structured output.
    Expects env vars: DOCUMENT_AI_PROJECT_ID, DOCUMENT_AI_LOCATION, DOCUMENT_AI_PROCESSOR_ID
    Optionally: GOOGLE_APPLICATION_CREDENTIALS for service account
    """
    project_id = os.environ.get('DOCUMENT_AI_PROJECT_ID')
    location = os.environ.get('DOCUMENT_AI_LOCATION', 'us')
    processor_id = os.environ.get('DOCUMENT_AI_PROCESSOR_ID')

    if not project_id or not processor_id:
        raise ValueError('DOCUMENT_AI_PROJECT_ID and DOCUMENT_AI_PROCESSOR_ID must be set')

    # Create client using application default credentials or service account
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_path:
        creds = service_account.Credentials.from_service_account_file(creds_path)
        client = documentai.DocumentProcessorServiceClient(credentials=creds)
    else:
        client = documentai.DocumentProcessorServiceClient()

    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    document = {
        "content": file_bytes,
        "mime_type": mime_type
    }

    request = {
        "name": name,
        "raw_document": document
    }

    result = client.process_document(request=request)
    document_obj = result.document

    # Extract text
    full_text = document_obj.text if document_obj and hasattr(document_obj, 'text') else ''

    # Extract entities and form fields
    fields = []
    try:
        for entity in document_obj.entities:
            fields.append({
                'type': entity.type_,
                'mention_text': entity.mention_text,
                'confidence': entity.confidence,
                'normalized_value': entity.normalized_value.text if entity.normalized_value else None
            })
    except Exception:
        # some processors expose entities differently
        pass

    form_fields = []
    try:
        for page in document_obj.pages:
            for form_field in page.form_fields:
                name = form_field.field_name.text_anchor
                value = form_field.field_value.text_anchor
                # Resolve anchors -> simplified extraction (Document AI has text anchors referencing ranges)
                def anchor_text(anchor):
                    if not anchor or not anchor.text_segments:
                        return ''
                    parts = []
                    for seg in anchor.text_segments:
                        start_index = int(seg.start_index) if seg.start_index else 0
                        end_index = int(seg.end_index) if seg.end_index else None
                        parts.append(full_text[start_index:end_index])
                    return ''.join(parts)

                form_fields.append({
                    'name': anchor_text(form_field.field_name.text_anchor),
                    'value': anchor_text(form_field.field_value.text_anchor)
                })
    except Exception:
        pass

    output = {
        'text': full_text,
        'entities': fields,
        'form_fields': form_fields,
        'raw': json.loads(document_obj.to_json() if hasattr(document_obj, 'to_json') else '{}')
    }

    return output

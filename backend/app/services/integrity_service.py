import hashlib
import os
from app.models.document import Document

def verify_document_integrity(document: Document) -> dict:
    """
    Computes the SHA-256 hash of the physical file at document.file_path and
    compares it with document.file_hash stored in the database.
    """
    # Locate file path
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    file_path = os.path.join(base_dir, document.file_path)

    if not os.path.exists(file_path):
        return {
            "status": "missing_file",
            "file_name": document.file_name,
            "stored_hash": document.file_hash,
            "calculated_hash": None
        }

    try:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        calculated_hash = sha256.hexdigest()
    except Exception as e:
        return {
            "status": "error",
            "file_name": document.file_name,
            "stored_hash": document.file_hash,
            "calculated_hash": None,
            "error_msg": str(e)
        }

    if calculated_hash == document.file_hash:
        return {
            "status": "matched",
            "file_name": document.file_name,
            "stored_hash": document.file_hash,
            "calculated_hash": calculated_hash
        }
    else:
        return {
            "status": "mismatched",
            "file_name": document.file_name,
            "stored_hash": document.file_hash,
            "calculated_hash": calculated_hash
        }

import os
import qrcode
import hashlib

def generate_credential_qr(credential_id: str) -> str:
    """
    Generates a QR code for a given credential_id.
    If credential_id is a full URI/URL, encodes it directly and uses a hashed filename.
    Otherwise, encodes http://localhost:8080/verify/{credential_id} and uses credential_id as filename.
    """
    # Base directory for uploads/qrcodes
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    qrcodes_dir = os.path.join(base_dir, "uploads", "qrcodes")
    os.makedirs(qrcodes_dir, exist_ok=True)

    is_uri = any(credential_id.startswith(p) for p in ["http://", "https://", "openid-credential-offer://", "urn:"])
    
    if is_uri:
        qr_data = credential_id
        # Use MD5 hash of the URI to get a safe alphanumeric filename
        file_hash = hashlib.md5(credential_id.encode('utf-8')).hexdigest()
        file_name = f"VC-8F2A-{file_hash[:4].upper()}-{file_hash[4:8].upper()}.png"
    else:
        qr_data = f"http://localhost:8080/verify/{credential_id}"
        file_name = f"{credential_id}.png"

    # Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    file_path = os.path.join(qrcodes_dir, file_name)
    img.save(file_path)

    return f"/uploads/qrcodes/{file_name}"

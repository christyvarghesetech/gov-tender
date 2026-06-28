import os
import qrcode

def generate_credential_qr(credential_id: str) -> str:
    """
    Generates a QR code for a given credential_id.
    Encodes the verification URL: http://localhost:8080/verify/{credential_id}
    Saves the image to backend/uploads/qrcodes/{credential_id}.png
    Returns the relative path '/uploads/qrcodes/{credential_id}.png'
    """
    # Base directory for uploads/qrcodes
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    qrcodes_dir = os.path.join(base_dir, "uploads", "qrcodes")
    os.makedirs(qrcodes_dir, exist_ok=True)

    # Content to encode
    qr_data = f"http://localhost:8080/verify/{credential_id}"

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
    file_name = f"{credential_id}.png"
    file_path = os.path.join(qrcodes_dir, file_name)
    img.save(file_path)

    return f"/uploads/qrcodes/{file_name}"

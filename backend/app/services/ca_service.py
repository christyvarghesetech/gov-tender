import os
import datetime
import shutil
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12

# Storage Directory for Keys and Certificates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEYS_DIR = os.path.join(BASE_DIR, "keys")
os.makedirs(KEYS_DIR, exist_ok=True)

PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "department_privkey.pem")
CSR_PATH = os.path.join(KEYS_DIR, "department_csr.pem")
CERT_PATH = os.path.join(KEYS_DIR, "department_cert.pem")
CA_CERT_PATH = os.path.join(KEYS_DIR, "ca_cert.pem")
CA_KEY_PATH = os.path.join(KEYS_DIR, "ca_key.pem")
P12_OUTPUT_PATH = os.path.join(KEYS_DIR, "local.p12")

# Optional automatic deployment path (e.g. to copy keystore directly into local Inji stack)
INJI_KEYSTORE_COPY_TARGETS = [
    os.path.join(BASE_DIR, "..", "scratch_inji", "docker-compose", "docker-compose-injistack", "config", "local.p12")
]

def generate_key_and_csr(common_name: str, organization: str, country: str) -> dict:
    """
    Generates a new department RSA 2048 keypair, stores the private key,
    and returns a Certificate Signing Request (CSR) in PEM format.
    """
    # 1. Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # 2. Serialize and save private key to disk
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(priv_pem)

    # 3. Create CSR subject name
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # 4. Build CSR
    csr = x509.CertificateSigningRequestBuilder().subject_name(subject).sign(
        private_key, hashes.SHA256()
    )

    # 5. Serialize and save CSR
    csr_pem = csr.public_bytes(serialization.Encoding.PEM)
    with open(CSR_PATH, "wb") as f:
        f.write(csr_pem)

    # Clean up previous certificate if any
    if os.path.exists(CERT_PATH):
        os.remove(CERT_PATH)
    if os.path.exists(P12_OUTPUT_PATH):
        os.remove(P12_OUTPUT_PATH)

    return {
        "status": "pending_ca_signature",
        "common_name": common_name,
        "organization": organization,
        "country": country,
        "csr_pem": csr_pem.decode("utf-8")
    }

def mock_sign_csr() -> dict:
    """
    Simulates CA signing. Generates a mock Root CA (if missing), signs the department CSR,
    and packages the resulting key & cert into a local.p12 keystore.
    """
    if not os.path.exists(PRIVATE_KEY_PATH) or not os.path.exists(CSR_PATH):
        raise ValueError("Private key or CSR does not exist. Generate CSR first.")

    # 1. Load department private key and CSR
    with open(PRIVATE_KEY_PATH, "rb") as f:
        dept_private_key = serialization.load_pem_private_key(f.read(), password=None)
    with open(CSR_PATH, "rb") as f:
        csr = x509.load_pem_x509_csr(f.read())

    # 2. Get or generate Mock Root CA key and cert
    if os.path.exists(CA_KEY_PATH) and os.path.exists(CA_CERT_PATH):
        with open(CA_KEY_PATH, "rb") as f:
            ca_private_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(CA_CERT_PATH, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
    else:
        # Generate new Root CA key
        ca_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_priv_pem = ca_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(CA_KEY_PATH, "wb") as f:
            f.write(ca_priv_pem)

        # Generate Root CA Cert
        ca_name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "GovTender Sandbox CA Authority"),
            x509.NameAttribute(NameOID.COMMON_NAME, "GovTender Sandbox Root CA"),
        ])
        ca_cert = x509.CertificateBuilder().subject_name(
            ca_name
        ).issuer_name(
            ca_name
        ).public_key(
            ca_private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow() - datetime.timedelta(days=1)
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=3650)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        ).sign(ca_private_key, hashes.SHA256())

        with open(CA_CERT_PATH, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    # 3. Sign the department's CSR using the CA Key
    cert_builder = x509.CertificateBuilder().subject_name(
        csr.subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        csr.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow() - datetime.timedelta(days=1)
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    )
    
    dept_cert = cert_builder.sign(ca_private_key, hashes.SHA256())
    dept_cert_pem = dept_cert.public_bytes(serialization.Encoding.PEM)

    with open(CERT_PATH, "wb") as f:
        f.write(dept_cert_pem)

    # 4. Package key & cert into PKCS12 keystore (local.p12)
    build_keystore(dept_private_key, dept_cert, ca_cert)

    return {
        "status": "active",
        "certificate_pem": dept_cert_pem.decode("utf-8"),
        "ca_certificate_pem": ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    }

def import_ca_signed_certificate(cert_pem_str: str) -> dict:
    """
    Imports a CA-signed certificate PEM, validates it against the generated private key,
    and packages it into local.p12.
    """
    if not os.path.exists(PRIVATE_KEY_PATH):
        raise ValueError("Private key does not exist. Generate CSR first.")

    # 1. Load private key
    with open(PRIVATE_KEY_PATH, "rb") as f:
        dept_private_key = serialization.load_pem_private_key(f.read(), password=None)

    # 2. Parse certificate
    try:
        dept_cert = x509.load_pem_x509_certificate(cert_pem_str.encode("utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to parse certificate PEM: {e}")

    # 3. Validate public key matches
    priv_public_bytes = dept_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    cert_public_bytes = dept_cert.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    if priv_public_bytes != cert_public_bytes:
        raise ValueError("The certificate does not match the private key generated for the CSR.")

    # 4. Save certificate to disk
    with open(CERT_PATH, "wb") as f:
        f.write(cert_pem_str.encode("utf-8"))

    # 5. Pack keystore
    build_keystore(dept_private_key, dept_cert, None)

    return {"status": "active"}

def build_keystore(private_key, certificate, ca_cert=None):
    """
    Builds a PKCS12 keystore (local.p12) with the standard 'local' password
    needed by Inji Certify/MOSIP's KeyManager.
    """
    cas = [ca_cert] if ca_cert else None
    
    # Pack keystore
    p12_data = pkcs12.serialize_key_and_certificates(
        name=b"certify-signing-key",  # Standard alias used inside certifiers
        key=private_key,
        cert=certificate,
        cas=cas,
        encryption_algorithm=serialization.BestAvailableEncryption(b"local")
    )

    # Write keystore to disk
    with open(P12_OUTPUT_PATH, "wb") as f:
        f.write(p12_data)

    # Automatically sync to Inji Certify dev paths if mapped/accessible
    for target_path in INJI_KEYSTORE_COPY_TARGETS:
        target_dir = os.path.dirname(target_path)
        if os.path.exists(target_dir):
            try:
                shutil.copy2(P12_OUTPUT_PATH, target_path)
                print(f"[CA SERVICE] Keystore auto-deployed to: {target_path}")
            except Exception as e:
                print(f"[CA SERVICE] Failed to deploy keystore to {target_path}: {e}")

def get_keystore_status() -> dict:
    """
    Returns the current cryptographic keystore config status.
    """
    has_key = os.path.exists(PRIVATE_KEY_PATH)
    has_csr = os.path.exists(CSR_PATH)
    has_cert = os.path.exists(CERT_PATH)
    has_p12 = os.path.exists(P12_OUTPUT_PATH)

    csr_pem = ""
    cert_pem = ""
    ca_pem = ""
    subject_info = {}
    validity = {}
    issuer_info = {}

    if has_csr:
        try:
            with open(CSR_PATH, "rb") as f:
                csr_data = f.read()
                csr_pem = csr_data.decode("utf-8")
                csr = x509.load_pem_x509_csr(csr_data)
                subject_info = {
                    "common_name": csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
                    "organization": csr.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value,
                    "country": csr.subject.get_attributes_for_oid(NameOID.COUNTRY_NAME)[0].value,
                }
        except Exception:
            pass

    if has_cert:
        try:
            with open(CERT_PATH, "rb") as f:
                cert_data = f.read()
                cert_pem = cert_data.decode("utf-8")
                cert = x509.load_pem_x509_certificate(cert_data)
                
                # Update subject details from active cert
                subject_info = {
                    "common_name": cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
                    "organization": cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value,
                    "country": cert.subject.get_attributes_for_oid(NameOID.COUNTRY_NAME)[0].value,
                }
                
                issuer_info = {
                    "common_name": cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
                    "organization": cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value,
                }

                validity = {
                    "not_before": cert.not_valid_before.strftime("%Y-%m-%d %H:%M:%S"),
                    "not_after": cert.not_valid_after.strftime("%Y-%m-%d %H:%M:%S")
                }
        except Exception:
            pass

    if os.path.exists(CA_CERT_PATH):
        try:
            with open(CA_CERT_PATH, "rb") as f:
                ca_pem = f.read().decode("utf-8")
        except Exception:
            pass

    status = "inactive"
    if has_key:
        status = "pending_ca_signature"
    if has_cert and has_p12:
        status = "active"

    return {
        "status": status,
        "has_private_key": has_key,
        "has_csr": has_csr,
        "has_certificate": has_cert,
        "has_keystore": has_p12,
        "csr_pem": csr_pem,
        "certificate_pem": cert_pem,
        "ca_certificate_pem": ca_pem,
        "subject": subject_info,
        "issuer": issuer_info,
        "validity": validity
    }

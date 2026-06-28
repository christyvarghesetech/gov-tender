import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

def generate_tender_keypair() -> tuple:
    """
    Generates a new RSA 2048 keypair.
    Returns:
        (private_key_pem: str, public_key_pem: str)
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    public_key = private_key.public_key()
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    return pem_private, pem_public

def encrypt_with_public_key(public_key_pem: str, data: str) -> str:
    """
    Encrypts string data using the PEM-encoded public key.
    Returns the base64-encoded ciphertext.
    """
    pub_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
    ciphertext = pub_key.encrypt(
        data.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(ciphertext).decode('utf-8')

def decrypt_with_private_key(private_key_pem: str, ciphertext_b64: str) -> str:
    """
    Decrypts the base64-encoded ciphertext using the PEM-encoded private key.
    Returns the decrypted string.
    """
    priv_key = serialization.load_pem_private_key(private_key_pem.encode('utf-8'), password=None)
    ciphertext = base64.b64decode(ciphertext_b64.encode('utf-8'))
    decrypted = priv_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted.decode('utf-8')

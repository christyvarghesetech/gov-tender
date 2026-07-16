import os
import json
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def main():
    print("Initializing eSignet Local Keys and Configs...")
    
    esignet_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Generate RSA private key
    print("Generating RSA 2048 key pair...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # 2. Serialize private key to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    private_key_path = os.path.join(esignet_dir, "private_key.pem")
    with open(private_key_path, "w") as f:
        f.write(private_pem)
    print(f"Saved private key to {private_key_path}")
    
    # 3. Get public numbers for JWK
    public_key = private_key.public_key()
    numbers = public_key.public_numbers()
    
    def int_to_b64url(val):
        hex_val = hex(val)[2:]
        if len(hex_val) % 2 != 0:
            hex_val = '0' + hex_val
        b = bytes.fromhex(hex_val)
        return base64.urlsafe_b64encode(b).decode('utf-8').rstrip('=')
    
    n_b64 = int_to_b64url(numbers.n)
    e_b64 = int_to_b64url(numbers.e)
    
    jwk = {
        "kty": "RSA",
        "kid": "govtender-local-key",
        "use": "sig",
        "alg": "RS256",
        "n": n_b64,
        "e": e_b64
    }
    
    jwk_str = json.dumps(jwk)
    jwk_path = os.path.join(esignet_dir, "public_key.jwk")
    with open(jwk_path, "w") as f:
        f.write(jwk_str)
    print(f"Saved public key JWK to {jwk_path}")
    
    # Calculate SHA-256 hash of JWK
    public_key_hash = hashlib.sha256(jwk_str.encode('utf-8')).hexdigest()
    print(f"Generated public key hash: {public_key_hash}")
    
    # 4. Generate init.sql from template
    init_template = """-- eSignet DB Initialization
CREATE DATABASE mosip_esignet;
CREATE DATABASE mosip_mockidentitysystem;

\\c mosip_esignet postgres

DROP SCHEMA IF EXISTS esignet CASCADE;
CREATE SCHEMA esignet;
ALTER SCHEMA esignet OWNER TO postgres;
ALTER DATABASE mosip_esignet SET search_path TO esignet,pg_catalog,public;

CREATE TABLE esignet.client_detail(
	id varchar(100) NOT NULL,
	name varchar(600) NOT NULL,
	rp_id varchar(100) NOT NULL,
	logo_uri varchar(2048) NOT NULL,
	redirect_uris varchar(2048) NOT NULL,
	claims varchar(2048) NOT NULL,
	acr_values varchar(1024) NOT NULL,
	public_key varchar(1024) NOT NULL,
	public_key_hash varchar(128) NOT NULL,
	enc_public_key varchar(1024),
	enc_public_key_hash varchar(128),
	enc_public_key_cert varchar(4000),
	grant_types varchar(512) NOT NULL,
	auth_methods varchar(512) NOT NULL,
	status varchar(20) NOT NULL,
	additional_config varchar(2048),
	cr_dtimes timestamp NOT NULL,
	upd_dtimes timestamp,
	CONSTRAINT pk_clntdtl_id PRIMARY KEY (id),
	CONSTRAINT uk_clntdtl_public_key_hash UNIQUE (public_key_hash)
);

CREATE TABLE esignet.consent_detail (
    id VARCHAR(36) NOT NULL,
    client_id VARCHAR(256) NOT NULL,
    psu_token VARCHAR(256) NOT NULL,
    claims VARCHAR(2048) NOT NULL,
    authorization_scopes VARCHAR(1024) NOT NULL,
    cr_dtimes TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expire_dtimes TIMESTAMP,
    signature VARCHAR(1024),
    hash VARCHAR(100),
    accepted_claims VARCHAR(1024),
    permitted_scopes VARCHAR(1024),
    PRIMARY KEY (id),
    CONSTRAINT unique_client_token UNIQUE (client_id, psu_token)
);

CREATE INDEX idx_consent_psu_client ON esignet.consent_detail(psu_token, client_id);

CREATE TABLE esignet.consent_history (
    id VARCHAR(36) NOT NULL,
    client_id VARCHAR(256) NOT NULL,
    psu_token VARCHAR(256) NOT NULL,
    claims VARCHAR(2048) NOT NULL,
    authorization_scopes VARCHAR(1024) NOT NULL,
    cr_dtimes TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expire_dtimes TIMESTAMP,
    signature VARCHAR(1024),
    hash VARCHAR(100),
    accepted_claims VARCHAR(1024),
    permitted_scopes VARCHAR(1024),
    PRIMARY KEY (id)
);

CREATE INDEX idx_consent_history_psu_client ON esignet.consent_history(psu_token, client_id);

INSERT INTO esignet.client_detail (
    id, name, rp_id, logo_uri, redirect_uris, claims, acr_values, 
    public_key, public_key_hash, grant_types, auth_methods, status, cr_dtimes
) VALUES (
    'govtender-local-client',
    'GovTender',
    'govtender-rp',
    'http://localhost:8080/logo.png',
    '["http://localhost:8080/auth/esignet/callback"]',
    '["openid","profile","email"]',
    '["mosip:idp:acr:generated-code","mosip:idp:acr:biometrics","mosip:idp:acr:linked-wallet","mosip:idp:acr:knowledge"]',
    '{public_key_jwk}',
    '{public_key_hash}',
    '["authorization_code"]',
    '["private_key_jwt"]',
    'ACTIVE',
    CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS esignet.key_policy_def (
    app_id VARCHAR(50) NOT NULL PRIMARY KEY,
    key_validity_duration INT NOT NULL,
    is_active BOOLEAN NOT NULL,
    pre_expire_days INT NOT NULL,
    access_allowed VARCHAR(250),
    cr_by VARCHAR(250) NOT NULL,
    cr_dtimes TIMESTAMP NOT NULL,
    upd_by VARCHAR(250),
    upd_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    del_dtimes TIMESTAMP
);

INSERT INTO esignet.key_policy_def (
    app_id, key_validity_duration, is_active, pre_expire_days, access_allowed, cr_by, cr_dtimes, is_deleted
) VALUES 
('ROOT', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('MOCK', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('MOCK_IDENTITY_SYSTEM', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('ESIGNET', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('REGISTRATION', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('PARTNER', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('IDA', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('MOCK_AUTHENTICATION_SERVICE', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('OIDC_SERVICE', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('OIDC_PARTNER', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('OIDC_CLIENT', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false)
ON CONFLICT (app_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS esignet.key_alias (
    id VARCHAR(255) PRIMARY KEY,
    app_id VARCHAR(255) NOT NULL,
    cert_thumbprint VARCHAR(255),
    cr_by VARCHAR(255),
    cr_dtimes TIMESTAMP,
    del_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    key_expire_dtimes TIMESTAMP,
    key_gen_dtimes TIMESTAMP,
    ref_id VARCHAR(255),
    status_code VARCHAR(255),
    uni_ident VARCHAR(255),
    upd_by VARCHAR(255),
    upd_dtimes TIMESTAMP
);

CREATE TABLE IF NOT EXISTS esignet.ca_cert_store (
    cert_id VARCHAR(36) NOT NULL PRIMARY KEY,
    cr_by VARCHAR(256),
    cr_dtimes TIMESTAMP,
    del_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    upd_by VARCHAR(256),
    upd_dtimes TIMESTAMP,
    ca_cert_type VARCHAR(255),
    cert_data TEXT NOT NULL,
    cert_issuer VARCHAR(255) NOT NULL,
    cert_not_after TIMESTAMP NOT NULL,
    cert_not_before TIMESTAMP NOT NULL,
    cert_serial_no VARCHAR(255),
    cert_subject VARCHAR(255) NOT NULL,
    cert_thumbprint VARCHAR(255),
    crl_uri VARCHAR(255),
    issuer_id VARCHAR(255) NOT NULL,
    partner_domain VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS esignet.data_encrypt_keystore (
    id INT NOT NULL PRIMARY KEY,
    cr_by VARCHAR(255),
    cr_dtimes TIMESTAMP,
    key VARCHAR(255),
    key_status VARCHAR(255),
    upd_by VARCHAR(255),
    upd_dtimes TIMESTAMP
);

CREATE TABLE IF NOT EXISTS esignet.key_store (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    cr_by VARCHAR(256),
    cr_dtimes TIMESTAMP,
    del_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    upd_by VARCHAR(256),
    upd_dtimes TIMESTAMP,
    certificate_data TEXT,
    master_key TEXT,
    private_key TEXT
);

CREATE TABLE IF NOT EXISTS esignet.kyc_auth (
    kyc_token VARCHAR(255) NOT NULL PRIMARY KEY,
    individual_id VARCHAR(255),
    partner_specific_user_token VARCHAR(255),
    response_time TIMESTAMP,
    transaction_id VARCHAR(255),
    validity SMALLINT,
    CONSTRAINT kyc_auth_validity_check CHECK (validity >= 0 AND validity <= 2)
);

CREATE TABLE IF NOT EXISTS esignet.partner_cert_store (
    cert_id VARCHAR(36) NOT NULL PRIMARY KEY,
    cr_by VARCHAR(256),
    cr_dtimes TIMESTAMP,
    del_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    upd_by VARCHAR(256),
    upd_dtimes TIMESTAMP,
    cert_data TEXT NOT NULL,
    cert_issuer VARCHAR(255) NOT NULL,
    cert_not_after TIMESTAMP NOT NULL,
    cert_not_before TIMESTAMP NOT NULL,
    cert_serial_no VARCHAR(255),
    cert_subject VARCHAR(255) NOT NULL,
    cert_thumbprint VARCHAR(255),
    issuer_id VARCHAR(255) NOT NULL,
    key_usage VARCHAR(255),
    organization_name VARCHAR(255),
    partner_domain VARCHAR(255) NOT NULL,
    signed_cert_data TEXT
);

CREATE TABLE IF NOT EXISTS esignet.partner_data (
    partner_id VARCHAR(255) NOT NULL PRIMARY KEY,
    client_id VARCHAR(255),
    cr_dtimes TIMESTAMP,
    public_key TEXT,
    status VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS esignet.verified_claim (
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    claim VARCHAR(255),
    cr_dtimes TIMESTAMP,
    cr_by VARCHAR(255),
    detail VARCHAR(255),
    individual_id VARCHAR(255),
    is_active BOOLEAN,
    trust_framework VARCHAR(255),
    upd_dtimes TIMESTAMP
);


\\c mosip_mockidentitysystem postgres
CREATE SCHEMA IF NOT EXISTS mockidentitysystem AUTHORIZATION postgres;

CREATE TABLE IF NOT EXISTS mockidentitysystem.mock_identity (
    individual_id VARCHAR(128) NOT NULL PRIMARY KEY,
    identity_json TEXT NOT NULL
);

INSERT INTO mockidentitysystem.mock_identity(individual_id, identity_json) 
VALUES ('8267411571', '{"individualId": "8267411571", "pin": "111111", "fullName": [{"language": "eng", "value": "Sarah Connor"}], "email": "sconnor@cyberdyne.com", "gender": "Female"}')
ON CONFLICT (individual_id) DO NOTHING;

INSERT INTO mockidentitysystem.mock_identity(individual_id, identity_json) 
VALUES ('8267411572', '{"individualId": "8267411572", "pin": "111111", "fullName": [{"language": "eng", "value": "Officer Jane Doe"}], "email": "jane.doe@infrastructure.gov", "gender": "Female"}')
ON CONFLICT (individual_id) DO NOTHING;

INSERT INTO mockidentitysystem.mock_identity(individual_id, identity_json) 
VALUES ('8267411573', '{"individualId": "8267411573", "pin": "111111", "fullName": [{"language": "eng", "value": "Auditor Arthur Dent"}], "email": "arthur.dent@auditor.gov", "gender": "Male"}')
ON CONFLICT (individual_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS mockidentitysystem.key_policy_def (
    app_id VARCHAR(50) NOT NULL PRIMARY KEY,
    key_validity_duration INT NOT NULL,
    is_active BOOLEAN NOT NULL,
    pre_expire_days INT NOT NULL,
    access_allowed VARCHAR(250),
    cr_by VARCHAR(250) NOT NULL,
    cr_dtimes TIMESTAMP NOT NULL,
    upd_by VARCHAR(250),
    upd_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    del_dtimes TIMESTAMP
);

INSERT INTO mockidentitysystem.key_policy_def (
    app_id, key_validity_duration, is_active, pre_expire_days, access_allowed, cr_by, cr_dtimes, is_deleted
) VALUES 
('ROOT', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('MOCK', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('MOCK_IDENTITY_SYSTEM', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('ESIGNET', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('REGISTRATION', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('PARTNER', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('IDA', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('MOCK_AUTHENTICATION_SERVICE', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('OIDC_SERVICE', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('OIDC_PARTNER', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false),
('OIDC_CLIENT', 1095, true, 60, 'NA', 'mosipadmin', CURRENT_TIMESTAMP, false)
ON CONFLICT (app_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS mockidentitysystem.key_alias (
    id VARCHAR(255) PRIMARY KEY,
    app_id VARCHAR(255) NOT NULL,
    cert_thumbprint VARCHAR(255),
    cr_by VARCHAR(255),
    cr_dtimes TIMESTAMP,
    del_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    key_expire_dtimes TIMESTAMP,
    key_gen_dtimes TIMESTAMP,
    ref_id VARCHAR(255),
    status_code VARCHAR(255),
    uni_ident VARCHAR(255),
    upd_by VARCHAR(255),
    upd_dtimes TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mockidentitysystem.ca_cert_store (
    cert_id VARCHAR(36) NOT NULL PRIMARY KEY,
    cr_by VARCHAR(256),
    cr_dtimes TIMESTAMP,
    del_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    upd_by VARCHAR(256),
    upd_dtimes TIMESTAMP,
    ca_cert_type VARCHAR(255),
    cert_data TEXT NOT NULL,
    cert_issuer VARCHAR(255) NOT NULL,
    cert_not_after TIMESTAMP NOT NULL,
    cert_not_before TIMESTAMP NOT NULL,
    cert_serial_no VARCHAR(255),
    cert_subject VARCHAR(255) NOT NULL,
    cert_thumbprint VARCHAR(255),
    crl_uri VARCHAR(255),
    issuer_id VARCHAR(255) NOT NULL,
    partner_domain VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS mockidentitysystem.data_encrypt_keystore (
    id INT NOT NULL PRIMARY KEY,
    cr_by VARCHAR(255),
    cr_dtimes TIMESTAMP,
    key VARCHAR(255),
    key_status VARCHAR(255),
    upd_by VARCHAR(255),
    upd_dtimes TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mockidentitysystem.key_store (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    cr_by VARCHAR(256),
    cr_dtimes TIMESTAMP,
    del_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    upd_by VARCHAR(256),
    upd_dtimes TIMESTAMP,
    certificate_data TEXT,
    master_key TEXT,
    private_key TEXT
);

CREATE TABLE IF NOT EXISTS mockidentitysystem.kyc_auth (
    kyc_token VARCHAR(255) NOT NULL PRIMARY KEY,
    individual_id VARCHAR(255),
    partner_specific_user_token VARCHAR(255),
    response_time TIMESTAMP,
    transaction_id VARCHAR(255),
    validity SMALLINT,
    CONSTRAINT kyc_auth_validity_check CHECK (validity >= 0 AND validity <= 2)
);

CREATE TABLE IF NOT EXISTS mockidentitysystem.partner_cert_store (
    cert_id VARCHAR(36) NOT NULL PRIMARY KEY,
    cr_by VARCHAR(256),
    cr_dtimes TIMESTAMP,
    del_dtimes TIMESTAMP,
    is_deleted BOOLEAN,
    upd_by VARCHAR(256),
    upd_dtimes TIMESTAMP,
    cert_data TEXT NOT NULL,
    cert_issuer VARCHAR(255) NOT NULL,
    cert_not_after TIMESTAMP NOT NULL,
    cert_not_before TIMESTAMP NOT NULL,
    cert_serial_no VARCHAR(255),
    cert_subject VARCHAR(255) NOT NULL,
    cert_thumbprint VARCHAR(255),
    issuer_id VARCHAR(255) NOT NULL,
    key_usage VARCHAR(255),
    organization_name VARCHAR(255),
    partner_domain VARCHAR(255) NOT NULL,
    signed_cert_data TEXT
);

CREATE TABLE IF NOT EXISTS mockidentitysystem.partner_data (
    partner_id VARCHAR(255) NOT NULL PRIMARY KEY,
    client_id VARCHAR(255),
    cr_dtimes TIMESTAMP,
    public_key TEXT,
    status VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS mockidentitysystem.verified_claim (
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    claim VARCHAR(255),
    cr_dtimes TIMESTAMP,
    cr_by VARCHAR(255),
    detail VARCHAR(255),
    individual_id VARCHAR(255),
    is_active BOOLEAN,
    trust_framework VARCHAR(255),
    upd_dtimes TIMESTAMP
);
"""
    
    # Escape single quotes in JSON string for SQL
    escaped_jwk = jwk_str.replace("'", "''")
    init_sql = init_template.replace("{public_key_jwk}", escaped_jwk).replace("{public_key_hash}", public_key_hash)
    
    init_sql_path = os.path.join(esignet_dir, "init.sql")
    with open(init_sql_path, "w") as f:
        f.write(init_sql)
    print(f"Generated DB init script at {init_sql_path}")
    
    # 5. Patch .env
    backend_dir = os.path.abspath(os.path.join(esignet_dir, "..", "backend"))
    env_path = os.path.join(backend_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
            
        new_lines = []
        skip_keys = ["ESIGNET_BASE_URL", "ESIGNET_CLIENT_ID", "ESIGNET_CLIENT_SECRET", "ESIGNET_REDIRECT_URI", "ESIGNET_PRIVATE_KEY_PATH"]
        for line in lines:
            stripped = line.strip()
            # If the line starts with any of the keys, skip it
            if any(stripped.startswith(f"{key}=") for key in skip_keys):
                continue
            new_lines.append(line)
            
        # Add new configurations
        new_lines.append("\n# --- Local eSignet Sandbox Configurations ---\n")
        new_lines.append("ESIGNET_BASE_URL=http://localhost:8088\n")
        new_lines.append("ESIGNET_CLIENT_ID=govtender-local-client\n")
        new_lines.append("ESIGNET_CLIENT_SECRET=\n")
        new_lines.append("ESIGNET_REDIRECT_URI=http://localhost:8080/auth/esignet/callback\n")
        new_lines.append("ESIGNET_PRIVATE_KEY_PATH=esignet/private_key.pem\n")
        
        with open(env_path, "w") as f:
            f.writelines(new_lines)
        print(f"Successfully patched backend .env file at {env_path}")
    else:
        print(f"Warning: backend .env file not found at {env_path}")

if __name__ == "__main__":
    main()

"""
OCI Token Exchange - GitHub OIDC to OCI Session Token

This script exchanges a GitHub OIDC JWT token for an OCI session token,
enabling passwordless authentication from GitHub Actions to OCI.

Flow:
  1. Generate RSA key pair (for signing OCI API requests)
  2. Request OIDC token from GitHub
  3. Exchange OIDC token for OCI session token
  4. Configure OCI CLI with the session token
  5. (Optional) Start background daemon to refresh token

Required environment variables (set by action.yml):
  - INPUT_OIDC_CLIENT_IDENTIFIER: OAuth client credentials (client_id:client_secret)
  - INPUT_DOMAIN_BASE_URL: OCI Identity Domain URL
  - INPUT_OCI_TENANCY: OCI Tenancy OCID
  - INPUT_OCI_REGION: OCI Region

Optional:
  - INPUT_ENABLE_TOKEN_REFRESH: "true" to enable background refresh (for long jobs)
  - INPUT_REFRESH_INTERVAL_MINUTES: Minutes between refreshes (default: 50)

GitHub-provided (automatic when id-token: write permission is set):
  - ACTIONS_ID_TOKEN_REQUEST_URL: GitHub OIDC endpoint
  - ACTIONS_ID_TOKEN_REQUEST_TOKEN: Authorization token for OIDC request
"""

import os
import sys
import time
import base64
import hashlib
import subprocess
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


def get_env(name):
    # Helper to get env vars
    value = os.environ.get(name)
    if not value:
        print(f"Error: Variable '{name}' is missing.")
        sys.exit(1)
    return value


def do_token_exchange():
    # Read config
    client_creds = get_env("INPUT_OIDC_CLIENT_IDENTIFIER")
    domain_url = get_env("INPUT_DOMAIN_BASE_URL").rstrip("/")
    tenancy = get_env("INPUT_OCI_TENANCY")
    region = get_env("INPUT_OCI_REGION")

    # Use user's home dir
    home = os.environ.get("HOME", "/root")

    # 1. Generate Keys
    print("\n[Step 1] Generating keys...")

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    public_b64 = base64.b64encode(public_der).decode()

    # Calculate fingerprint the simple way
    md5_hash = hashlib.md5(public_der).hexdigest()
    fingerprint_parts = []
    for i in range(0, len(md5_hash), 2):
        fingerprint_parts.append(md5_hash[i:i+2])
    fingerprint = ":".join(fingerprint_parts)

    print(f"  Fingerprint: {fingerprint}")

    # 2. Get GitHub Token
    print("\n[Step 2] Getting GitHub token...")

    oidc_url = get_env("ACTIONS_ID_TOKEN_REQUEST_URL") + "&audience=https://cloud.oracle.com"
    oidc_token = get_env("ACTIONS_ID_TOKEN_REQUEST_TOKEN")

    headers = {"Authorization": f"Bearer {oidc_token}"}
    response = requests.get(oidc_url, headers=headers)

    if response.status_code != 200:
        print("Error getting GitHub token")
        print(response.text)
        sys.exit(1)

    github_jwt = response.json()["value"]
    print("  Got GitHub token")

    # 3. Exchange for OCI Token
    print("\n[Step 3] Exchanging with OCI...")

    auth_header = "Basic " + base64.b64encode(client_creds.encode()).decode()

    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "requested_token_type": "urn:oci:token-type:oci-upst",
        "public_key": public_b64,
        "subject_token": github_jwt,
        "subject_token_type": "jwt"
    }

    response = requests.post(
        f"{domain_url}/oauth2/v1/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": auth_header
        },
        data=data
    )

    if response.status_code != 200:
        print("Error exchanging token with OCI")
        print(response.text)
        sys.exit(1)

    session_token = response.json().get("token")
    print("  Got OCI session token")

    # 4. Configure CLI
    print("\n[Step 4] Writing config...")

    oci_dir = os.path.join(home, ".oci")
    if not os.path.exists(oci_dir):
        os.makedirs(oci_dir)

    key_path = os.path.join(oci_dir, "session_key.pem")
    token_path = os.path.join(oci_dir, "session_token")
    config_path = os.path.join(oci_dir, "config")

    # Save key
    with open(key_path, "wb") as f:
        f.write(private_pem)
    os.chmod(key_path, 0o600)

    # Save token
    with open(token_path, "w") as f:
        f.write(session_token)
    os.chmod(token_path, 0o600)

    # Save config
    config_content = f"""[DEFAULT]
user={tenancy}
fingerprint={fingerprint}
key_file={key_path}
tenancy={tenancy}
region={region}
security_token_file={token_path}
"""
    with open(config_path, "w") as f:
        f.write(config_content)
    os.chmod(config_path, 0o600)

    print(f"  Config saved to {config_path}")


def run_daemon(interval):
    print(f"Daemon started. Sleeping {interval} minutes...")
    while True:
        time.sleep(int(interval) * 60)
        try:
            print("Refreshing token...")
            do_token_exchange()
            print("Done.")
        except Exception as e:
            print(f"Error refreshing: {e}")


if __name__ == "__main__":
    # Check if daemon mode
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        interval = os.environ.get("INPUT_REFRESH_INTERVAL_MINUTES", "50")
        run_daemon(interval)
        sys.exit(0)

    # Normal run
    print("--- OCI Token Exchange ---")
    do_token_exchange()

    # Auto-refresh check
    refresh = os.environ.get("INPUT_ENABLE_TOKEN_REFRESH", "false")
    if refresh.lower() == "true":
        interval = os.environ.get("INPUT_REFRESH_INTERVAL_MINUTES", "50")
        print(f"\nStarting background refresh (every {interval} mins)...")

        # Start detached process
        subprocess.Popen(
            [sys.executable, __file__, "--daemon"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    print("\nDone! OCI CLI is ready.")


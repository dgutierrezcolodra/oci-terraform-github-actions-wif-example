from __future__ import annotations

import importlib.util
import io
import os
import pathlib
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ACTION = PROJECT_ROOT / "ansible-oci-wif" / "main.py"


def load_action_module() -> object:
    specification = importlib.util.spec_from_file_location("ansible_oci_wif", ACTION)
    if specification is None or specification.loader is None:
        raise RuntimeError("Unable to load the Ansible OCI WIF helper")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class FakePrivateKey:
    def private_bytes(self, encoding: object, private_format: object, encryption_algorithm: object) -> bytes:
        return b"-----BEGIN PRIVATE KEY-----\nfake-private-key\n-----END PRIVATE KEY-----\n"


class FakeTokenExchangeSigner:
    def __init__(
        self,
        jwt_or_func: object,
        oci_domain_url: str,
        client_id: str,
        client_secret: str,
        region: str,
    ) -> None:
        self.jwt_or_func = jwt_or_func
        self.oci_domain_url = oci_domain_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.security_token = "sensitive-security-token"
        self.private_key = FakePrivateKey()

    def get_security_token(self) -> str:
        return self.security_token


class AnsibleOciWifTest(unittest.TestCase):
    def test_writes_protected_security_token_credentials_without_printing_token(self) -> None:
        action = load_action_module()

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = pathlib.Path(temporary_dir)
            jwt_path = root / "github-oidc.jwt"
            jwt_path.write_text("github-oidc-token", encoding="utf-8")
            environment_file = root / "github-env"
            environment_file.touch()
            output = io.StringIO()

            with patch.dict(
                os.environ,
                {
                    "OCI_WORKLOAD_IDENTITY_TOKEN_PATH": str(jwt_path),
                    "OCI_TOKEN_EXCHANGE_DOMAIN_URL": "https://example.identity.oraclecloud.com",
                    "OCI_TOKEN_EXCHANGE_CLIENT_ID": "client-id",
                    "OCI_TOKEN_EXCHANGE_CLIENT_SECRET": "client-secret",
                    "OCI_REGION": "eu-madrid-1",
                    "RUNNER_TEMP": str(root),
                    "GITHUB_ENV": str(environment_file),
                },
                clear=True,
            ):
                with redirect_stdout(output):
                    with patch.object(
                        action,
                        "serialize_private_key",
                        return_value=b"-----BEGIN PRIVATE KEY-----\nfake-private-key\n-----END PRIVATE KEY-----\n",
                    ):
                        action.main(token_exchange_signer=FakeTokenExchangeSigner)

            credentials_dir = root.resolve() / "oci-ansible-wif"
            security_token_path = credentials_dir / "security_token"
            private_key_path = credentials_dir / "private_key.pem"
            config_path = credentials_dir / "config"

            self.assertEqual(security_token_path.read_text(encoding="utf-8"), "sensitive-security-token")
            self.assertEqual(
                private_key_path.read_text(encoding="utf-8"),
                "-----BEGIN PRIVATE KEY-----\nfake-private-key\n-----END PRIVATE KEY-----\n",
            )
            config = config_path.read_text(encoding="utf-8")
            self.assertIn(f"security_token_file={security_token_path}", config)
            self.assertIn(f"key_file={private_key_path}", config)
            self.assertEqual(
                environment_file.read_text(encoding="utf-8"),
                f"OCI_CONFIG_FILE={config_path}\nOCI_ANSIBLE_AUTH_TYPE=security_token\n",
            )
            for path in (security_token_path, private_key_path, config_path):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertNotIn("sensitive-security-token", output.getvalue())


if __name__ == "__main__":
    unittest.main()

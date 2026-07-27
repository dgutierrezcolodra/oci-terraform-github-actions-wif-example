#!/usr/bin/env python3
"""Create ephemeral OCI security-token credentials for the OCI Ansible collection."""

from __future__ import annotations

import os
import pathlib
import tempfile
from collections.abc import Callable
from typing import Any


def required_env(name: str) -> str:
    """Return a required environment value without exposing its contents."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def required_config_value(name: str) -> str:
    """Reject values that could inject another OCI config setting."""
    value = required_env(name)
    if "\n" in value or "\r" in value:
        raise RuntimeError(f"Invalid value for environment variable: {name}")
    return value


def source_jwt_reader(path: pathlib.Path) -> Callable[[], str]:
    """Return a callback so the SDK reads the current source JWT from disk."""
    if not path.is_file():
        raise RuntimeError("OCI_WORKLOAD_IDENTITY_TOKEN_PATH must name a file")

    def read_jwt() -> str:
        token = path.read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError("OCI workload identity token file is empty")
        return token

    return read_jwt


def atomic_write(path: pathlib.Path, content: str | bytes) -> None:
    """Atomically write a protected credential file."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        if isinstance(content, bytes):
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def serialize_private_key(private_key: Any) -> bytes:
    """Serialize the signer's ephemeral proof-of-possession key as PEM."""
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

    return private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())


def append_command_values(variable: str, values: dict[str, pathlib.Path | str]) -> None:
    """Append non-secret paths or environment settings to a GitHub command file."""
    command_file = os.environ.get(variable)
    if not command_file:
        return

    rendered_values = {name: str(value) for name, value in values.items()}
    if any("\n" in value or "\r" in value for value in rendered_values.values()):
        raise RuntimeError(f"Invalid value for GitHub command file: {variable}")

    with open(command_file, "a", encoding="utf-8") as stream:
        for name, value in rendered_values.items():
            stream.write(f"{name}={value}\n")


def create_signer(jwt_reader: Callable[[], str]) -> Any:
    """Construct the OCI SDK signer without ever persisting client credentials."""
    try:
        from oci.auth.signers import TokenExchangeSigner
    except ImportError as exc:
        raise RuntimeError("The OCI Python SDK is required to exchange the workload identity token") from exc

    return TokenExchangeSigner(
        jwt_or_func=jwt_reader,
        oci_domain_url=required_config_value("OCI_TOKEN_EXCHANGE_DOMAIN_URL"),
        client_id=required_config_value("OCI_TOKEN_EXCHANGE_CLIENT_ID"),
        client_secret=required_config_value("OCI_TOKEN_EXCHANGE_CLIENT_SECRET"),
        region=required_config_value("OCI_REGION"),
    )


def main(token_exchange_signer: Callable[..., Any] | None = None) -> None:
    """Exchange the GitHub JWT and write OCI collection-compatible credentials."""
    runner_temp = pathlib.Path(required_env("RUNNER_TEMP")).resolve()
    credentials_dir = runner_temp / "oci-ansible-wif"
    source_token_path = pathlib.Path(required_env("OCI_WORKLOAD_IDENTITY_TOKEN_PATH")).resolve()
    jwt_reader = source_jwt_reader(source_token_path)
    signer = token_exchange_signer(
        jwt_or_func=jwt_reader,
        oci_domain_url=required_config_value("OCI_TOKEN_EXCHANGE_DOMAIN_URL"),
        client_id=required_config_value("OCI_TOKEN_EXCHANGE_CLIENT_ID"),
        client_secret=required_config_value("OCI_TOKEN_EXCHANGE_CLIENT_SECRET"),
        region=required_config_value("OCI_REGION"),
    ) if token_exchange_signer else create_signer(jwt_reader)

    security_token_path = credentials_dir / "security_token"
    private_key_path = credentials_dir / "private_key.pem"
    config_path = credentials_dir / "config"
    security_token = signer.get_security_token()
    if not isinstance(security_token, str) or not security_token:
        raise RuntimeError("OCI token exchange did not return a security token")

    atomic_write(security_token_path, security_token)
    atomic_write(private_key_path, serialize_private_key(signer.private_key))
    atomic_write(
        config_path,
        "[DEFAULT]\n"
        f"region={required_config_value('OCI_REGION')}\n"
        f"security_token_file={security_token_path}\n"
        f"key_file={private_key_path}\n",
    )
    append_command_values(
        "GITHUB_ENV",
        {
            "OCI_CONFIG_FILE": config_path,
            "OCI_ANSIBLE_AUTH_TYPE": "security_token",
            "OCI_ANSIBLE_SECURITY_TOKEN_FILE": security_token_path,
            "OCI_ANSIBLE_PRIVATE_KEY_FILE": private_key_path,
        },
    )
    append_command_values(
        "GITHUB_OUTPUT",
        {
            "config_path": config_path,
            "security_token_path": security_token_path,
            "private_key_path": private_key_path,
        },
    )
    print("Ephemeral OCI Ansible security-token credentials created")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        raise SystemExit(f"Error: {exc}") from exc

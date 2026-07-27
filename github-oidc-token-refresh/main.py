#!/usr/bin/env python3
"""Write refreshable GitHub OIDC token material for OCI Terraform WIF.

This action never calls OCI and never creates an OCI UPST or RSA key. The OCI
Terraform provider owns those values so token and proof-of-possession key
rotation remain synchronized.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


MINIMUM_REMAINING_SECONDS = 60
EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def token_path() -> pathlib.Path:
    runner_temp = pathlib.Path(required_env("RUNNER_TEMP")).resolve()
    configured = os.environ.get("INPUT_TOKEN_PATH", "").strip()
    if configured:
        path = pathlib.Path(configured).expanduser()
        if not path.is_absolute():
            raise RuntimeError("INPUT_TOKEN_PATH must be absolute")
    else:
        path = runner_temp / "oci-wif" / "github-oidc.jwt"
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(runner_temp)
    except ValueError as exc:
        raise RuntimeError(
            "INPUT_TOKEN_PATH must be inside RUNNER_TEMP and not equal to RUNNER_TEMP"
        ) from exc
    if relative_path == pathlib.Path("."):
        raise RuntimeError(
            "INPUT_TOKEN_PATH must be inside RUNNER_TEMP and not equal to RUNNER_TEMP"
        )
    return resolved_path


def oidc_url(audience: str) -> str:
    parsed = urllib.parse.urlsplit(required_env("ACTIONS_ID_TOKEN_REQUEST_URL"))
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["audience"] = audience
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def decode_claims_without_verification(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise RuntimeError("GitHub returned a value that is not a three-part JWT")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("GitHub returned a JWT with an invalid payload") from exc
    if not isinstance(claims, dict):
        raise RuntimeError("GitHub returned a JWT payload that is not an object")
    return claims


def fetch_token(audience: str) -> tuple[str, int]:
    request = urllib.request.Request(
        oidc_url(audience),
        headers={"Authorization": f"Bearer {required_env('ACTIONS_ID_TOKEN_REQUEST_TOKEN')}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub OIDC endpoint returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("GitHub OIDC endpoint could not be reached") from exc

    token = result.get("value") if isinstance(result, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("GitHub OIDC response does not contain a token")

    claims = decode_claims_without_verification(token)
    try:
        expires_at = int(claims.get("exp", 0))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("GitHub OIDC JWT has an invalid exp claim") from exc
    remaining = expires_at - int(time.time())
    if remaining <= MINIMUM_REMAINING_SECONDS:
        raise RuntimeError("GitHub OIDC JWT expires in less than 60 seconds")
    if claims.get("iss") != EXPECTED_ISSUER:
        raise RuntimeError("GitHub OIDC JWT issuer is not the expected GitHub issuer")
    if claims.get("aud") != audience:
        raise RuntimeError("GitHub OIDC JWT audience does not match the requested audience")
    return token, remaining


def atomic_write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
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


def append_command_file(variable: str, value: str) -> None:
    command_file = os.environ.get(variable, "").strip()
    if command_file:
        with open(command_file, "a", encoding="utf-8") as stream:
            stream.write(f"token_path={value}\n" if variable == "GITHUB_OUTPUT" else f"OCI_WORKLOAD_IDENTITY_TOKEN_PATH={value}\n")


def refresh_once(path: pathlib.Path, audience: str) -> int:
    token, remaining = fetch_token(audience)
    atomic_write(path, token)
    return remaining


def refresh_forever(path: pathlib.Path, audience: str, interval_minutes: int) -> None:
    interval_seconds = interval_minutes * 60
    wait_seconds = interval_seconds
    while True:
        time.sleep(wait_seconds)
        try:
            refresh_once(path, audience)
            wait_seconds = interval_seconds
        except Exception:
            # Keep the previous valid file and retry quickly. Terraform will fail
            # closed if no valid source JWT is available for its next exchange.
            wait_seconds = min(30, interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    args = parser.parse_args()

    path = token_path()
    audience = os.environ.get("INPUT_AUDIENCE", "https://cloud.oracle.com").strip()
    if not audience:
        raise RuntimeError("INPUT_AUDIENCE cannot be empty")
    try:
        interval = int(os.environ.get("INPUT_REFRESH_INTERVAL_MINUTES", "3"))
    except ValueError as exc:
        raise RuntimeError("Refresh interval must be an integer") from exc
    if not 1 <= interval <= 4:
        raise RuntimeError(
            "Refresh interval must be between 1 and 4 minutes: GitHub OIDC JWTs "
            "expire after roughly 5 minutes, so longer intervals leave an "
            "expired source token on disk"
        )

    if args.daemon:
        refresh_forever(path, audience, interval)
        return

    remaining = refresh_once(path, audience)
    append_command_file("GITHUB_OUTPUT", str(path))
    append_command_file("GITHUB_ENV", str(path))
    print(f"GitHub OIDC token file created with {remaining} seconds remaining")

    refresh_enabled = os.environ.get("INPUT_ENABLE_TOKEN_REFRESH", "false").lower() == "true"
    if refresh_enabled:
        subprocess.Popen(
            [sys.executable, str(pathlib.Path(__file__).resolve()), "--daemon"],
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print(f"GitHub OIDC token-file refresh enabled every {interval} minutes")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        raise SystemExit(f"Error: {exc}") from exc

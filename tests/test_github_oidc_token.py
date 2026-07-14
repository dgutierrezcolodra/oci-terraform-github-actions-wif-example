from __future__ import annotations

import base64
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ACTION = PROJECT_ROOT / "github-oidc-token" / "main.py"


def segment(value: dict[str, object]) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(value).encode("utf-8"))
    return encoded.rstrip(b"=").decode("ascii")


class OidcHandler(BaseHTTPRequestHandler):
    authorization = ""
    audience = ""

    def do_GET(self) -> None:  # noqa: N802 - inherited API name
        type(self).authorization = self.headers.get("Authorization", "")
        type(self).audience = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)["audience"][0]
        token = ".".join(
            (
                segment({"alg": "RS256"}),
                segment(
                    {
                        "iss": "https://token.actions.githubusercontent.com",
                        "aud": type(self).audience,
                        "exp": int(time.time()) + 600,
                    }
                ),
                "signature",
            )
        )
        body = json.dumps({"value": token}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class GitHubOidcTokenTest(unittest.TestCase):
    def test_writes_protected_token_and_github_command_files(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), OidcHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = pathlib.Path(temporary_dir)
            output_file = root / "github-output"
            env_file = root / "github-env"
            output_file.touch()
            env_file.touch()
            env = os.environ.copy()
            env.update(
                {
                    "ACTIONS_ID_TOKEN_REQUEST_URL": f"http://127.0.0.1:{server.server_port}/oidc?api-version=1",
                    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-token",
                    "GITHUB_OUTPUT": str(output_file),
                    "GITHUB_ENV": str(env_file),
                    "RUNNER_TEMP": str(root),
                    "INPUT_AUDIENCE": "https://cloud.oracle.com",
                    "INPUT_ENABLE_TOKEN_REFRESH": "false",
                }
            )
            result = subprocess.run(
                [sys.executable, str(ACTION)],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            token_path = (root / "oci-wif" / "github-oidc.jwt").resolve()
            self.assertEqual(OidcHandler.authorization, "Bearer request-token")
            self.assertEqual(OidcHandler.audience, "https://cloud.oracle.com")
            self.assertEqual(stat.S_IMODE(token_path.stat().st_mode), 0o600)
            self.assertIn(f"token_path={token_path}", output_file.read_text(encoding="utf-8"))
            self.assertIn(
                f"OCI_WORKLOAD_IDENTITY_TOKEN_PATH={token_path}",
                env_file.read_text(encoding="utf-8"),
            )
            self.assertNotIn(token_path.read_text(encoding="utf-8"), result.stdout)


if __name__ == "__main__":
    unittest.main()

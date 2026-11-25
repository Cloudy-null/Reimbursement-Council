"""A small HTTP client for the running website, used by the live test (live-test command).

It does what a member's browser does: upload files with consent, send the claim from the check
step, and fetch the claim's export. Standard library only.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

PATIENT_OPTION = re.compile(r'<select[^>]*name="patient".*?<option[^>]*value="([^"]+)"', re.S)
CLAIM_PATH = re.compile(r"/claims/([0-9a-f-]{36})")


class WebClientError(Exception):
    """The website answered with an error, or not in the way a member's browser expects."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class WebClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect)

    def _send(self, request: urllib.request.Request) -> tuple[int, dict[str, str], bytes]:
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as error:  # 3xx land here too (no redirects followed)
            return error.code, dict(error.headers), error.read()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise WebClientError(
                f"the website at {self.base_url} did not answer: {error}"
            ) from error

    def first_patient(self) -> str:
        status, _, body = self._send(urllib.request.Request(f"{self.base_url}/?lang=en"))
        found = PATIENT_OPTION.search(body.decode("utf-8", "replace"))
        if status != 200 or found is None:
            raise WebClientError(f"no person to pick on the new claim page (status {status})")
        return found.group(1)

    def upload(self, patient: str, files: list[tuple[str, bytes]], lang: str) -> str:
        """POST /claims with consent; returns the new claim id from the redirect."""
        boundary = uuid.uuid4().hex
        parts: list[bytes] = []
        for name, value in (("patient", patient), ("lang", lang), ("consent", "yes")):
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n".encode()
            )
        for file_name, data in files:
            safe = file_name.replace('"', "")
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="photos"; '
                f'filename="{safe}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                + data
                + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            f"{self.base_url}/claims",
            data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        status, headers, body = self._send(request)
        location = headers.get("location") or headers.get("Location") or ""
        found = CLAIM_PATH.search(location) or CLAIM_PATH.search(body.decode("utf-8", "replace"))
        if status not in (200, 303) or found is None:
            raise WebClientError(f"upload refused (status {status}): {body[:200]!r}")
        return found.group(1)

    def submit(self, claim_id: str, lang: str) -> None:
        """POST the check step as it is, without edits (the member accepts what was read)."""
        data = urllib.parse.urlencode({"lang": lang}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/claims/{claim_id}/submit", data=data, method="POST"
        )
        status, _, body = self._send(request)
        if status != 303:
            raise WebClientError(f"send refused (status {status}): {body[:200]!r}")

    def export(self, claim_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/claims/{claim_id}/export"
        status, _, body = self._send(urllib.request.Request(url))
        if status != 200:
            raise WebClientError(f"no export (status {status}): {body[:200]!r}")
        data: Any = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict):
            raise WebClientError("the export is not a JSON object")
        return data

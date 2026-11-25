"""Talks to the local Ollama server over HTTP on this machine. Nothing is sent anywhere else.

The client only sends a prompt (and, for reading, the document image) and returns the model's
text. What the text means, and whether to trust it, is decided by the checks that call it.
"""

import base64
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from reimbursement_council.config.models import LocalModelConfig

logger = logging.getLogger(__name__)

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# (url, body) -> parsed JSON reply. Replaced in tests by a fake.
Transport = Callable[[str, dict[str, Any], float], dict[str, Any]]


class LocalModelError(Exception):
    """The local model could not be reached or gave no usable reply."""


def http_transport(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            reply: Any = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        raise LocalModelError(f"the local model did not answer: {error}") from error
    if not isinstance(reply, dict):
        raise LocalModelError("the local model reply is not a JSON object")
    return reply


class LocalModelClient:
    """One chat call to Ollama: temperature and seed from config, so the same input gives the
    same answer. Refuses any server that is not on this machine."""

    def __init__(self, config: LocalModelConfig, transport: Transport = http_transport) -> None:
        host = urlparse(config.url).hostname or ""
        if host not in LOCAL_HOSTS:
            raise ValueError(f"the local model must run on this machine, not {host!r}")
        self.config = config
        self._transport = transport

    @property
    def name(self) -> str:
        return self.config.model

    def chat(
        self,
        prompt: str,
        images: list[bytes] | None = None,
        schema: dict[str, Any] | None = None,
        system: str | None = None,
    ) -> str:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        user: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            user["images"] = [base64.b64encode(image).decode("ascii") for image in images]
        messages.append(user)
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": self.config.keep_alive,
            "options": {"temperature": self.config.temperature, "seed": self.config.seed},
        }
        if schema is not None:
            body["format"] = schema
        started = time.perf_counter()
        reply = self._transport(
            f"{self.config.url.rstrip('/')}/api/chat", body, self.config.timeout_seconds
        )
        message = reply.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise LocalModelError("the local model reply has no message text")
        logger.info(
            "local model %s answered in %.1f s (%d characters)",
            self.config.model,
            time.perf_counter() - started,
            len(content),
        )
        return content

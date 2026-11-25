"""The AI case reviewer's model call: text only, temperature and seed from config, and its own
timeout (short on the live path, longer for the golden check that may load the model)."""

import urllib.error
from typing import Any

from reimbursement_council.adapters.local_model import (
    LocalModelClient,
    LocalModelError,
    Transport,
    http_transport,
)
from reimbursement_council.config.models import LocalModelConfig


class ReviewerTimeoutError(LocalModelError):
    """The model did not answer within the reviewer's timeout."""


def _is_timeout(error: BaseException | None) -> bool:
    if isinstance(error, TimeoutError):
        return True
    return isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError)


class LocalCaseReviewer:
    def __init__(
        self,
        config: LocalModelConfig,
        timeout_seconds: float,
        transport: Transport = http_transport,
    ) -> None:
        self._client = LocalModelClient(
            config.model_copy(update={"timeout_seconds": timeout_seconds}), transport
        )
        self.prompt_version = config.prompt_version

    @property
    def name(self) -> str:
        return self._client.name

    def review(self, prompt: str, system: str, schema: dict[str, Any]) -> str:
        """The model's raw answer text. Raises ReviewerTimeoutError or LocalModelError."""
        try:
            return self._client.chat(prompt, schema=schema, system=system)
        except LocalModelError as error:
            if _is_timeout(error.__cause__):
                raise ReviewerTimeoutError(str(error)) from error
            raise

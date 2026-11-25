from typing import Any

import pytest

from reimbursement_council.adapters.local_model import LocalModelClient, LocalModelError
from reimbursement_council.config.loader import load_settings
from reimbursement_council.config.models import LocalModelConfig
from tests.factories import REPO_CONFIG


def config(url: str = "http://127.0.0.1:11434") -> LocalModelConfig:
    base = load_settings(REPO_CONFIG, env={}).local_model
    return base.model_copy(update={"url": url})


class Recorder:
    def __init__(self, reply: dict[str, Any]) -> None:
        self.reply = reply
        self.calls: list[tuple[str, dict[str, Any], float]] = []

    def __call__(self, url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
        self.calls.append((url, body, timeout))
        return self.reply


def test_repo_config_uses_temperature_zero_and_a_fixed_seed() -> None:
    local = load_settings(REPO_CONFIG, env={}).local_model
    assert local.temperature == 0.0
    assert isinstance(local.seed, int)
    assert local.model == "qwen3-vl:8b-instruct"


def test_chat_sends_temperature_seed_schema_and_images() -> None:
    fake = Recorder({"message": {"content": '{"a": 1}'}})
    client = LocalModelClient(config(), transport=fake)
    text = client.chat("read this", images=[b"\x89PNG"], schema={"type": "object"})
    assert text == '{"a": 1}'
    url, body, _ = fake.calls[0]
    assert url == "http://127.0.0.1:11434/api/chat"
    assert body["options"]["temperature"] == 0.0
    assert body["options"]["seed"] == config().seed
    assert body["options"]["num_ctx"] == config().num_ctx
    assert body["format"] == {"type": "object"}
    assert body["stream"] is False
    assert body["messages"][-1]["images"] == ["iVBORw=="]


def test_a_server_that_is_not_on_this_machine_is_refused() -> None:
    with pytest.raises(ValueError, match="this machine"):
        LocalModelClient(config("http://10.0.0.5:11434"))


def test_a_reply_without_text_is_an_error() -> None:
    client = LocalModelClient(config(), transport=Recorder({"done": True}))
    with pytest.raises(LocalModelError):
        client.chat("hello")


def test_an_unreachable_server_is_an_error() -> None:
    client = LocalModelClient(config("http://127.0.0.1:9"))
    with pytest.raises(LocalModelError):
        client.chat("hello")

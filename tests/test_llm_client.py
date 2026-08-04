import pytest

from src.llm_client import FakeLLMClient, RetryExhaustedError


def test_fake_client_returns_queued_responses_in_order():
    client = FakeLLMClient(responses=[{"a": 1}, {"a": 2}])
    assert client.complete("sys", "user1", {}) == {"a": 1}
    assert client.complete("sys", "user2", {}) == {"a": 2}


def test_fake_client_records_calls():
    client = FakeLLMClient(responses=[{"a": 1}])
    client.complete("sys-prompt", "user-prompt", {"type": "object"})
    assert client.calls[0]["system"] == "sys-prompt"
    assert client.calls[0]["user"] == "user-prompt"


def test_fake_client_raises_when_responses_exhausted():
    client = FakeLLMClient(responses=[])
    with pytest.raises(RetryExhaustedError):
        client.complete("sys", "user", {})

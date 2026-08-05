import pytest

from src.llm_client import FakeLLMClient, RetryExhaustedError, TimelyLLMClient


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


def test_timely_client_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("TIMELY_API_KEY", "sdk_live_test123")
    client = TimelyLLMClient(model="anthropic/claude-opus-4.7")
    assert client is not None  # 생성자가 예외 없이 성공하는지만 확인 (실 API 호출 없음)


def test_timely_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("TIMELY_API_KEY", raising=False)
    with pytest.raises(KeyError):
        TimelyLLMClient(model="anthropic/claude-opus-4.7")

"""Which model gets the work, and what it is actually sent.

The default matters more than the feature: a fresh clone has no key, and the
whole privacy claim is that nothing about a job search leaves the machine
unless someone chooses otherwise. These pin that the switch is the key itself,
so there is no way to end up half configured and quietly sending data out.
"""
import json

import pytest

from app.ai import llm


class FakeResponse:
    # A real response always carries a status, and `_ollama_chat` reads it to
    # tell "the model is not installed" apart from every other 404. A double
    # without one only passes for as long as nobody checks.
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture()
def sent(monkeypatch):
    """Capture the one HTTP call each helper makes."""
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "body": json, "headers": headers, "timeout": timeout})
        return FakeResponse(
            {
                "message": {"content": '{"ok":1}'},
                "choices": [{"message": {"content": '{"ok":1}'}}],
            }
        )

    monkeypatch.setattr(llm.httpx, "post", post)
    return calls


def _local(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "")
    monkeypatch.setattr(llm.settings, "llm_base_url", "")


def _remote(monkeypatch, base="https://api.groq.com/openai/v1"):
    monkeypatch.setattr(llm.settings, "llm_api_key", "sk-test")
    monkeypatch.setattr(llm.settings, "llm_base_url", base)
    monkeypatch.setattr(llm.settings, "llm_model", "llama-3.3-70b")


def test_no_key_means_the_local_model(monkeypatch, sent) -> None:
    """The state a fresh clone is in, and the one the privacy claim is about."""
    _local(monkeypatch)
    assert llm.hosted() is False
    llm.generate_json("sys", "hello")
    assert "11434" in sent[0]["url"]
    assert sent[0]["headers"] is None


def test_a_base_url_without_a_key_is_still_local(monkeypatch, sent) -> None:
    """Half configured must not mean half sent. Both or neither."""
    monkeypatch.setattr(llm.settings, "llm_api_key", "")
    monkeypatch.setattr(llm.settings, "llm_base_url", "https://api.groq.com/openai/v1")
    assert llm.hosted() is False
    llm.generate_json("sys", "hello")
    assert "11434" in sent[0]["url"]


def test_a_key_sends_the_work_to_the_hosted_model(monkeypatch, sent) -> None:
    _remote(monkeypatch)
    assert llm.hosted() is True
    llm.generate_json("sys", "hello")
    call = sent[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-test"
    assert call["body"]["model"] == "llama-3.3-70b"
    assert call["body"]["response_format"] == {"type": "json_object"}


def test_a_trailing_slash_does_not_double_up(monkeypatch, sent) -> None:
    """People paste the URL from the docs, and half of them end in a slash."""
    _remote(monkeypatch, base="https://api.groq.com/openai/v1/")
    llm.generate_json("sys", "hello")
    assert sent[0]["url"] == "https://api.groq.com/openai/v1/chat/completions"


def test_plain_text_asks_for_no_json_envelope(monkeypatch, sent) -> None:
    """LaTeX goes through generate_text so every backslash does not have to
    survive JSON escaping."""
    _remote(monkeypatch)
    llm.generate_text("sys", "hello")
    assert "response_format" not in sent[0]["body"]

    _local(monkeypatch)
    sent.clear()
    llm.generate_text("sys", "hello")
    assert "format" not in sent[0]["body"]


def test_the_local_json_flag_is_set_only_for_json(monkeypatch, sent) -> None:
    _local(monkeypatch)
    llm.generate_json("sys", "hello")
    assert sent[0]["body"]["format"] == "json"


def test_waiting_forever_is_a_local_idea_only(monkeypatch, sent) -> None:
    """timeout=None locally means "the user can watch progress". Against
    someone else's API it means a request that can hang for the life of the
    process."""
    _remote(monkeypatch)
    llm.generate_json("sys", "hello", timeout=None)
    assert sent[0]["timeout"] == 300.0

    _local(monkeypatch)
    sent.clear()
    llm.generate_json("sys", "hello", timeout=None)
    assert sent[0]["timeout"] is None


def test_both_backends_return_the_parsed_object(monkeypatch, sent) -> None:
    for configure in (_local, _remote):
        configure(monkeypatch)
        assert llm.generate_json("sys", "hello") == {"ok": 1}


def test_the_output_cap_reaches_both_backends(monkeypatch, sent) -> None:
    """Capping the answer is what stopped a resume section taking two minutes
    of padding, and it has to survive the switch."""
    _local(monkeypatch)
    llm.generate_json("sys", "hello", max_tokens=250)
    assert sent[0]["body"]["options"]["num_predict"] == 250

    _remote(monkeypatch)
    sent.clear()
    llm.generate_json("sys", "hello", max_tokens=250)
    assert sent[0]["body"]["max_tokens"] == 250


def test_the_system_prompt_is_sent_as_a_system_message(monkeypatch, sent) -> None:
    for configure in (_local, _remote):
        configure(monkeypatch)
        sent.clear()
        llm.generate_json("the rules", "the question")
        assert sent[0]["body"]["messages"] == [
            {"role": "system", "content": "the rules"},
            {"role": "user", "content": "the question"},
        ]


def test_a_key_is_never_in_a_url(monkeypatch, sent) -> None:
    """URLs end up in logs and error messages. Keys go in a header."""
    _remote(monkeypatch)
    llm.generate_json("sys", "hello")
    assert "sk-test" not in sent[0]["url"]
    assert "sk-test" not in json.dumps(sent[0]["body"])

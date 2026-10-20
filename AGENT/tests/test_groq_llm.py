from __future__ import annotations

import json

import groq
import httpx
import pytest
from groq.types.chat import ChatCompletion

from truthguard_agent.llm import GroqLLM, LLMError
from truthguard_agent.schemas import Chunk, Document, RetrievedPassage
from truthguard_agent.synthesizer import synthesize

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def completion(content="hi", finish="stop", choices=True):
    message = {"role": "assistant", "content": content}
    body = {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [{"index": 0, "finish_reason": finish, "message": message}] if choices else [],
    }
    return ChatCompletion.model_validate(body)


def status_error(cls, status, message):
    response = httpx.Response(status, request=REQUEST, json={"error": {"message": message}})
    return cls(message, response=response, body={"error": {"message": message}})


class StubCompletions:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def create(self, *, messages, model, **options):
        self.calls.append({"messages": messages, "model": model, **options})
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class StubClient:
    def __init__(self, outcome):
        self.chat = type("Chat", (), {})()
        self.chat.completions = StubCompletions(outcome)


def llm_for(outcome, **kwargs):
    client = StubClient(outcome)
    return GroqLLM("groq-test", client=client, **kwargs), client.chat.completions


def test_complete_returns_the_text_and_sends_the_model_and_both_prompts():
    llm, completions = llm_for(completion("hello"))
    assert llm.complete("be brief", "say hello") == "hello"
    call = completions.calls[0]
    assert call["model"] == "groq-test"
    assert call["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "say hello"},
    ]


def test_the_model_name_is_available_to_record_with_an_answer():
    assert llm_for(completion())[0].model_name == "groq-test"


def test_json_output_asks_for_json_object_mode_and_plain_output_does_not():
    llm, completions = llm_for(completion("{}"))
    llm.complete("s", "u", json_output=True)
    llm.complete("s", "u")
    assert completions.calls[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in completions.calls[1]


def test_the_reply_length_limit_is_sent():
    llm, completions = llm_for(completion("x"), max_output_tokens=1234)
    llm.complete("s", "u")
    assert completions.calls[0]["max_completion_tokens"] == 1234


def test_a_rate_limit_error_becomes_an_llm_error_with_the_status_and_message():
    error = status_error(groq.RateLimitError, 429, "Rate limit reached for model")
    with pytest.raises(LLMError, match=r"429.*Rate limit reached for model"):
        llm_for(error)[0].complete("s", "u")


def test_a_server_error_a_timeout_and_a_lost_connection_also_become_llm_errors():
    with pytest.raises(LLMError, match="503.*over capacity"):
        llm_for(status_error(groq.InternalServerError, 503, "over capacity"))[0].complete("s", "u")
    with pytest.raises(LLMError, match="APITimeoutError"):
        llm_for(groq.APITimeoutError(request=REQUEST))[0].complete("s", "u")
    with pytest.raises(LLMError, match="APIConnectionError"):
        llm_for(groq.APIConnectionError(request=REQUEST))[0].complete("s", "u")


def test_a_value_error_from_the_sdk_becomes_an_llm_error_but_ctrl_c_does_not():
    with pytest.raises(LLMError, match="bad config"):
        llm_for(ValueError("bad config"))[0].complete("s", "u")
    with pytest.raises(KeyboardInterrupt):
        llm_for(KeyboardInterrupt())[0].complete("s", "u")


def test_a_reply_cut_off_by_the_length_limit_is_an_llm_error_not_a_half_answer():
    with pytest.raises(LLMError, match="cut off"):
        llm_for(completion('{"claims": [', finish="length"))[0].complete("s", "u")


@pytest.mark.parametrize("finish", ["tool_calls", "function_call"])
def test_a_reply_that_did_not_stop_normally_is_an_llm_error(finish):
    with pytest.raises(LLMError, match="stopped"):
        llm_for(completion("partial", finish=finish))[0].complete("s", "u")


def test_a_normal_stop_returns_the_text():
    assert llm_for(completion("fine", finish="stop"))[0].complete("s", "u") == "fine"


@pytest.mark.parametrize(
    "outcome, message",
    [
        (completion(choices=False), "no choice"),
        (completion(None), "empty reply"),
        (completion("   "), "empty reply"),
    ],
    ids=["no-choices", "no-text", "blank"],
)
def test_a_reply_with_no_text_is_an_llm_error(outcome, message):
    with pytest.raises(LLMError, match=message):
        llm_for(outcome)[0].complete("s", "u")


def test_without_an_api_key_building_the_client_fails_clearly(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqLLM("groq-test")


@pytest.fixture()
def sdk_client_kwargs(monkeypatch):
    seen = {}

    class FakeSdkClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr("groq.Groq", FakeSdkClient)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    return seen


def test_the_sdk_client_gets_the_key_and_a_timeout_in_seconds(sdk_client_kwargs):
    GroqLLM("groq-test", api_key="the-key", timeout_seconds=12.5)
    assert sdk_client_kwargs["api_key"] == "the-key"
    assert sdk_client_kwargs["timeout"] == 12.5


def test_one_complete_call_is_one_request_because_the_sdk_does_not_retry(sdk_client_kwargs):
    GroqLLM("groq-test", api_key="the-key")
    assert sdk_client_kwargs["max_retries"] == 0


def test_the_key_can_come_from_the_environment_and_an_explicit_key_beats_it(sdk_client_kwargs, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    GroqLLM("groq-test")
    assert sdk_client_kwargs["api_key"] == "env-key"
    GroqLLM("groq-test", api_key="explicit-key")
    assert sdk_client_kwargs["api_key"] == "explicit-key"


def test_any_failure_while_building_the_sdk_client_is_an_llm_error(monkeypatch):
    class BrokenSdkClient:
        def __init__(self, **kwargs):
            raise RuntimeError("no credentials")

    monkeypatch.setattr("groq.Groq", BrokenSdkClient)
    with pytest.raises(LLMError, match="GROQ_API_KEY.*no credentials"):
        GroqLLM("groq-test", api_key="k")


def test_groq_llm_works_with_the_synthesizer_end_to_end():
    chunk = Chunk(
        chunk_id="d1::chunk_000", document_id="d1", index=0, text="Five days.", start_offset=0, end_offset=10
    )
    document = Document(document_id="d1", title="t", content="Five days.")
    passage = RetrievedPassage(chunk=chunk, document=document)
    claims = [{"text": "Five days.", "citation_chunk_ids": ["d1::chunk_000"]}]
    llm, completions = llm_for(completion(json.dumps({"claims": claims, "caveats": []})))
    result = synthesize("How many days?", [passage], llm)
    assert result.ok and result.model_name == "groq-test"
    assert completions.calls[0]["response_format"] == {"type": "json_object"}

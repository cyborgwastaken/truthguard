from __future__ import annotations

import json

import pytest
from google.genai import errors, types

from truthguard_agent.llm import GeminiLLM, LLMError
from truthguard_agent.schemas import Chunk, Document, RetrievedPassage
from truthguard_agent.synthesizer import synthesize


def response(text=None, finish=types.FinishReason.STOP, **fields):
    parts = [types.Part(text=text)] if text is not None else []
    candidate = types.Candidate(content=types.Content(role="model", parts=parts), finish_reason=finish)
    return types.GenerateContentResponse(candidates=[candidate], **fields)


class StubModels:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class StubClient:
    def __init__(self, outcome):
        self.models = StubModels(outcome)


def llm_for(outcome, **kwargs):
    client = StubClient(outcome)
    return GeminiLLM("gemini-test", client=client, **kwargs), client.models


def test_complete_returns_the_text_and_sends_the_model_system_and_user_prompt():
    llm, models = llm_for(response("hello"))
    assert llm.complete("be brief", "say hello") == "hello"
    call = models.calls[0]
    assert call["model"] == "gemini-test" and call["contents"] == "say hello"
    assert call["config"].system_instruction == "be brief"


def test_the_model_name_is_available_to_record_with_an_answer():
    assert llm_for(response("x"))[0].model_name == "gemini-test"


def test_json_output_asks_for_a_json_reply_and_plain_output_does_not():
    llm, models = llm_for(response("{}"))
    llm.complete("s", "u", json_output=True)
    llm.complete("s", "u")
    assert models.calls[0]["config"].response_mime_type == "application/json"
    assert models.calls[1]["config"].response_mime_type is None


def test_the_reply_length_limit_is_sent():
    llm, models = llm_for(response("x"), max_output_tokens=1234)
    llm.complete("s", "u")
    assert models.calls[0]["config"].max_output_tokens == 1234


def test_an_api_error_becomes_an_llm_error_with_the_status_and_message():
    error = errors.ClientError(
        429, {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    )
    llm, _ = llm_for(error)
    with pytest.raises(LLMError, match=r"429.*RESOURCE_EXHAUSTED.*Quota exceeded"):
        llm.complete("s", "u")


def test_a_server_error_and_a_timeout_also_become_llm_errors():
    body = {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}
    server = errors.ServerError(503, body)
    with pytest.raises(LLMError, match="503"):
        llm_for(server)[0].complete("s", "u")
    with pytest.raises(LLMError, match="TimeoutError"):
        llm_for(TimeoutError("read timed out"))[0].complete("s", "u")


def test_a_blocked_prompt_is_an_llm_error_that_names_the_reason():
    blocked = types.GenerateContentResponse(
        prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason=types.BlockedReason.SAFETY)
    )
    with pytest.raises(LLMError, match="blocked.*SAFETY"):
        llm_for(blocked)[0].complete("s", "u")


def test_a_reply_cut_off_by_the_length_limit_is_an_llm_error_not_a_half_answer():
    with pytest.raises(LLMError, match="cut off"):
        llm_for(response('{"claims": [', finish=types.FinishReason.MAX_TOKENS))[0].complete("s", "u")


def test_a_reply_stopped_for_another_reason_is_an_llm_error():
    with pytest.raises(LLMError, match="SAFETY"):
        llm_for(response("partial", finish=types.FinishReason.SAFETY))[0].complete("s", "u")


@pytest.mark.parametrize(
    "outcome, message",
    [
        (types.GenerateContentResponse(), "no candidate"),
        (response(None), "empty reply"),
        (response("   "), "empty reply"),
        (types.GenerateContentResponse(
            candidates=[types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text="reasoning", thought=True)]),
                finish_reason=types.FinishReason.STOP,
            )]
        ), "empty reply"),
    ],
    ids=["no-candidates", "no-text", "blank", "thinking-only"],
)
def test_a_reply_with_no_text_is_an_llm_error(outcome, message):
    with pytest.raises(LLMError, match=message):
        llm_for(outcome)[0].complete("s", "u")


@pytest.mark.parametrize(
    "finish",
    [None, types.FinishReason.FINISH_REASON_UNSPECIFIED, types.FinishReason.STOP],
    ids=["none", "unspecified", "stop"],
)
def test_a_normal_finish_reason_returns_the_text(finish):
    assert llm_for(response("fine", finish=finish))[0].complete("s", "u") == "fine"


def test_a_continuation_stop_reason_is_not_taken_as_a_complete_reply():
    with pytest.raises(LLMError, match="CONTINUATION"):
        llm_for(response("part", finish=types.FinishReason.CONTINUATION))[0].complete("s", "u")


def test_one_call_is_one_request_with_no_automatic_continuation():
    llm, models = llm_for(response("x"))
    llm.complete("s", "u")
    assert models.calls[0]["config"].automatic_continuation is False


def test_an_api_error_without_a_status_or_message_still_reads_clearly():
    with pytest.raises(LLMError) as raised:
        llm_for(errors.ServerError(502, {}))[0].complete("s", "u")
    assert "502" in str(raised.value) and "None" not in str(raised.value)


def test_a_value_error_from_the_sdk_becomes_an_llm_error_but_ctrl_c_does_not():
    with pytest.raises(LLMError, match="bad config"):
        llm_for(ValueError("bad config"))[0].complete("s", "u")
    with pytest.raises(KeyboardInterrupt):
        llm_for(KeyboardInterrupt())[0].complete("s", "u")


def test_without_an_api_key_building_the_client_fails_clearly(monkeypatch):
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiLLM("gemini-test")


@pytest.fixture()
def sdk_client_kwargs(monkeypatch):
    seen = {}

    class FakeSdkClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr("google.genai.Client", FakeSdkClient)
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return seen


def test_the_sdk_client_gets_the_key_and_a_timeout_in_milliseconds(sdk_client_kwargs):
    GeminiLLM("gemini-test", api_key="the-key", timeout_seconds=12.5)
    assert sdk_client_kwargs["api_key"] == "the-key"
    assert sdk_client_kwargs["http_options"].timeout == 12500


def test_the_sdk_client_always_uses_the_gemini_api_never_vertex(sdk_client_kwargs, monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    GeminiLLM("gemini-test", api_key="the-key")
    assert sdk_client_kwargs["vertexai"] is False


def test_the_key_is_taken_from_gemini_api_key_even_when_google_api_key_is_set(sdk_client_kwargs, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    GeminiLLM("gemini-test")
    assert sdk_client_kwargs["api_key"] == "gemini-key"


def test_an_explicit_key_beats_the_environment(sdk_client_kwargs, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    GeminiLLM("gemini-test", api_key="explicit-key")
    assert sdk_client_kwargs["api_key"] == "explicit-key"


def test_any_failure_while_building_the_sdk_client_is_an_llm_error(monkeypatch):
    class BrokenSdkClient:
        def __init__(self, **kwargs):
            raise RuntimeError("no credentials")

    monkeypatch.setattr("google.genai.Client", BrokenSdkClient)
    with pytest.raises(LLMError, match="no credentials"):
        GeminiLLM("gemini-test", api_key="k")


def test_gemini_llm_works_with_the_synthesizer_end_to_end():
    chunk = Chunk(
        chunk_id="d1::chunk_000", document_id="d1", index=0, text="Five days.", start_offset=0, end_offset=10
    )
    document = Document(document_id="d1", title="t", content="Five days.")
    passage = RetrievedPassage(chunk=chunk, document=document)
    claims = [{"text": "Five days.", "citation_chunk_ids": ["d1::chunk_000"]}]
    reply = json.dumps({"claims": claims, "caveats": []})
    llm, models = llm_for(response(reply))
    result = synthesize("How many days?", [passage], llm)
    assert result.ok and result.model_name == "gemini-test"
    assert models.calls[0]["config"].response_mime_type == "application/json"

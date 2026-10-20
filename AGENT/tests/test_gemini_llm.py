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
        if isinstance(self.outcome, Exception):
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
    server = errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})
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
    "empty",
    [types.GenerateContentResponse(), response(None), response("   ")],
    ids=["no-candidates", "no-text", "blank"],
)
def test_a_reply_with_no_text_is_an_llm_error(empty):
    with pytest.raises(LLMError, match="empty|no reply|no candidate"):
        llm_for(empty)[0].complete("s", "u")


def test_without_an_api_key_building_the_client_fails_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiLLM("gemini-test")


def test_the_sdk_client_gets_the_key_and_a_timeout_in_milliseconds(monkeypatch):
    seen = {}

    class FakeSdkClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr("google.genai.Client", FakeSdkClient)
    GeminiLLM("gemini-test", api_key="the-key", timeout_seconds=12.5)
    assert seen["api_key"] == "the-key"
    assert seen["http_options"].timeout == 12500


def test_gemini_llm_works_with_the_synthesizer_end_to_end():
    chunk = Chunk(chunk_id="d1::chunk_000", document_id="d1", index=0, text="Five days.", start_offset=0, end_offset=10)
    passage = RetrievedPassage(chunk=chunk, document=Document(document_id="d1", title="t", content="Five days."))
    reply = json.dumps({"claims": [{"text": "Five days.", "citation_chunk_ids": ["d1::chunk_000"]}], "caveats": []})
    llm, models = llm_for(response(reply))
    result = synthesize("How many days?", [passage], llm)
    assert result.ok and result.model_name == "gemini-test"
    assert models.calls[0]["config"].response_mime_type == "application/json"

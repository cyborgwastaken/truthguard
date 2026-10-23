from __future__ import annotations

import pytest

from truthguard_agent.llm import CachingLLM, FakeLLM, GroqLLM, LLMError


def test_fake_llm_replies_in_order_and_records_every_call():
    llm = FakeLLM(["first", "second"])
    assert llm.complete("sys 1", "user 1") == "first"
    assert llm.complete("sys 2", "user 2", json_output=True) == "second"
    assert llm.calls == [
        {"system": "sys 1", "user": "user 1", "json_output": False},
        {"system": "sys 2", "user": "user 2", "json_output": True},
    ]


def test_fake_llm_raises_an_exception_given_in_place_of_a_reply():
    llm = FakeLLM([LLMError("rate limited"), "recovered"])
    with pytest.raises(LLMError, match="rate limited"):
        llm.complete("s", "u")
    assert llm.complete("s", "u") == "recovered"


def test_fake_llm_with_no_reply_left_fails_loudly_instead_of_inventing_one():
    llm = FakeLLM(["only"])
    llm.complete("s", "u")
    with pytest.raises(LLMError):
        llm.complete("s", "u")


def test_fake_llm_has_a_model_name_to_record_with_an_answer():
    assert FakeLLM([]).model_name == "fake-llm"
    assert FakeLLM([], model_name="scripted-1").model_name == "scripted-1"


# ---- CachingLLM ------------------------------------------------------------------------------------------

def test_record_then_replay_gives_the_same_replies_without_the_model(tmp_path):
    path = tmp_path / "replies.jsonl"
    live = FakeLLM(["one", "two"], model_name="m")
    recorder = CachingLLM(live, path, "record")
    assert recorder.complete("s", "u1") == "one"
    assert recorder.complete("s", "u2", json_output=True) == "two"

    replay = CachingLLM(None, path, "replay", model_name="m")
    assert replay.complete("s", "u1") == "one"
    assert replay.complete("s", "u2", json_output=True) == "two"
    assert replay.hits == 2 and replay.misses == 0


def test_replay_without_a_stored_reply_is_a_visible_error_never_a_fallback(tmp_path):
    replay = CachingLLM(None, tmp_path / "none.jsonl", "replay", model_name="m")
    with pytest.raises(LLMError, match="No recorded reply"):
        replay.complete("s", "u")


def test_the_key_covers_model_system_user_and_json_output(tmp_path):
    path = tmp_path / "r.jsonl"
    CachingLLM(FakeLLM(["a", "b", "c", "d"], model_name="m"), path, "record").complete("s", "u")
    for model, system, user, json_output in [("other", "s", "u", False), ("m", "s2", "u", False),
                                            ("m", "s", "u2", False), ("m", "s", "u", True)]:
        with pytest.raises(LLMError):
            CachingLLM(None, path, "replay", model_name=model).complete(system, user, json_output=json_output)


def test_cache_mode_calls_the_model_once_and_resumes_from_the_file(tmp_path):
    path = tmp_path / "r.jsonl"
    inner = FakeLLM(["only once"], model_name="m")
    first = CachingLLM(inner, path, "cache")
    assert first.complete("s", "u") == "only once"
    assert first.complete("s", "u") == "only once"
    assert len(inner.calls) == 1 and first.hits == 1 and first.misses == 1
    resumed = CachingLLM(FakeLLM([], model_name="m"), path, "cache")  # a new process would do this
    assert resumed.complete("s", "u") == "only once"


def test_a_failed_call_is_not_stored(tmp_path):
    path = tmp_path / "r.jsonl"
    recorder = CachingLLM(FakeLLM([LLMError("503"), "fine"], model_name="m"), path, "cache")
    with pytest.raises(LLMError):
        recorder.complete("s", "u")
    assert recorder.complete("s", "u") == "fine"  # the failure was not remembered


def test_live_mode_stores_nothing(tmp_path):
    path = tmp_path / "r.jsonl"
    CachingLLM(FakeLLM(["x"], model_name="m"), path, "live").complete("s", "u")
    assert not path.exists()


def test_a_model_client_is_required_unless_replaying(tmp_path):
    with pytest.raises(ValueError):
        CachingLLM(None, tmp_path / "r.jsonl", "record")
    with pytest.raises(ValueError):
        CachingLLM(FakeLLM([]), tmp_path / "r.jsonl", "sometimes")


# ---- temperature -----------------------------------------------------------------------------------------

class _Capture:
    """Stands in for the Groq SDK client and remembers the arguments of the call."""

    def __init__(self):
        self.kwargs = None
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.kwargs = kwargs

                class _Msg:
                    content = "{}"

                class _Choice:
                    finish_reason = "stop"
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def test_temperature_is_sent_only_when_set():
    capture = _Capture()
    GroqLLM("m", client=capture, temperature=0).complete("s", "u")
    assert capture.kwargs["temperature"] == 0
    capture = _Capture()
    GroqLLM("m", client=capture).complete("s", "u")
    assert "temperature" not in capture.kwargs

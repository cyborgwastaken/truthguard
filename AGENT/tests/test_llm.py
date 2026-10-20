from __future__ import annotations

import pytest

from truthguard_agent.llm import FakeLLM, LLMError


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

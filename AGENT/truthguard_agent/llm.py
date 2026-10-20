"""The language model behind a small interface, so agents never depend on one provider and tests never
call a paid API. A real client (Gemini) implements LLMClient; FakeLLM is for tests."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Protocol, Union


class LLMError(Exception):
    """A model call failed or gave nothing usable: API error, timeout, blocked prompt, cut-off reply."""


class LLMClient(Protocol):
    model_name: str

    def complete(self, system: str, user: str, json_output: bool = False) -> str:
        """The model's reply as text. json_output asks for JSON only.

        Any failure must surface as LLMError: an implementation wraps every other exception, so callers
        only have to catch one type.
        """
        ...


class FakeLLM:
    """Replies with canned text in order. An Exception in the list is raised instead of returned.

    Every call is recorded in .calls. With no reply left it raises LLMError, so a test that makes an
    unexpected extra call fails loudly.
    """

    def __init__(self, replies: Iterable[Union[str, Exception]], model_name: str = "fake-llm") -> None:
        self.model_name = model_name
        self.calls: List[Dict[str, Any]] = []
        self._replies = list(replies)

    def complete(self, system: str, user: str, json_output: bool = False) -> str:
        self.calls.append({"system": system, "user": user, "json_output": json_output})
        if not self._replies:
            raise LLMError("FakeLLM has no reply left")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

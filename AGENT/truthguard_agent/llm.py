"""The language model behind a small interface, so agents never depend on one provider and tests never
call a paid or quota-limited API. A real client (Groq) implements LLMClient; FakeLLM is for tests."""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Protocol, Union


class LLMError(Exception):
    """A model call failed or gave nothing usable: API error, timeout, cut-off or empty reply."""


class LLMClient(Protocol):
    model_name: str

    def complete(self, system: str, user: str, json_output: bool = False) -> str:
        """The model's reply as text. json_output asks for JSON only.

        Any failure must surface as LLMError: an implementation wraps every other exception, so callers
        only have to catch one type.
        """
        ...


class GroqLLM:
    """LLMClient for the Groq API (groq SDK).

    The key comes from api_key, else the GROQ_API_KEY environment variable; it is never logged or stored
    here. The model name is passed in (AGENT cannot read BACKEND's settings). The SDK is told not to
    retry, so one complete() call is one request against the rate limit. Groq says it does not train on
    customer data, but send it only the fictional fixtures until the team has agreed otherwise.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_output_tokens: int = 8192,
        client: Any = None,
    ) -> None:
        self.model_name = model
        self._max_output_tokens = max_output_tokens
        if client is None:
            import groq

            try:
                client = groq.Groq(
                    api_key=api_key or os.environ.get("GROQ_API_KEY"), timeout=timeout_seconds, max_retries=0
                )
            except Exception as error:  # a missing key raises GroqError; keep the one error type
                raise LLMError("Could not create the Groq client (is GROQ_API_KEY set?): %s" % error) from error
        self._client = client

    def complete(self, system: str, user: str, json_output: bool = False) -> str:
        options: Dict[str, Any] = {"max_completion_tokens": self._max_output_tokens}
        if json_output:
            options["response_format"] = {"type": "json_object"}
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                **options,
            )
        except Exception as error:  # API errors, timeouts, lost connections, anything else the SDK raises
            raise LLMError(self._describe(error)) from error
        return self._text_of(response)

    @staticmethod
    def _describe(error: Exception) -> str:
        status = getattr(error, "status_code", None)
        if status is not None:
            return "Groq API error %s: %s" % (status, getattr(error, "message", None) or "(no message)")
        return "Groq call failed (%s): %s" % (type(error).__name__, error)

    @staticmethod
    def _text_of(response: Any) -> str:
        if not response.choices:
            raise LLMError("Groq returned no choice")
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise LLMError("Groq's reply was cut off by the output limit")
        if choice.finish_reason != "stop":
            raise LLMError("Groq stopped early: %s" % choice.finish_reason)
        text = choice.message.content
        if not text or not text.strip():
            raise LLMError("Groq returned an empty reply")
        return text


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

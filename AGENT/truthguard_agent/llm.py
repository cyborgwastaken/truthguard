"""The language model behind a small interface, so agents never depend on one provider and tests never
call a paid API. A real client (Gemini) implements LLMClient; FakeLLM is for tests."""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Protocol, Union


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


def _sdk():
    """The google-genai SDK, imported when a Gemini client is first used, so the rest of the package
    (and every test with FakeLLM) does not need it."""
    from google import genai
    from google.genai import errors, types

    return genai, errors, types


class GeminiLLM:
    """LLMClient for the Gemini API (google-genai SDK).

    The key comes from api_key, else the GEMINI_API_KEY environment variable (else the SDK's own
    GOOGLE_API_KEY); it is never logged or stored here. Always the Gemini API, never Vertex AI. The model
    name is passed in (AGENT cannot read BACKEND's settings). Free-tier prompts are used by Google to
    improve its products, so send it only the fictional fixtures, never real documents.
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
            genai, _, types = _sdk()
            try:
                client = genai.Client(
                    api_key=api_key or os.environ.get("GEMINI_API_KEY"),
                    vertexai=False,
                    http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
                )
            except Exception as error:  # a missing key raises ValueError; keep the one error type
                message = "Could not create the Gemini client (is GEMINI_API_KEY set?): %s" % error
                raise LLMError(message) from error
        self._client = client

    def complete(self, system: str, user: str, json_output: bool = False) -> str:
        _, errors, types = _sdk()
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self._max_output_tokens,
            response_mime_type="application/json" if json_output else None,
            automatic_continuation=False,  # one complete() call is one request against the quota
        )
        try:
            response = self._client.models.generate_content(
                model=self.model_name, contents=user, config=config
            )
        except errors.APIError as error:
            status, detail = error.status or "(no status)", error.message or "(no message)"
            raise LLMError("Gemini API error %s %s: %s" % (error.code, status, detail)) from error
        except Exception as error:  # timeouts, connection errors, anything else the SDK raises
            raise LLMError("Gemini call failed (%s): %s" % (type(error).__name__, error)) from error
        return self._text_of(response, types)

    @staticmethod
    def _text_of(response: Any, types: Any) -> str:
        block = response.prompt_feedback.block_reason if response.prompt_feedback else None
        if block is not None and block != types.BlockedReason.BLOCKED_REASON_UNSPECIFIED:
            raise LLMError("Gemini blocked the prompt (%s)" % block.name)
        if not response.candidates:
            raise LLMError("Gemini returned no candidate")
        reason = response.candidates[0].finish_reason
        if reason == types.FinishReason.MAX_TOKENS:
            raise LLMError("Gemini's reply was cut off by the output limit")
        if reason not in (None, types.FinishReason.STOP, types.FinishReason.FINISH_REASON_UNSPECIFIED):
            raise LLMError("Gemini stopped early: %s" % reason.name)
        text = response.text
        if not text or not text.strip():
            raise LLMError("Gemini returned an empty reply")
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

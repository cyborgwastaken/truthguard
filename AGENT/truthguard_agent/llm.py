"""The language model behind a small interface, so agents never depend on one provider and tests never
call a paid or quota-limited API. A real client (Groq) implements LLMClient; FakeLLM is for tests."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Union


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


_WAIT = re.compile(r"try again in\s+(?:(\d+(?:\.\d+)?)h)?\s*(?:(\d+(?:\.\d+)?)m(?!s))?\s*(?:(\d+(?:\.\d+)?)s)?\s*(?:(\d+(?:\.\d+)?)ms)?", re.IGNORECASE)


def retry_after_seconds(error: Exception) -> Optional[float]:
    """How long the service asked us to wait: the retry-after header, else "try again in 1m2.5s" in the message."""
    headers = getattr(getattr(error, "response", None), "headers", None)
    if headers is not None:
        try:
            return float(headers.get("retry-after"))
        except (TypeError, ValueError):
            pass
    match = _WAIT.search(str(getattr(error, "message", "") or "") + " " + str(error))
    if match and any(match.groups()):
        hours, minutes, seconds, millis = (float(g) if g else 0.0 for g in match.groups())
        return hours * 3600 + minutes * 60 + seconds + millis / 1000
    return None


class GroqLLM:
    """LLMClient for the Groq API (groq SDK).

    The key comes from api_key, else the GROQ_API_KEY environment variable; it is never logged or stored
    here. The model name is passed in (AGENT cannot read BACKEND's settings). The SDK is told not to
    retry; the one retry this class does is deliberate: when Groq answers 429 (rate limit, for example the
    free tier's tokens-per-minute cap) it waits as long as Groq says (the retry-after header, else the "try
    again in ..." text) and tries again, up to rate_limit_retries times. A wait longer than max_wait_seconds
    (a daily limit, say) is not waited out: it fails at once with the message. Groq says it does not train on
    customer data, but send it only the fictional fixtures until the team has agreed otherwise.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_output_tokens: int = 8192,
        client: Any = None,
        temperature: Optional[float] = None,
        rate_limit_retries: int = 3,
        max_wait_seconds: float = 45.0,
        default_wait_seconds: float = 15.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model_name = model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._rate_limit_retries = rate_limit_retries
        self._max_wait = max_wait_seconds
        self._default_wait = default_wait_seconds
        self._sleep = sleep
        self.rate_limit_waits = 0  # how many times a call had to wait for the rate limit
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
        if self._temperature is not None:
            options["temperature"] = self._temperature
        if json_output:
            options["response_format"] = {"type": "json_object"}
        attempt = 0
        while True:
            try:
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    **options,
                )
                break
            except Exception as error:  # API errors, timeouts, lost connections, anything else the SDK raises
                wait = self._rate_limit_wait(error) if attempt < self._rate_limit_retries else None
                if wait is None:
                    raise LLMError(self._describe(error)) from error
                attempt += 1
                self.rate_limit_waits += 1
                self._sleep(wait)
        return self._text_of(response)

    def _rate_limit_wait(self, error: Exception) -> Optional[float]:
        """Seconds to wait before retrying a rate-limited call, or None if it should not be retried."""
        if getattr(error, "status_code", None) != 429:
            return None
        wait = retry_after_seconds(error)
        if wait is None:
            wait = self._default_wait
        return wait + 0.5 if wait <= self._max_wait else None

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


CACHE_MODES = ("live", "record", "cache", "replay")


class CachingLLM:
    """Wraps a client so that model replies can be recorded and replayed.

    live    pass every call through; nothing is stored.
    record  pass every call through and store the reply.
    cache   use a stored reply if there is one, else call the model and store the reply (also lets an
            interrupted benchmark resume).
    replay  use stored replies only; a call with no stored reply raises LLMError, so a gap is a visible
            verification_failed and never a silent fallback. `inner` may be None.

    A reply is stored under the SHA-256 of model name, system prompt, user prompt and json_output. A failed
    call is never stored. The file is JSON lines, appended as replies arrive."""

    def __init__(self, inner: Optional[LLMClient], path: Union[str, Path], mode: str = "live",
                 model_name: Optional[str] = None) -> None:
        if mode not in CACHE_MODES:
            raise ValueError("mode must be one of %s" % ", ".join(CACHE_MODES))
        if inner is None and mode != "replay":
            raise ValueError("a model client is needed unless mode is replay")
        self.mode = mode
        self._inner = inner
        self._path = Path(path)
        self.model_name = model_name or (inner.model_name if inner is not None else "replay")
        self._lock = threading.Lock()
        self._replies: Dict[str, str] = {}
        self.hits = 0
        self.misses = 0
        if mode != "live" and self._path.exists():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self._replies[entry["key"]] = entry["reply"]

    def _key(self, system: str, user: str, json_output: bool) -> str:
        raw = json.dumps([self.model_name, system, user, bool(json_output)], ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _store(self, key: str, reply: str) -> None:
        with self._lock:
            self._replies[key] = reply
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"key": key, "model": self.model_name, "reply": reply}, ensure_ascii=False) + "\n")

    def complete(self, system: str, user: str, json_output: bool = False) -> str:
        if self.mode == "live":
            return self._inner.complete(system, user, json_output=json_output)
        key = self._key(system, user, json_output)
        if self.mode in ("cache", "replay") and key in self._replies:
            self.hits += 1
            return self._replies[key]
        self.misses += 1
        if self.mode == "replay":
            raise LLMError("No recorded reply for this prompt (replay mode). Record it first.")
        reply = self._inner.complete(system, user, json_output=json_output)
        self._store(key, reply)
        return reply

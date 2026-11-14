"""The Gemini Decisions API client (`POST /v1beta/decisions`, model gemini-decision-1).

One request scores many closed questions about one input in one pass; each answer carries the
probability of every option. The key goes in the `x-goog-api-key` header only, never in a URL, a
log line or an error. 429 and 5xx are retried with backoff; anything else (another HTTP status, a
timeout, a reply that is not JSON) is a `DecisionsError` whose message is safe to show.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from app.core.errors import InvalidInputError

URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
MODEL = "gemini-decision-1"
USD_PER_M_INPUT = 0.10  # output tokens are free (blog, 2026-11-11)
RETRY = frozenset({429, 500, 502, 503, 504})
TRIES = 4

log = logging.getLogger(__name__)
Json = dict[str, Any]


class DecisionsError(Exception):
    """The Decisions API gave no usable answer; the message holds no key and no body."""


class Decider(Protocol):
    @property
    def model(self) -> str: ...

    def decide(self, body: Json) -> Json:
        """The parsed reply to a request body; raises `DecisionsError`."""
        ...


# (body bytes, key, timeout) -> (HTTP status, reply bytes); raises OSError on a network failure
Transport = Callable[[bytes, str, float], tuple[int, bytes]]


def urllib_transport(body: bytes, key: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(
        URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class DecisionsClient:
    def __init__(
        self,
        api_key: str,
        timeout_s: float,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise InvalidInputError("GEMINI_API_KEY is empty: the Decisions reader needs a key")
        self._key = api_key
        self._timeout = timeout_s
        self._transport = transport
        self._sleep = sleep

    @property
    def model(self) -> str:
        return MODEL

    def __repr__(self) -> str:
        return f"DecisionsClient({MODEL})"

    def decide(self, body: Json) -> Json:
        raw = json.dumps(body).encode()
        delay = 1.0
        for attempt in range(1, TRIES + 1):
            start = time.monotonic()
            try:
                status, data = self._transport(raw, self._key, self._timeout)
            except OSError as error:  # URLError, timeouts, resets: not retried
                raise DecisionsError(f"no answer: {type(error).__name__}") from None
            if status == 200:
                try:
                    reply = json.loads(data)
                except json.JSONDecodeError:
                    raise DecisionsError("the answer is not JSON") from None
                tokens = int(reply.get("usage", {}).get("total_input_tokens", 0))
                log.info(
                    "decisions: %s, %.2f s, %d input tokens, $%.6f, try %d",
                    MODEL, time.monotonic() - start, tokens,
                    tokens * USD_PER_M_INPUT / 1e6, attempt,
                )  # fmt: skip
                return reply
            if status in RETRY and attempt < TRIES:
                self._sleep(delay)
                delay *= 2
                continue
            raise DecisionsError(f"HTTP {status} {_status(data)}".strip())
        raise AssertionError("unreachable")


def _status(data: bytes) -> str:
    """Google's error status word (RESOURCE_EXHAUSTED...), never the raw body."""
    try:
        status = json.loads(data).get("error", {}).get("status", "")
    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
        return ""
    return status if isinstance(status, str) and status.replace("_", "").isalpha() else ""


class FakeDecisionsClient:
    """Replays recorded replies by request key (`request_key(body)` of the reader), or raises
    `DecisionsError` for a key it has no reply for. Counts the calls."""

    def __init__(self, replies: Mapping[str, Json], fail: str | None = None) -> None:
        self._replies = dict(replies)
        self._fail = fail
        self.calls = 0

    @property
    def model(self) -> str:
        return MODEL

    def decide(self, body: Json) -> Json:
        from app.adapters.decisions.g1main import request_key

        self.calls += 1
        if self._fail is not None:
            raise DecisionsError(self._fail)
        key = request_key(body)
        if key not in self._replies:
            raise DecisionsError("no recorded reply")
        return self._replies[key]

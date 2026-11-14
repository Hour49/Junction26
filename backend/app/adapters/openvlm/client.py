"""An OpenAI-compatible chat client for our own model server (vLLM on Verda, reached by tunnel).

The key goes in the `Authorization` header only, never in a URL, a log line or an error. 429 and
5xx are retried with backoff; anything else (another HTTP status, a network failure or timeout,
a reply that is not JSON) is an `OpenVlmError` whose message holds no key and no body.
"""

import base64
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from app.core.errors import InvalidInputError

RETRY = frozenset({429, 500, 502, 503, 504})
TRIES = 4

log = logging.getLogger(__name__)
Json = dict[str, Any]


class OpenVlmError(Exception):
    """The model server gave no usable answer; the message is safe to show."""


# (url, body bytes, key, timeout) -> (HTTP status, reply bytes); raises OSError on a network failure
Transport = Callable[[str, bytes, str, float], tuple[int, bytes]]


def urllib_transport(url: str, body: bytes, key: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def image_part(png: bytes) -> Json:
    return {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode("ascii")},
    }


class OpenVlmClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise InvalidInputError("EU_VLM_API_KEY is empty: the EU model server needs a key")
        if not base_url:
            raise InvalidInputError("EU_VLM_BASE_URL is empty: the EU model server needs a URL")
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self.model = model
        self._timeout = timeout_s
        self._transport = transport
        self._sleep = sleep

    def __repr__(self) -> str:
        return f"OpenVlmClient({self.model})"

    def chat(self, body: Json) -> Json:
        """The parsed reply to a chat completions body (`model` is filled in)."""
        raw = json.dumps({**body, "model": self.model}).encode()
        delay = 1.0
        for attempt in range(1, TRIES + 1):
            start = time.monotonic()
            try:
                status, data = self._transport(self._url, raw, self._key, self._timeout)
            except OSError as error:  # URLError, timeouts, resets: not retried
                raise OpenVlmError(f"no answer: {type(error).__name__}") from None
            if status == 200:
                try:
                    reply = json.loads(data)
                except json.JSONDecodeError:
                    raise OpenVlmError("the answer is not JSON") from None
                if not isinstance(reply, dict) or not reply.get("choices"):
                    raise OpenVlmError("the answer has no choices")
                usage = reply.get("usage") or {}
                log.info(
                    "openvlm: %s, %.2f s, %s prompt + %s completion tokens, try %d",
                    self.model, time.monotonic() - start, usage.get("prompt_tokens"),
                    usage.get("completion_tokens"), attempt,
                )  # fmt: skip
                return reply
            if status in RETRY and attempt < TRIES:
                self._sleep(delay)
                delay *= 2
                continue
            raise OpenVlmError(f"HTTP {status} {_code(data)}".strip())
        raise AssertionError("unreachable")


def _code(data: bytes) -> str:
    """The server's error type word (BadRequestError...), never the raw body."""
    try:
        error = json.loads(data).get("error", {})
        code = error.get("type", "") if isinstance(error, dict) else ""
    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
        return ""
    return code if isinstance(code, str) and code.replace("_", "").isalnum() else ""

"""The raster composite's remote reader (`RASTER_COMPONENTS` source `verda`): the detector served
from our Verda serverless container `hour49-reader` (deploy/verda/), on a GPU in Helsinki.

The page's bytes are posted to `<url>/read` with the Verda inference key as a bearer token. The
reply (`reader_v1`, written by deploy/verda/server.py) carries the backend's own `Extracted` as
JSON: plans and elements as page fractions with `attrs.score`, and `read`. It is validated with
the same model, so the remote reader gives what `detector:<arm>` gives on the CPU.

Errors: a wrong URL, key or reply raises (`InvalidInputError`). When the endpoint is busy or
down (timeout, connection error, 429, 5xx) the sheet is left unread (`read` empty, the reason in
`notes`), so its classes stay unknown, never 0, as for any component that did not read a sheet.
The first request after the endpoint scaled to zero waits for a replica to start (about a
minute), hence the long default timeout.

At most `max_in_flight` requests (default 4) are open at once per client, whatever the caller's
thread count: with more, Verda's gateway queued requests for 11-16 s, and at 10 it lost some
(.agents/serve.md, measured 2026-11-14).
"""

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from threading import BoundedSemaphore
from typing import Any, Protocol

from pydantic import ValidationError

from app.core.drawing.model import Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles

SCHEMA = "reader_v1"
TIMEOUT_S = 300.0  # a cold start is about 60 s; the gateway queues requests meanwhile
MAX_IN_FLIGHT = 4  # one replica served 3.6 sheets/s at 4; more only queued or got lost

log = logging.getLogger(__name__)


class ReaderUnavailableError(Exception):
    """The endpoint did not answer this time (busy, starting or down); worth trying later."""


class ReaderClient(Protocol):
    def read(self, image: bytes) -> dict[str, Any]: ...


class HttpReaderClient:
    """POST <url>/read with the image bytes; the reply as a dict."""

    def __init__(
        self, url: str, key: str, timeout: float = TIMEOUT_S, max_in_flight: int = MAX_IN_FLIGHT
    ) -> None:
        if max_in_flight < 1:
            raise InvalidInputError("the remote reader needs at least 1 request in flight")
        if not url.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
            raise InvalidInputError(
                "VERDA_READER_URL must be an https:// URL (the key goes with it)"
            )
        self._url = url.rstrip("/") + "/read"
        self._key = key
        self._timeout = timeout
        self._slots = BoundedSemaphore(max_in_flight)

    def read(self, image: bytes) -> dict[str, Any]:
        request = urllib.request.Request(self._url, data=image, method="POST")
        request.add_header("Authorization", f"Bearer {self._key}")
        request.add_header("Content-Type", "application/octet-stream")
        try:
            with self._slots, urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            detail = f"HTTP {error.code} from {self._url}: {error.read()[:200]!r}"
            if error.code == 429 or error.code >= 500:
                raise ReaderUnavailableError(detail) from error
            raise InvalidInputError(detail) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            raise ReaderUnavailableError(f"{self._url}: {error}") from error
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise InvalidInputError(f"{self._url} did not answer JSON: {raw[:200]!r}") from error


class FakeReaderClient:
    """Answers each image with `reply(image)`; keeps the images it was sent."""

    def __init__(self, reply: Callable[[bytes], dict[str, Any]]) -> None:
        self._reply = reply
        self.sent: list[bytes] = []

    def read(self, image: bytes) -> dict[str, Any]:
        self.sent.append(image)
        return self._reply(image)


class RemoteReader:
    def __init__(self, files: DrawingFiles, client: ReaderClient, name: str = "verda") -> None:
        self._files = files
        self._client = client
        self._name = name

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        started = time.perf_counter()
        try:
            body = self._client.read(self._files.read(source.path))
        except ReaderUnavailableError as error:
            log.warning("%s: %s not read: %s", self._name, source.path, error)
            return Extracted(
                method="detector",
                scale=Scale(status="no_scale"),
                read=(),
                notes=(f"{self._name}: not read, the endpoint did not answer ({error})",),
            )
        if not isinstance(body, dict) or body.get("schema") != SCHEMA:
            raise InvalidInputError(f"{self._name}: the reply is not {SCHEMA}")
        try:
            extracted = Extracted.model_validate(body.get("extracted"))
        except ValidationError as error:
            raise InvalidInputError(f"{self._name}: the reply's `extracted`: {error}") from error
        seconds = time.perf_counter() - started
        log.info("%s: %s read in %.2f s", self._name, source.path, seconds)
        note = (
            f"{self._name}: model {body.get('model')} on {body.get('provider')}, "
            f"{body.get('seconds')} s on the server, {seconds:.2f} s with the network"
        )
        return extracted.model_copy(update={"notes": (*extracted.notes, note)})

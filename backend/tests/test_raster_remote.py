"""The remote reader (`verda`): the reply contract, errors, and the HTTP client against a local
stand-in server. Synthetic images and replies only; the real endpoint only in the `live` test."""

import json
import os
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest

from app.adapters import raster_remote
from app.adapters.raster_remote import (
    SCHEMA,
    FakeReaderClient,
    HttpReaderClient,
    ReaderUnavailableError,
    RemoteReader,
)
from app.core.drawing.model import Element, Page, Plan, Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet

PNG = "data/cubicasa5k/x.png"
DATA = b"\x89PNG not really"

# What deploy/verda/server.py sends: the backend's `Extracted`, dumped as JSON by alias.
READ = Extracted(
    method="detector",
    scale=Scale(status="no_scale"),
    plans=(Plan(id="p1", page=1, box=(0.0, 0.0, 0.5, 1.0)),),
    elements=(
        Element.model_validate(
            {
                "id": "e1",
                "class": "door",
                "page": 1,
                "box": (0.1, 0.1, 0.2, 0.2),
                "attrs": {"score": 0.91, "detector_class": "door"},
            }
        ),
    ),
    read=("door", "window"),
    notes=("detector arm-x (rfdetr, 1024 px, onnxruntime CPU): 1 elements, 1 plans by detector",),
)


def reply(extracted: Any = None) -> dict[str, Any]:
    body = READ.model_dump(mode="json", by_alias=True) if extracted is None else extracted
    return {"schema": SCHEMA, "model": "arm-x", "provider": "CUDAExecutionProvider",
            "seconds": 0.05, "extracted": body}  # fmt: skip


class Files:
    def read(self, path: str) -> bytes:
        assert path == PNG
        return DATA


def sheet() -> tuple[DrawingFile, Sheet]:
    file = DrawingFile(path=PNG, size=1, sha256="0" * 64, kind="png")
    return file, Sheet(file=file, pages=(Page(page=1, width=200, height=100, unit="px"),))


def test_the_reply_becomes_the_same_extraction_with_a_note_on_where_it_ran() -> None:
    client = FakeReaderClient(lambda image: reply())
    got = RemoteReader(Files(), client).extract(*sheet())
    assert client.sent == [DATA]
    assert got.model_copy(update={"notes": got.notes[:1]}) == READ
    assert got.elements[0].attrs["score"] == 0.91
    assert got.read == ("door", "window")
    assert got.notes[1].startswith("verda: model arm-x on CUDAExecutionProvider, 0.05 s")


@pytest.mark.parametrize(
    "body",
    [
        {"schema": "other", "extracted": {}},
        reply({"method": "detector"}),  # no scale
        reply({**READ.model_dump(mode="json", by_alias=True), "elements": [{"class": "stair"}]}),
        ["not", "a", "dict"],
    ],
)
def test_a_reply_that_breaks_the_contract_raises(body: Any) -> None:
    with pytest.raises(InvalidInputError):
        RemoteReader(Files(), FakeReaderClient(lambda image: body)).extract(*sheet())


def test_an_endpoint_that_does_not_answer_leaves_the_sheet_unread() -> None:
    def down(image: bytes) -> dict[str, Any]:
        raise ReaderUnavailableError("HTTP 503")

    got = RemoteReader(Files(), FakeReaderClient(down)).extract(*sheet())
    assert got.read == ()  # unknown, never 0: the composite skips every class of this source
    assert got.elements == () and got.plans == ()
    assert "HTTP 503" in got.notes[0]


class Stub(BaseHTTPRequestHandler):
    """Answers POST /read with the server's (status, body); keeps what it got."""

    answer: ClassVar[tuple[int, bytes]] = (200, b"{}")
    got: ClassVar[list[tuple[str, str | None, bytes]]] = []

    def do_POST(self) -> None:
        size = int(self.headers["Content-Length"])
        type(self).got.append((self.path, self.headers["Authorization"], self.rfile.read(size)))
        status, body = type(self).answer
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def stub() -> Iterator[Callable[[int, bytes], str]]:
    server = HTTPServer(("127.0.0.1", 0), Stub)
    Stub.got = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def answer(status: int, body: bytes) -> str:
        Stub.answer = (status, body)
        return f"http://127.0.0.1:{server.server_port}/"

    yield answer
    server.shutdown()
    server.server_close()


def test_the_http_client_posts_the_image_with_the_key(stub: Callable[[int, bytes], str]) -> None:
    url = stub(200, json.dumps(reply()).encode())
    got = RemoteReader(Files(), HttpReaderClient(url, "k-test", timeout=5)).extract(*sheet())
    assert Stub.got == [("/read", "Bearer k-test", DATA)]
    assert got.elements == READ.elements


@pytest.mark.parametrize("status", [429, 502, 503])
def test_busy_or_failing_endpoint_is_unavailable(
    stub: Callable[[int, bytes], str], status: int
) -> None:
    with pytest.raises(ReaderUnavailableError):
        HttpReaderClient(stub(status, b"busy"), "k", timeout=5).read(DATA)


@pytest.mark.parametrize(("status", "body"), [(401, b"no"), (404, b"no"), (200, b"<html>")])
def test_wrong_key_route_or_reply_raises(
    stub: Callable[[int, bytes], str], status: int, body: bytes
) -> None:
    with pytest.raises(InvalidInputError):
        HttpReaderClient(stub(status, body), "k", timeout=5).read(DATA)


def test_nothing_listens_is_unavailable() -> None:
    server = HTTPServer(("127.0.0.1", 0), Stub)
    url = f"http://127.0.0.1:{server.server_port}"
    server.server_close()  # the port is free again: the connection is refused
    with pytest.raises(ReaderUnavailableError):
        HttpReaderClient(url, "k", timeout=5).read(DATA)


def test_at_most_max_in_flight_requests_reach_the_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """8 callers, limit 4. The endpoint holds every request until either all 8 reached it (no
    limit) or 4 did and the other 4 wait for a slot in the client; then it answers them all.
    No sleeps: each outcome is decided by counts, the timeouts only end a broken run."""
    seen = threading.Condition()
    count = {"in": 0, "most": 0, "waiting": 0}
    answer = threading.Event()
    body = json.dumps(reply()).encode()

    class Slots:
        """The client's semaphore, counting the callers that wait for a slot."""

        def __init__(self, value: int) -> None:
            self._slots = threading.BoundedSemaphore(value)

        def __enter__(self) -> None:
            with seen:
                count["waiting"] += 1
                seen.notify_all()
            self._slots.acquire()
            with seen:
                count["waiting"] -= 1

        def __exit__(self, *exc: object) -> None:
            self._slots.release()

    class Held(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            with seen:
                count["in"] += 1
                count["most"] = max(count["most"], count["in"])
                seen.notify_all()
            answer.wait(timeout=30)
            with seen:
                count["in"] -= 1
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    monkeypatch.setattr(raster_remote, "BoundedSemaphore", Slots)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Held)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = HttpReaderClient(f"http://127.0.0.1:{server.server_port}", "k", 30, max_in_flight=4)
    replies: list[dict[str, Any]] = []
    callers = [threading.Thread(target=lambda: replies.append(client.read(DATA))) for _ in range(8)]
    try:
        for caller in callers:
            caller.start()
        with seen:
            assert seen.wait_for(
                lambda: count["in"] == 8 or (count["in"] == 4 and count["waiting"] == 4), 30
            )
    finally:
        answer.set()
        for caller in callers:
            caller.join(30)
        server.shutdown()
        server.server_close()
    assert count["most"] == 4
    assert len(replies) == 8


def test_the_key_never_goes_over_plain_http_to_another_host() -> None:
    with pytest.raises(InvalidInputError):
        HttpReaderClient("http://example.com/hour49-reader", "k")


@pytest.mark.live
def test_the_verda_endpoint_reads_a_synthetic_page(make_png: Callable[[int, int], bytes]) -> None:
    """RUN_LIVE_TESTS=1 with VERDA_READER_URL and VERDA_INFERENCE_API_KEY in the environment.
    A blank page: the reply validates and finds nothing. Costs a replica start when cold."""
    url, key = os.environ["VERDA_READER_URL"], os.environ["VERDA_INFERENCE_API_KEY"]

    class Blank:
        def read(self, path: str) -> bytes:
            return make_png(800, 600)

    got = RemoteReader(Blank(), HttpReaderClient(url, key)).extract(*sheet())
    assert got.read and got.elements == ()

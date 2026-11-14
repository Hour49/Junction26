"""The Gemini room reader (app/adapters/raster_ocr/gemini.py, arm G4): how a reply becomes rooms,
the reply cache, and what a failed call leaves. Every test runs on a fake model or a stubbed
urlopen: no network, no data/."""

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.adapters.raster_ocr.gemini import (
    GeminiClient,
    GeminiError,
    GeminiRoomExtractor,
    GeminiRoomReader,
    parse_rooms,
    reply_text,
)
from app.core.drawing.model import Page
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Sheet
from app.settings import Settings

KEY = "test-key-0123456789"


def room(kind: str, label: str, box: list[int]) -> str:
    return json.dumps({"type": kind, "label": label, "box_2d": box})


def reply(*rooms: str) -> str:
    return "[" + ", ".join(rooms) + "]"


def test_box_2d_is_y_first_and_becomes_page_fractions() -> None:
    [(kind, label, box)] = parse_rooms(reply(room("kitchen", "K", [100, 200, 300, 600])))
    assert (kind, label) == ("kitchen", "K")
    assert box == pytest.approx((0.2, 0.1, 0.6, 0.3))


def test_rooms_with_one_label_and_different_boxes_are_all_counted() -> None:
    # arm G's parser merged these (it deduplicated before reading box_2d): 3 bedrooms became 1
    rooms = parse_rooms(
        reply(
            room("bedroom", "MH", [100, 100, 300, 300]),
            room("bedroom", "MH", [100, 400, 300, 600]),
            room("bedroom", "MH", [400, 100, 600, 300]),
            room("bedroom", "MH", [400, 100, 600, 300]),  # an exact repeat counts once
        )
    )
    assert [kind for kind, _, _ in rooms] == ["bedroom"] * 3


def test_bathrooms_with_one_label_count_once() -> None:
    rooms = parse_rooms(
        reply(
            room("bathroom", "KPH", [100, 100, 300, 300]),
            room("bathroom", "KPH", [120, 100, 320, 300]),
            room("bathroom", "PH", [500, 500, 700, 700]),
        )
    )
    assert [label for _, label, _ in rooms] == ["KPH", "PH"]


def test_a_looping_reply_is_dropped_and_a_cut_reply_keeps_what_came_before() -> None:
    loop = [room("kitchen", "K", [100 * i, 500, 100 * i + 50, 550]) for i in range(7)]
    cut = reply(room("wc", "WC", [0, 0, 100, 100]), *loop)[:-1] + ', {"type": "sau'
    assert [kind for kind, _, _ in parse_rooms(cut)] == ["wc"]


def test_unknown_types_name_no_room_and_bad_boxes_cover_the_page() -> None:
    rooms = parse_rooms(
        '[{"type": "garage", "label": "AT"}, {"type": "sauna", "label": "S", "box_2d": [5, 5]}]'
    )
    assert rooms == [("sauna", "S", (0.0, 0.0, 1.0, 1.0))]


def test_thought_parts_are_left_out_and_an_empty_answer_is_an_error() -> None:
    answer = {"candidates": [{"content": {"parts": [{"text": "hmm", "thought": True},
                                                    {"text": "[]"}]}}]}  # fmt: skip
    assert reply_text(answer) == "[]"
    with pytest.raises(GeminiError, match="SAFETY"):
        reply_text({"candidates": [{"finishReason": "SAFETY"}]})
    with pytest.raises(GeminiError, match="no candidates"):
        reply_text({"promptFeedback": {"blockReason": "OTHER"}})


class FakeModel:
    name = "fake/low"

    def __init__(self, text: str | None) -> None:
        self.text = text  # None: the call fails
        self.calls = 0

    def ask(self, png: bytes, prompt: str) -> str:
        self.calls += 1
        Image.open(io.BytesIO(png)).verify()  # it is sent a PNG
        if self.text is None:
            raise GeminiError("HTTP 503 UNAVAILABLE")
        return self.text


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (300, 200), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_a_reply_is_cached_by_image_and_a_failure_is_not(tmp_path: Path) -> None:
    data = png()
    model = FakeModel(reply(room("wc", "WC", [0, 0, 100, 100])))
    reader = GeminiRoomReader(model, tmp_path)
    with Image.open(io.BytesIO(data)) as image:
        first, again = reader.read(data, image), reader.read(data, image)
    assert model.calls == 1
    assert first.rooms == again.rooms
    assert "cached reply" in again.note
    failing = GeminiRoomReader(FakeModel(None), tmp_path / "other")
    with Image.open(io.BytesIO(data)) as image, pytest.raises(GeminiError):
        failing.read(data, image)
    assert not (tmp_path / "other").exists()


class BytesFiles:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self, path: str) -> bytes:
        return self.data


def extract(model: FakeModel) -> Any:
    source = DrawingFile(path="data/cubicasa5k/x.png", size=1, sha256="0" * 64, kind="png")
    sheet = Sheet(file=source, pages=(Page(page=1, width=300, height=200, unit="px"),))
    reader = GeminiRoomReader(model, None)
    return GeminiRoomExtractor(BytesFiles(png()), reader).extract(source, sheet)


def test_the_extractor_reads_rooms_only() -> None:
    found = extract(
        FakeModel(
            reply(room("balcony", "PARVEKE", [0, 0, 100, 900]), room("hall", "", [200, 0, 300, 50]))
        )
    )
    assert found.read == ("room",)
    assert [(r.id, r.type, r.label, r.outdoor) for r in found.rooms] == [
        ("r1", "balcony", "PARVEKE", True),
        ("r2", "hall", None, False),
    ]
    assert "2 rooms" in found.notes[0]


def test_a_failed_call_leaves_the_rooms_unread_and_says_why() -> None:
    found = extract(FakeModel(None))
    assert found.read == ()  # unknown, not 0 rooms, and no other reader's rooms
    assert found.rooms == ()
    assert found.notes == ("gemini: rooms not read: HTTP 503 UNAVAILABLE",)


def test_the_client_sends_the_key_in_a_header_only_and_never_shows_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[urllib.request.Request] = []

    def refuse(request: urllib.request.Request, timeout: float) -> Any:
        sent.append(request)
        body = io.BytesIO(json.dumps({"error": {"status": "PERMISSION_DENIED"}}).encode())
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, body)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    client = GeminiClient(KEY, "gemini-3.5-flash", timeout_s=5)
    with pytest.raises(GeminiError) as error:
        client.ask(png(), "prompt")
    assert str(error.value) == "HTTP 403 PERMISSION_DENIED"
    [request] = sent
    assert request.get_header("X-goog-api-key") == KEY
    assert KEY not in request.full_url
    assert KEY not in repr(client)
    body = json.loads(request.data)  # type: ignore[arg-type]
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


def test_a_timeout_is_a_gemini_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(request: urllib.request.Request, timeout: float) -> Any:
        assert timeout == 5
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", slow)
    with pytest.raises(GeminiError, match="TimeoutError"):
        GeminiClient(KEY, "gemini-3.5-flash", timeout_s=5).ask(png(), "prompt")


def test_no_key_refuses_to_start_and_the_setting_hides_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(InvalidInputError, match="GEMINI_API_KEY"):
        GeminiClient("", "gemini-3.5-flash", timeout_s=5)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    settings = Settings()
    assert settings.gemini_api_key.get_secret_value() == KEY
    assert KEY not in repr(settings) and KEY not in str(settings.model_dump())

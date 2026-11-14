"""Two writers of one cache file (two backends on one cache folder, or two threads reading the
same pixels) both finish: each writes its own temporary file before the rename. With one fixed
`<key>.tmp`, the second writer's rename took the first one's file and the first raised
FileNotFoundError. The first writer is held between its write and its rename (no sleeps)."""

import io
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.adapters.decisions.g1main import FAMILIES, G1MainReader
from app.adapters.decisions_kind import KindReader
from app.adapters.raster_ocr.gemini import GeminiRoomReader
from app.adapters.review_store import JsonReviewStore

KIND_REPLY = json.loads(
    (Path(__file__).parent / "fixtures/decisions_kind/replies.json").read_text()
)[0]["reply"]
COUNTS_REPLY = {"answers": {
    f"g1_{key}": {"type": "choice", "probabilities": {"1": 1.0}}
    for key, _, _ in FAMILIES.values()}}  # fmt: skip


class Decider:
    model = "gemini-decision-1"

    def __init__(self, reply: dict[str, Any]) -> None:
        self.reply = reply

    def decide(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.reply


class RoomModel:
    name = "fake/low"

    def ask(self, png: bytes, prompt: str) -> str:
        return '[{"type": "wc", "label": "WC", "box_2d": [0, 0, 100, 100]}]'


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (30, 20), "white").save(out, format="PNG")
    return out.getvalue()


def kind(folder: Path) -> None:
    KindReader(Decider(KIND_REPLY), folder).read(png())


def counts(folder: Path) -> None:
    G1MainReader(Decider(COUNTS_REPLY), folder).read(png())


def rooms(folder: Path) -> None:
    with Image.open(io.BytesIO(png())) as image:
        GeminiRoomReader(RoomModel(), folder).read(image)


def review(folder: Path) -> None:  # a store per writer: one per process, so no shared lock
    JsonReviewStore(folder).update(None, "d1", lambda state: state)


@pytest.mark.parametrize("write", [kind, counts, rooms, review], ids=lambda w: w.__name__)
def test_two_writers_of_one_key_both_finish(
    write: Callable[[Path], None], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    held, released = threading.Event(), threading.Event()
    rename = Path.replace
    errors: list[BaseException] = []

    def hold_first(self: Path, target: Path) -> Path:
        if threading.current_thread() is first and not held.is_set():
            held.set()
            assert released.wait(10)
        return rename(self, target)

    def run() -> None:
        try:
            write(tmp_path)
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(Path, "replace", hold_first)
    first = threading.Thread(target=run)
    first.start()
    assert held.wait(10)  # the first writer wrote its temporary file and waits to rename it
    write(tmp_path)  # the second writer writes and renames the same key
    released.set()
    first.join(10)
    assert not first.is_alive()
    if errors:
        raise errors[0]
    assert len(list(tmp_path.rglob("*.json"))) == 1
    assert not list(tmp_path.rglob("*.tmp"))

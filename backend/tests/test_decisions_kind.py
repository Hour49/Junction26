"""The sheet-kind signal (app/adapters/decisions_kind): request, parse, cache, degraded mode.

No network: a fake decider replays replies. The 5 replies in fixtures/decisions_kind/ are the
prototype's own (prototypes/decide2/kind_parity.py checked that the adapter's request bodies hash
to the prototype's requests for those files, and that the parse gives the same probabilities).
"""

import base64
import io
import json
from pathlib import Path
from typing import Any

import pypdfium2
import pytest
from PIL import Image

from app.adapters.decisions.client import MODEL, DecisionsError
from app.adapters.decisions_kind import (
    KINDS,
    MAX_SIDE,
    PHOTO_AT,
    UNAVAILABLE,
    KindReader,
    KindSignal,
    KindUnavailable,
    page_png,
    parse,
    request_body,
)
from app.adapters.decisions_kind.probe import KindProbe
from app.core.ingest.model import Probed

FIXTURE = Path(__file__).parent / "fixtures/decisions_kind/replies.json"
# label -> (top kind, photo flag, P(floor plan)) as the prototype's report read them
EXPECTED = {
    "floor_plan": ("floor_plan", False, 0.7758),
    "elevation_section": ("elevation_section", False, 0.0045),
    "schedule": ("schedule", False, 0.0047),
    "photo_plan": ("photo_plan", True, 0.0337),
    "site_plan": ("site_plan", False, 0.0077),
}


class FakeDecider:
    def __init__(self, reply: dict[str, Any] | None = None, fail: str | None = None) -> None:
        self.reply = reply
        self.fail = fail
        self.bodies: list[dict[str, Any]] = []

    @property
    def model(self) -> str:
        return MODEL

    def decide(self, body: dict[str, Any]) -> dict[str, Any]:
        self.bodies.append(body)
        if self.fail is not None:
            raise DecisionsError(self.fail)
        assert self.reply is not None
        return self.reply


def png(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def replies() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text())


@pytest.mark.parametrize("row", replies(), ids=lambda row: row["label"])
def test_parity_with_the_prototype_replies(row: dict[str, Any]) -> None:
    signal = KindSignal(parse(row["reply"]), "")
    top, photo, p_plan = EXPECTED[row["label"]]
    assert signal.kind == top
    assert signal.photo is photo
    assert signal.p_plan == pytest.approx(p_plan, abs=1e-4)


def test_request_asks_one_six_way_choice_on_one_png() -> None:
    body = request_body(png(10, 10), MODEL)
    assert body["model"] == MODEL
    (block,) = body["input"]
    assert block["type"] == "image" and block["mime_type"] == "image/png"
    assert block["resolution"] == "high"
    assert base64.b64decode(block["data"]).startswith(b"\x89PNG")
    (question,) = body["questions"].values()
    assert question["type"] == "choice"
    assert question["instructions"] == "What is this file's first page?"
    assert list(question["criteria"]) == list(KINDS) and len(KINDS) == 6


def test_page_png_caps_the_long_side_and_keeps_small_images() -> None:
    big = Image.open(io.BytesIO(page_png(png(6144, 3072))))
    assert big.size == (MAX_SIDE, MAX_SIDE // 2)
    assert Image.open(io.BytesIO(page_png(png(300, 200)))).size == (300, 200)


def test_page_png_renders_a_pdf_first_page_to_the_long_side() -> None:
    pdf = pypdfium2.PdfDocument.new()
    pdf.new_page(400, 200)
    out = io.BytesIO()
    pdf.save(out)
    pdf.close()
    image = Image.open(io.BytesIO(page_png(out.getvalue())))
    assert image.size == (MAX_SIDE, MAX_SIDE // 2)


def test_read_caches_by_content_and_question(tmp_path: Path) -> None:
    decider = FakeDecider(reply=replies()[3]["reply"])  # the phone photo
    reader = KindReader(decider, tmp_path)
    first = reader.read(png(20, 20))
    second = reader.read(png(20, 20))
    assert isinstance(first, KindSignal) and isinstance(second, KindSignal)
    assert first.photo and first.probs == second.probs
    assert len(decider.bodies) == 1  # the second read came from the cache
    (cached,) = tmp_path.glob("*.json")
    assert cached.name.startswith("kind-") and MODEL in cached.name
    assert "photo of a plan" in first.line() and "cached" in second.note
    reader.read(png(21, 20))  # other content: a new request
    assert len(decider.bodies) == 2


def test_api_error_is_a_declared_unavailable_signal_and_nothing_is_cached(tmp_path: Path) -> None:
    reader = KindReader(FakeDecider(fail="HTTP 402"), tmp_path)
    result = reader.read(png(20, 20))
    assert isinstance(result, KindUnavailable)
    assert result.note == f"{UNAVAILABLE}: HTTP 402"
    assert not list(tmp_path.iterdir())


def test_unusable_reply_and_unreadable_file_are_unavailable(tmp_path: Path) -> None:
    bad = KindReader(FakeDecider(reply={"answers": {}}), tmp_path).read(png(20, 20))
    assert isinstance(bad, KindUnavailable) and "no kind probabilities" in bad.note
    assert not list(tmp_path.iterdir())
    decider = FakeDecider(reply=replies()[0]["reply"])
    junk = KindReader(decider, None).read(b"not an image")
    assert isinstance(junk, KindUnavailable) and junk.note.startswith(UNAVAILABLE)
    assert not decider.bodies


def test_plan_sheet_counts_a_photo_of_a_plan_as_a_plan() -> None:
    probs = dict.fromkeys(KINDS, 0.0) | {"floor_plan": 0.25, "photo_plan": 0.7, "schedule": 0.05}
    assert KindSignal(probs, "").p_plan_sheet == pytest.approx(0.95)


def test_photo_flag_is_at_the_threshold() -> None:
    probs = dict.fromkeys(KINDS, 0.0)
    assert not KindSignal(probs | {"photo_plan": PHOTO_AT - 1e-9}, "").photo
    assert KindSignal(probs | {"photo_plan": PHOTO_AT}, "").photo


# ---- KindProbe: the probe ingest would be given --------------------------------------------


class StubProbe:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def probe(self, data: bytes) -> Probed:
        return Probed(kind=self.kind, did="the probe's words")  # type: ignore[arg-type]


def kind_probe(kind: str, decider: FakeDecider) -> KindProbe:
    return KindProbe(StubProbe(kind), KindReader(decider, None))


def test_flagged_drawing_image_becomes_a_photo_of_a_plan() -> None:
    probed = kind_probe("jpeg_plan", FakeDecider(reply=replies()[3]["reply"])).probe(png(20, 20))
    assert probed.kind == "photo_plan"
    assert probed.did.startswith("the probe's words; sheet kind photo_plan (0.95)")
    assert probed.did.endswith("-> photo_plan")


def test_unflagged_image_keeps_the_probe_kind_with_the_signal_in_the_trace() -> None:
    plan = kind_probe("png_plan", FakeDecider(reply=replies()[0]["reply"])).probe(png(20, 20))
    assert plan.kind == "png_plan" and "P(plan) 0.78" in plan.did


def test_unavailable_signal_keeps_the_probe_answer_and_says_why() -> None:
    probed = kind_probe("jpeg_plan", FakeDecider(fail="HTTP 503")).probe(png(20, 20))
    assert probed == Probed(kind="jpeg_plan", did=f"the probe's words; {UNAVAILABLE}: HTTP 503")


def test_only_drawing_images_are_sent() -> None:
    # PDFs, camera photos, models and text keep the probe's own answer with no call (ingest-4):
    # the decider would flag a photo, so any call would change the kind or the words
    decider = FakeDecider(reply=replies()[3]["reply"])
    for kind in ("pdf_scan", "pdf_vector", "photo_plan", "ifc", "pdf_text", "text", "dxf",
                 "office", "unknown"):  # fmt: skip
        probed = kind_probe(kind, decider).probe(png(20, 20))
        assert probed == Probed(kind=kind, did="the probe's words")  # type: ignore[arg-type]
    assert not decider.bodies

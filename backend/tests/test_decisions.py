"""The Gemini Decisions adapter (app/adapters/decisions/): request, client, cache, F1main's count
swap and the answer confidence. Fake client and synthetic pages only, no network and no data/.
The parity fixture holds 5 val pages recorded by prototypes/decide/record_parity.py: the
detector's class counts, the API's reply, and the prototype's expected counts and probabilities."""

import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from app.adapters.decisions.client import DecisionsClient, DecisionsError, FakeDecisionsClient
from app.adapters.decisions.g1main import (
    FAMILIES,
    MAIN_DWELLING,
    G1MainReader,
    mime_of,
    questions,
    request_body,
    request_key,
)
from app.adapters.decisions.uses import (
    CLASSES,
    DecisionsConfidence,
    DecisionsCountExtractor,
)
from app.core.drawing.model import Element, ElementClass, Page, Plan, ReadClass, Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet

PARITY = Path(__file__).parent / "fixtures" / "decisions" / "parity.json"
PNG = b"\x89PNG\r\n\x1a\n" + b"page-one"
FILE = DrawingFile(path="data/cubicasa5k/x.png", size=1, sha256="0" * 64, kind="png")
SHEET = Sheet(file=FILE, pages=(Page(page=1, width=40, height=30, unit="px"),))
PLAN = Plan(id="p1", page=1, box=(0.1, 0.1, 0.9, 0.9))


class Files:
    def __init__(self, data: bytes = PNG) -> None:
        self.data = data

    def read(self, path: str) -> bytes:
        return self.data


class Inner:
    """A component (the detector) with fixed elements: `counts` per class, scores descending."""

    def __init__(self, counts: dict[str, int], read: Sequence[ReadClass] | None = None) -> None:
        elements = [
            Element.model_validate({"id": f"{kind}{n}", "class": kind, "page": 1,
                                    "box": (0.2, 0.2, 0.3, 0.3),
                                    "attrs": {"score": round(0.9 - n / 100, 3)}})
            for kind, count in counts.items() for n in range(count)
        ]  # fmt: skip
        self.found = Extracted(
            method="detector",
            scale=Scale(status="no_scale"),
            plans=(PLAN,),
            elements=tuple(elements),
            read=None if read is None else tuple(read),
        )

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return self.found


def reply(dists: dict[str, dict[int, float]]) -> dict[str, Any]:
    """A reply where each family not given is certain of 1."""
    return {"answers": {
        f"g1_{key}": {"type": "choice", "probabilities": {
            str(k): v for k, v in dists.get(family, {1: 1.0}).items()}}
        for family, (key, _, _) in FAMILIES.items()}}  # fmt: skip


def fake(answer: dict[str, Any], data: bytes = PNG) -> FakeDecisionsClient:
    return FakeDecisionsClient({request_key(request_body(data, "gemini-decision-1")): answer})


def counts(found: Extracted) -> Counter[ElementClass]:
    return Counter(e.class_ for e in found.elements)


def family_count(found: Extracted, family: str) -> int:
    return sum(counts(found)[kind] for kind in CLASSES[family][0])


# ---- request and client ------------------------------------------------------------------------


def test_questions_are_stoas_with_the_main_dwelling_rule_and_train_ranges() -> None:
    asked = questions()
    assert len(asked) == 12
    door = asked["g1_door"]
    assert door["type"] == "choice" and door["instructions"].endswith(MAIN_DWELLING)
    assert list(door["criteria"]) == [str(k) for k in range(44)]  # 0..43, the train max
    assert list(asked["g1_sauna"]["criteria"]) == ["0", "1", "2"]


def test_image_type_is_sniffed() -> None:
    assert mime_of(PNG) == "image/png"
    assert mime_of(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert mime_of(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    with pytest.raises(DecisionsError):
        mime_of(b"%PDF-1.7")


class Transport:
    def __init__(self, replies: list[tuple[int, Any]]) -> None:
        self.replies = replies
        self.sent: list[tuple[bytes, str]] = []

    def __call__(self, body: bytes, key: str, timeout: float) -> tuple[int, bytes]:
        self.sent.append((body, key))
        status, payload = self.replies.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return status, json.dumps(payload).encode()


def test_client_retries_429_and_5xx_only_and_keeps_the_key_out_of_body_and_errors() -> None:
    ok = {"answers": {}, "usage": {"total_input_tokens": 10}}
    transport = Transport([(429, {}), (503, {}), (200, ok)])
    client = DecisionsClient("secret-key", 5.0, transport, sleep=lambda s: None)
    assert client.decide({"q": 1}) == ok
    assert len(transport.sent) == 3
    assert all(key == "secret-key" and b"secret-key" not in body for body, key in transport.sent)
    for status in (400, 402, 403):
        failing = Transport([(status, {"error": {"status": "RESOURCE_EXHAUSTED",
                                                 "message": "secret-key in body"}})])  # fmt: skip
        with pytest.raises(DecisionsError) as error:
            DecisionsClient("secret-key", 5.0, failing, sleep=lambda s: None).decide({})
        assert len(failing.sent) == 1
        assert str(error.value) == f"HTTP {status} RESOURCE_EXHAUSTED"


def test_client_network_failure_is_an_error_not_a_retry() -> None:
    transport = Transport([(0, TimeoutError("timed out")), (200, {})])
    with pytest.raises(DecisionsError, match="no answer: TimeoutError"):
        DecisionsClient("k", 5.0, transport, sleep=lambda s: None).decide({})
    assert len(transport.sent) == 1


def test_client_needs_a_key() -> None:
    with pytest.raises(InvalidInputError, match="GEMINI_API_KEY"):
        DecisionsClient("", 5.0)


def test_reader_caches_a_reply_on_disk_and_not_a_broken_one(tmp_path: Path) -> None:
    client = fake(reply({"door": {3: 0.7, 4: 0.3}}))
    first = G1MainReader(client, tmp_path).read(PNG)
    second = G1MainReader(client, tmp_path).read(PNG)
    assert client.calls == 1 and "cached reply" in second.note
    assert first.families["door"].top == 3 and second.families["door"].p(4) == 0.3
    broken = fake({"answers": {"g1_door": {}}}, b"\x89PNG other")
    with pytest.raises(DecisionsError, match="no probabilities for door"):
        G1MainReader(broken, tmp_path).read(b"\x89PNG other")
    assert len(list(tmp_path.iterdir())) == 1


# ---- uses --------------------------------------------------------------------------------------


def test_swap_down_drops_the_least_sure_detections() -> None:
    inner = Inner({"toilet": 3, "door": 5})
    client = fake(reply({"toilet": {1: 0.9, 3: 0.01, 2: 0.09}, "door": {9: 1.0}}))
    found = DecisionsCountExtractor(inner, Files(), G1MainReader(client, None)).extract(FILE, SHEET)
    kept = [e.id for e in found.elements if e.class_ == "toilet"]
    assert kept == ["toilet0"]  # scores 0.9, 0.89, 0.88: the two lowest go
    assert counts(found)["door"] == 5  # doors are never swapped (threshold 0)
    assert "toilet 3 -> 1 (P(3) = 0.010)" in found.notes[-1]


def test_swap_up_adds_unlocated_elements_on_the_plan() -> None:
    inner = Inner({"shower": 1}, read=("shower", "bathtub"))
    client = fake(reply({"shower+bathtub": {1: 0.2, 2: 0.8}}))
    found = DecisionsCountExtractor(inner, Files(), G1MainReader(client, None)).extract(FILE, SHEET)
    added = [e for e in found.elements if e.attrs.get("located") is False]
    assert family_count(found, "shower+bathtub") == 2 and len(added) == 1
    assert added[0].class_ == "shower" and added[0].box == PLAN.box and added[0].plan == "p1"
    assert added[0].attrs["source"] == "decisions"


def test_a_class_the_component_did_not_read_is_not_swapped() -> None:
    inner = Inner({"door": 2}, read=("door", "window"))
    client = fake(reply({"sauna": {1: 1.0}, "toilet": {2: 1.0}}))
    found = DecisionsCountExtractor(inner, Files(), G1MainReader(client, None)).extract(FILE, SHEET)
    assert counts(found) == Counter({"door": 2})
    assert "counts kept" in found.notes[-1]


def test_an_api_error_leaves_the_counts_and_says_so() -> None:
    inner = Inner({"toilet": 3})
    client = FakeDecisionsClient({}, fail="HTTP 503 UNAVAILABLE")
    found = DecisionsCountExtractor(inner, Files(), G1MainReader(client, None)).extract(FILE, SHEET)
    assert found.elements == inner.found.elements
    assert found.notes[-1] == (
        "decisions: confidence not available: HTTP 503 UNAVAILABLE; counts left as read"
    )
    confidence = DecisionsConfidence(Files(), G1MainReader(client, None))
    got = confidence.probability(FILE.path, "toilet", 3)
    assert got.value is None and "confidence not available: HTTP 503" in got.note


def test_confidence_reads_a_page_once_and_refuses_what_it_cannot_score() -> None:
    client = fake(reply({"room:wc": {0: 0.3, 1: 0.7}}))
    confidence = DecisionsConfidence(Files(), G1MainReader(client, None))
    assert confidence.probability(FILE.path, "room:wc", 1).value == 0.7
    assert confidence.probability(FILE.path, "room:wc", 2).value == 0.0
    assert client.calls == 1
    assert confidence.probability(FILE.path, "area:room:*", 3).value is None
    assert confidence.probability(FILE.path, "door", 2.5).value is None


# ---- parity with the prototype (5 recorded val pages) ------------------------------------------


@pytest.mark.parametrize("page", json.loads(PARITY.read_text()), ids=lambda p: p["page"])
def test_parity_with_the_prototype(page: dict[str, Any]) -> None:
    data = b"\x89PNG " + page["page"].encode()
    client = fake(page["reply"], data)
    reader = G1MainReader(client, None)
    inner = Inner(page["detector"])
    found = DecisionsCountExtractor(inner, Files(data), reader).extract(FILE, SHEET)
    assert {f: family_count(found, f) for f in CLASSES} == page["expected_counts"]
    changed = [f for f in CLASSES if family_count(found, f) != family_count(inner.found, f)]
    assert changed == page["changed"]
    confidence = DecisionsConfidence(Files(data), reader)
    for family, top in page["expected_top"].items():
        got = confidence.probability(FILE.path, family, top)
        assert got.value == pytest.approx(page["expected_p_top"][family], abs=1e-6)

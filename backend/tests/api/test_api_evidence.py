"""GET /api/drawings/{id}/evidence.png: the answer's proof drawn on its page (docs/GOLDEN.md)."""

import io
from dataclasses import replace
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.adapters.decisions.uses import Confidence
from app.adapters.evidence_render import (
    MARGIN,
    Label,
    _bounds,
    _font,
    _in_polygon,
    _legend_lines,
    _overlap,
    _wrap,
    place_labels,
    render,
)
from app.api.ask import asked_on
from app.api.drawings import headline
from app.composition import DECISIONS_SIGNAL
from app.core.drawing.model import Table, TableRow
from app.core.review.ask import Asked
from app.core.review.model import MarkView
from app.core.review.proof import NO_PROOF, ClassKey, colour, number, schedule_proof
from app.settings import Settings
from scripts.make_sample_archive import build_archive

DOORS = "How many doors are there?"


def evidence(client: TestClient, drawing_id: str, question: str, width: int = 400) -> Image.Image:
    response = client.get(
        f"/api/drawings/{drawing_id}/evidence.png", params={"question": question, "width": width}
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"  # a review edit changes it
    return Image.open(io.BytesIO(response.content)).convert("RGB")


def red_pixels(image: Image.Image, box: tuple[float, float, float, float]) -> int:
    """Pixels of the door colour around a mark's box (its outline and number)."""
    red = tuple(int(colour("door")[at : at + 2], 16) for at in (1, 3, 5))
    x0, y0, x1, y1 = box
    w, h = image.size
    area = (int(x0 * w) - 20, int(y0 * h) - 30, int(x1 * w) + 20, int(y1 * h) + 20)
    return sum(1 for pixel in image.crop(area).get_flattened_data() if pixel == red)


def test_a_count_is_drawn_with_each_mark_outlined_in_its_class_colour_and_a_footer(
    client: TestClient, drawing_id: str
) -> None:
    marks = client.post("/api/ask", json={"drawing_id": drawing_id, "question": DOORS}).json()
    page = client.get(marks["pages"][0]["url"], params={"width": 400})
    plain = Image.open(io.BytesIO(page.content))
    drawn = evidence(client, drawing_id, DOORS)
    assert drawn.width == plain.width == 400
    assert drawn.height > plain.height  # the question, answer and colour key under the page
    for mark in marks["marks"]:
        assert red_pixels(drawn, mark["box"]) > 20
        assert red_pixels(plain.convert("RGB"), mark["box"]) == 0


def test_a_refusal_is_drawn_too(client: TestClient, drawing_id: str) -> None:
    assert evidence(client, drawing_id, "What colour is the roof?").width == 400


def test_the_width_is_one_of_the_page_widths(client: TestClient, drawing_id: str) -> None:
    response = client.get(
        f"/api/drawings/{drawing_id}/evidence.png", params={"question": DOORS, "width": 500}
    )
    assert (response.status_code, response.json()["code"]) == (422, "invalid")
    missing = client.get(f"/api/drawings/{drawing_id}/evidence.png")
    assert missing.status_code == 422


def test_a_model_fact_without_a_page_is_drawn_as_its_tables(
    client: TestClient, settings: Settings
) -> None:
    settings.sample_archive.write_bytes(build_archive())
    status = client.get(client.post("/api/projects/sample").json()["url"]).json()
    house = next(item for item in status["drawings"] if item["file"] == "model/house.ifc")
    question = "How many doors are shown on the floor plan of 'Ground Floor'?"
    proof = client.post(
        "/api/ask", json={"drawing_id": house["drawing_id"], "question": question}
    ).json()["proof"]
    assert proof["kind"] == "model" and len(proof["objects"]) == 2
    drawn = evidence(client, house["drawing_id"], question, width=1600)
    assert drawn.width == 1600  # objects with their GlobalIds, the storey table, the footer
    assert drawn.height > 200


def test_a_schedule_is_zoomed_to_its_table_and_every_footer_line_fits() -> None:
    page = Image.new("RGB", (3200, 2000), "white")
    buffer = io.BytesIO()
    page.save(buffer, format="PNG")
    rows = [(0.1, 0.1 + 0.02 * at, 0.3, 0.12 + 0.02 * at) for at in range(3)]
    marks = [
        MarkView(
            id=f"e{n}",
            n=n,
            page=1,
            box=box,
            polygon=None,
            state="counted",
            value=None,
            label=None,
            ref=None,
            reason=None,
        )
        for n, box in enumerate(rows, start=1)
    ]
    cells = tuple(TableRow(cells=(str(n),), box=box) for n, box in enumerate(rows))
    table = Table(id="t1", page=1, box=(0.1, 0.1, 0.3, 0.2), columns=("NO.",), rows=cells)
    proof = schedule_proof(marks, (table,), 3)
    long = "On sheet A-801 of the drawings, how many doors are listed? " * 4
    png = render(buffer.getvalue(), 1, marks, proof, long, "a credit " * 40, 1600)
    drawn = Image.open(io.BytesIO(png))
    assert drawn.width == 1600
    assert drawn.height < 1600 * 2000 / 3200  # the table's crop, not the whole page
    lines = _wrap(long, _font(26), 1568)
    assert len(lines) > 1
    assert all(_font(26).getlength(line) <= 1568 for line in lines)


def fixed_size(text: str, size: int) -> tuple[float, float]:
    """A label box of 0.6 em per character, 1.2 em high: the shape of a real font's."""
    return 0.6 * size * len(text) + 6, 1.2 * size + 4


def fixed_rect(label: Label) -> list[tuple[float, float]]:
    """The label's box centred on its outline's centroid, as the renderer did before."""
    w, h = fixed_size(label.text, label.size)
    cx = sum(x for x, _ in label.points) / len(label.points)
    cy = sum(y for _, y in label.points) / len(label.points)
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy + h / 2)]


def test_labels_of_two_overlapping_rooms_sit_inside_their_own_room_and_never_overlap() -> None:
    first = [(100.0, 100.0), (300.0, 100.0), (300.0, 200.0), (100.0, 200.0)]
    # almost on top of the first: both centroids' labels would cover each other
    second = [(120.0, 110.0), (320.0, 110.0), (320.0, 210.0), (120.0, 210.0)]
    labels = [Label("16.78", first, 22), Label("15.56", second, 22)]
    naive = [_bounds(fixed_rect(label)) for label in labels]
    assert _overlap(*naive)  # what centring each label on its room would do
    placed = place_labels(labels, fixed_size, 800, 600)
    rects = [spot.rect for spot in placed]
    assert all(rect is not None for rect in rects)
    a, b = (rect for rect in rects if rect is not None)
    assert not _overlap(a, b)
    for label, spot in zip(labels, placed, strict=True):
        assert spot.leader is None  # there is room inside, so no leader line
        assert spot.rect is not None
        x0, y0, x1, y1 = spot.rect
        assert all(_in_polygon(p, label.points) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


def test_crowded_small_marks_shrink_then_move_out_on_leaders_without_overlap() -> None:
    doors = [
        [
            (400.0 + 6 * at, 300.0),
            (404.0 + 6 * at, 300.0),
            (404.0 + 6 * at, 310.0),
            (400.0 + 6 * at, 310.0),
        ]
        for at in range(12)
    ]  # twelve 4 px doors side by side in a corridor: no number fits inside any
    labels = [Label(str(n), points, 20) for n, points in enumerate(doors, start=1)]
    placed = place_labels(labels, fixed_size, 1000, 800)
    rects = [spot.rect for spot in placed if spot.rect is not None]
    assert len(rects) == 12
    assert all(spot.leader is not None for spot in placed)
    assert not any(_overlap(a, b) for at, a in enumerate(rects) for b in rects[at + 1 :])
    door_boxes = [(p[0][0], p[0][1], p[2][0], p[2][1]) for p in doors]
    assert not any(_overlap(rect, door) for rect in rects for door in door_boxes)


def test_a_label_with_no_room_anywhere_is_left_for_the_list_under_the_page() -> None:
    tiny = [(1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)]
    (spot,) = place_labels([Label("1234567890", tiny, 20)], fixed_size, 20, 20)
    assert spot.rect is None


def test_marks_counted_without_a_position_are_named_in_the_legend_and_it_wraps_to_fit() -> None:
    keys = (
        ClassKey(label="shower", colour=colour("shower"), count=3, unlocated=2,
                 note="2 counted without a mark (second reader)"),
        ClassKey(label="bathtub", colour=colour("bathtub"), count=1),
    )  # fmt: skip
    proof = NO_PROOF.model_copy(update={"kind": "count", "legend": keys})
    room = 400 - 2 * MARGIN
    lines = _legend_lines(proof, _font(14), 14, room)
    texts = [text for line in lines for _, _, text in line]
    assert " ".join(texts) == "shower 3 (2 counted without a mark (second reader)) bathtub 1"
    assert len(texts) > 2  # at 400 px the shower key alone is wider than the page: it wraps
    assert [swatch for line in lines for _, swatch, _ in line] == [
        colour("shower"), *[None] * (len(texts) - 2), colour("bathtub"),
    ]  # fmt: skip
    assert all(
        x + (14 + 6 if swatch else 0) + _font(14).getlength(text) <= MARGIN + room
        for line in lines
        for x, swatch, text in line
    )
    wide = _legend_lines(proof, _font(22), 22, 1600 - 2 * MARGIN)
    assert len(wide) == 1  # both keys on one line where they fit


def test_the_picture_never_prints_the_answer_s_score(raster: tuple[TestClient, str]) -> None:
    """The score is Gemini's raw choice score, not a probability the answer is right: evidence.png
    is the same with DECISIONS_CONFIDENCE on as off."""
    client, drawing_id = raster
    url = f"/api/drawings/{drawing_id}/evidence.png"
    plain = client.get(url, params={"question": DOORS}).content
    state = cast(FastAPI, client.app).state
    state.answering = replace(state.answering, confidence=Scored, signal=DECISIONS_SIGNAL)
    assert client.post("/api/ask", json={"drawing_id": drawing_id, "question": DOORS}).json()[
        "confidence"
    ] == {"signal": "g1main", "score": 0.87, "calibrated": False}
    assert client.get(url, params={"question": DOORS}).content == plain


class Scored:
    def __init__(self, files: object) -> None:
        pass

    def probability(self, path: str, family: str, value: object) -> Confidence:
        return Confidence(0.87, "decisions: test")


def test_a_room_s_label_sits_in_its_corner_clear_of_its_printed_name() -> None:
    room = [(100.0, 100.0), (500.0, 100.0), (500.0, 400.0), (100.0, 400.0)]
    door = [(600.0, 100.0), (620.0, 100.0), (620.0, 110.0), (600.0, 110.0)]
    big, small = place_labels([Label("1", room, 20), Label("2", door, 20)], fixed_size, 800, 600)
    assert big.rect is not None and big.leader is None
    assert big.rect[2] < 300 and big.rect[3] < 250  # the top-left quarter, not the middle
    assert small.rect is not None  # a small outline is labelled as before


def test_a_sum_s_headline_is_rounded_as_its_arithmetic_and_its_key_has_no_count(
    client: TestClient, drawing_id: str
) -> None:
    question = "What is the net floor area of all indoor rooms in m²?"
    asked = ask_core(client, drawing_id, question)
    assert asked.proof.kind == "sum"
    total = number(float(asked.answer.answer or 0))
    assert headline(question, asked) == f"{question}  ->  {total} m2"
    assert asked.proof.arithmetic is not None and f"= {total} m2" in asked.proof.arithmetic
    lines = _legend_lines(asked.proof, _font(14), 14, 1600)
    texts = [text for line in lines for _, _, text in line]
    assert texts == [key.label for key in asked.proof.legend if key.count]


def ask_core(client: TestClient, drawing_id: str, question: str) -> Asked:
    """The use case behind POST /api/ask, as evidence.png runs it."""
    app = cast(FastAPI, client.app)
    ingest = app.state.ingest
    drawing = ingest.drawing(drawing_id)
    return asked_on(question, drawing, drawing_id, app.state.reviews, app.state.answering, ingest)

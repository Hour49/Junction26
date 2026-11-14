"""The local gate scores lgate / lgate2 from runtime readings: the core's score against local-dec's
offline fit, the reading taken from a stored drawing, and the model loader.

The parity fixture was recorded by scripts/check_local_gate.py --arm C1 --fixture 5: the lgate2-rt
model fit on config C1's val answers and 5 val units per family (pages renamed val-<n>) with their
readings and the offline value. The script itself checks all 3,382 val units of each model."""

import json
from pathlib import Path

import pytest

from app.adapters.local_gate import load_local_gate
from app.core.answering.local_gate import (
    GateReading,
    LocalGateModel,
    features,
    reading_of,
    score,
)
from app.core.drawing.model import Drawing, Element, Page, Plan, ReaderView, Scale
from app.core.errors import InvalidInputError

PARITY = Path(__file__).parent / "fixtures" / "local_gate" / "parity.json"
BOX = (0.1, 0.1, 0.2, 0.2)


def fixture() -> dict:
    return json.loads(PARITY.read_text())


def model_of(doc: dict) -> LocalGateModel:
    return LocalGateModel(
        name=doc["name"],
        families=tuple(doc["families"]),
        readers=tuple(doc["readers"]),
        blocks=frozenset(doc["blocks"]),
        prior={f: {int(k): v for k, v in d.items()} for f, d in doc["prior"].items()},
        mu=tuple(doc["mu"]),
        sd=tuple(doc["sd"]),
        coef=tuple(doc["coef"]),
        intercept=doc["intercept"],
    )


def test_the_core_reproduces_the_offline_lgate2_values() -> None:
    doc = fixture()
    model = model_of(doc["model"])
    assert {u["family"] for u in doc["units"]} == set(model.families)
    for u in doc["units"]:
        reading = GateReading(
            u["answer"], u["probs"], u["readers"], tuple(u["scores"]), u["plans"], u["arbiter_p"]
        )
        got = score(model, u["family"], reading)
        assert got == pytest.approx(u["expected"], abs=1e-6), (u["page"], u["family"])


def element(kind: str, score: float | None, n: int) -> Element:
    attrs = {} if score is None else {"score": score}
    return Element.model_validate(
        {"id": f"{kind}{n}", "class": kind, "page": 1, "box": BOX, "attrs": attrs}
    )


def test_the_reading_comes_from_the_stored_drawing() -> None:
    counted = (element("door", 0.9, 1), element("door", None, 2), element("toilet", 0.4, 3))
    drawing = Drawing(
        file="data/cubicasa5k/x.png",
        pages=(Page(page=1, width=40, height=30, unit="px"),),
        scale=Scale(status="no_scale"),
        plans=(Plan(id="p1", page=1, box=(0, 0, 1, 1)), Plan(id="p2", page=1, box=(0, 0, 1, 1))),
        elements=counted,
        double_check={
            "l1": ReaderView(read=("door", "toilet"), elements=(element("door", 0.8, 9),)),
            "m1": ReaderView(read=("toilet",), elements=()),  # did not look for doors
        },
    )
    door = reading_of(drawing, "door", 2, probs=[0.1, 0.2, 0.7], arbiter_p=0.6)
    assert door == GateReading(2, [0.1, 0.2, 0.7], {"l1": 1}, (0.9, None), 2, 0.6)
    assert reading_of(drawing, "toilet", 1).readers == {"l1": 0, "m1": 0}
    plan = reading_of(drawing, "plan", 2)
    assert (plan.readers, plan.scores, plan.plans) == ({}, (), 2)  # readers keep no plans
    assert reading_of(drawing, "room:wc", 1).readers == {}


def tiny(*blocks: str, families: tuple[str, ...] = ("door", "room:wc")) -> LocalGateModel:
    width = {"l1": 3, "readers": 5, "extras": 4, "arbiter_p": 1}
    n = 2 + sum(width[b] for b in blocks) + len(families)
    return LocalGateModel(
        "t", families, ("l1", "m1"), frozenset(blocks), {f: {1: 0.5} for f in families},
        (0.0,) * n, (1.0,) * n, (0.0,) * n, 0.0,
    )  # fmt: skip


def test_a_reader_that_did_not_look_gives_nothing_and_has_no_say_in_the_share() -> None:
    model = tiny("readers")
    x = features(model, "door", GateReading(1, readers={"l1": 1}))
    # a, log prior, [l1 == a, m1 == a], [|l1 - a|, |m1 - a|], share, one-hot
    assert x[2:7] == [1.0, 0.0, 0.0, 0.0, 1.0]
    rooms = features(model, "room:wc", GateReading(1, readers={"l1": 4}))
    assert rooms[2:7] == [0.0] * 5  # readers say nothing of rooms
    far = features(model, "door", GateReading(1, readers={"l1": 9, "m1": 3}))
    assert far[2:7] == [0.0, 0.0, 3.0, 2.0, 0.0]  # |9 - 1| is capped at 3
    plan = features(tiny("readers", families=("plan",)), "plan", GateReading(1, readers={"l1": 1}))
    assert plan[2:7] == [0.0] * 5  # readers keep no plans: their counts are not used


def test_lgate2_scores_leave_unscored_elements_out() -> None:
    x = features(tiny("extras"), "door", GateReading(2, scores=(0.4, None, 0.8), plans=1))
    assert x[2:6] == pytest.approx([0.4, 0.6, 1.0, 1.0])
    empty = features(tiny("extras"), "door", GateReading(0))
    assert empty[2:6] == [1.0, 1.0, 0.0, 0.0]


def test_a_model_with_l1_needs_its_probabilities_and_an_unfit_family_has_no_score() -> None:
    with pytest.raises(ValueError, match="L1"):
        score(tiny("l1"), "door", GateReading(1))
    assert score(tiny("l1"), "door", GateReading(1, probs=[0.5, 0.5])) == pytest.approx(0.5)
    assert score(tiny("l1"), "window", GateReading(1, probs=[0.5, 0.5])) is None


def test_the_loader_reads_the_model_and_refuses_a_broken_one(tmp_path: Path) -> None:
    doc = fixture()["model"]
    path = tmp_path / "lgate2-rt.json"
    path.write_text(json.dumps(doc))
    assert load_local_gate(path) == model_of(doc)
    for broken, says in (
        ({**doc, "schema": "x"}, "local_gate_v1"),
        ({**doc, "blocks": ["l1", "seg"]}, "unknown blocks"),
        ({**doc, "coef": doc["coef"][:-1]}, "differ in length"),
        ({**doc, "prior": {}}, "no prior"),
    ):
        path.write_text(json.dumps(broken))
        with pytest.raises(InvalidInputError, match=says):
            load_local_gate(path)

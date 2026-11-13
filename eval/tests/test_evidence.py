"""Evidence hit rate (golden-8 brief): subjects from the wording, the gold items they pick, the
centre-in-box hit test, and precision and recall, on made-up data."""

from typing import Any

import pytest

from stoa_eval.evidence_scoring import (
    APARTMENT_COUNT,
    UNKNOWN,
    WHOLE_MODEL,
    Subject,
    Target,
    hits,
    oracle_evidence,
    score_evidence,
    subject_of,
    targets,
)
from stoa_eval.extraction import Extraction
from stoa_eval.models import Answer, Evidence, GoldenItem, QuestionType
from tests.test_extraction_scoring import extraction

PLAN = "data/swiss_dwellings/demo.pdf"


@pytest.mark.parametrize(
    ("question", "type_", "family"),
    [
        ("How many windows are shown on this floor plan?", "count", "window"),
        ("Kuinka monta ikkunaa pohjapiirustuksessa on?", "count", "window"),
        ("Wie viele Türen sind auf diesem Grundriss eingezeichnet?", "count", "door"),
        ("Combien de portes sont dessinées sur ce plan ?", "count", "door"),
        ("Kuinka monta ovea pohjapiirustuksessa on?", "count", "door"),
        # the sink question names the kitchen and the bathroom: still the sinks
        ("How many sinks (kitchen and bathroom combined) are drawn?", "count", "sink"),
        ("Wie viele Lavabos sind auf diesem Grundriss eingezeichnet?", "count", "sink"),
        ("How many showers and bathtubs are drawn in total?", "count", "bathtub+shower"),
        ("Wie viele Duschen sind eingezeichnet?", "count", "shower"),
        ("Combien de baignoires sont dessinées ?", "count", "bathtub"),
        ("How many toilet bowls (WC seats) are drawn?", "count", "toilet"),
        ("Combien de WC sont dessinés sur ce plan ?", "count", "toilet"),
        # the bathroom question says "not counting WC rooms"; the WC room one says "toilet rooms"
        ("How many bathrooms are there, not counting separate WC rooms?", "count", "room:bathroom"),
        ("How many separate WC rooms (toilet rooms) are there?", "count", "room:wc"),
        ("How many bedrooms (makuuhuone) are on this floor plan?", "count", "room:bedroom"),
        ("How many kitchens (including kitchenettes) are there?", "count", "room:kitchen"),
        ("How many balconies are on this floor plan?", "count", "room:balcony"),
        ("Kuinka monta saunaa pohjapiirustuksessa on?", "count", "sauna (stove)"),
        ("How many floors (storeys) does this floor plan show?", "count", "plan"),
        ("How many rooms labelled 'Bad' are there on this floor?", "count", "rooms labelled"),
        ("Wie viele Räume mit der Bezeichnung «Bad» gibt es?", "count", "rooms labelled"),
        ("How many rooms (spaces) are shown on the floor plan of 'EG'?", "count", "all rooms"),
        ("Ile schodów pokazano na rzucie kondygnacji 'P1'?", "count", "stair"),
        ("Hvor mange søjler er vist på plantegningen for 'Stue'?", "count", "column"),
        ("What is the net floor area of apartment B in m²?", "area", "apartment rooms"),
        ("Quelle est la surface nette de l'appartement C en m² ?", "area", "apartment rooms"),
        ("What is the total net floor area of all numbered indoor rooms?", "area",
         "numbered indoor rooms"),
        ("What is the total net area of all rooms labelled 'Bad' on this floor?", "area",
         "rooms labelled"),
        ("What is the net floor area of room 2.03 ('Bad') in m²?", "area", "room by number"),
        ("What is the net floor area of room U12 ('Keller') in m²?", "area", "room by number"),
        ("What is the net floor area of the room 'Kitchen (01)' on 'EG', in m²?", "area",
         "room by name"),
        ("What is the total net floor area of all rooms (spaces) on 'EG', in m²?", "area",
         "all rooms"),
        ("What is the total net side area of all walls on 'EG', in m²?", "area", "wall"),
        ("Hvad er den samlede længde af alle vægge på 'Stue' i meter?", "length", "wall"),
        ("What is the total net volume of all slabs on 'EG', in m³?", "volume", "slab"),
    ],
)  # fmt: skip
def test_the_wording_gives_the_subject(question: str, type_: str, family: str) -> None:
    subject = subject_of(question, type_)
    assert isinstance(subject, Subject) and subject.family == family


def test_values_come_from_the_question() -> None:
    assert subject_of("How many rooms labelled 'Chambre' are there?", "count") == Subject(
        "rooms labelled", rooms="label", value="Chambre"
    )
    room = subject_of("What is the net floor area of room 2.03 ('Bad') in m²?", "area")
    assert isinstance(room, Subject) and room.value == "2.03"
    apartment = subject_of("Wie gross ist die Nettowohnfläche von Wohnung B in m²?", "area")
    assert isinstance(apartment, Subject) and apartment.value == "B"
    named = subject_of("Wie groß ist die Netto-Grundfläche des Raums „Küche“ im „EG“?", "area")
    assert isinstance(named, Subject) and named.value == "Küche"
    enlarged = subject_of("How many lavatories are drawn in enlarged plan 3C?", "count")
    assert isinstance(enlarged, Subject) and (enlarged.family, enlarged.plan) == ("sink", "3C")


@pytest.mark.parametrize(
    ("question", "type_", "reason"),
    [
        ("How many doors are there in the model 'Haus'?", "count", WHOLE_MODEL),
        ("Wie viele Fenster enthält das Modell „Haus“?", "count", WHOLE_MODEL),
        ("How many apartments are shown on this floor plan?", "count", APARTMENT_COUNT),
        ("How many cats are on this floor plan?", "count", UNKNOWN),
        ("What is the height of the ceiling?", "length", UNKNOWN),
        ("Which software made this model?", "text", UNKNOWN),
    ],
)
def test_wordings_without_a_subject_say_why(question: str, type_: str, reason: str) -> None:
    assert subject_of(question, type_) == reason


def room(id_: str, box: list[float], **fields: Any) -> dict[str, Any]:
    return {"id": id_, "type": "other", "page": 1, "box": box, **fields}


def element(id_: str, class_: str, box: list[float], **fields: Any) -> dict[str, Any]:
    return {"id": id_, "class": class_, "page": 1, "box": box, **fields}


def gold() -> Extraction:
    return extraction(
        file=PLAN,
        plans=[
            {"id": "p3C", "page": 1, "box": [0.0, 0.0, 0.5, 1.0]},
            {"id": "p3D", "page": 1, "box": [0.5, 0.0, 1.0, 1.0]},
        ],
        elements=[
            element("d1", "door", [0.10, 0.10, 0.12, 0.14], plan="p3C"),
            element("d2", "door", [0.60, 0.10, 0.62, 0.14], plan="p3D"),
            element("w1", "window", [0.30, 0.00, 0.40, 0.01], plan="p3C"),
            element("s1", "sink", [0.20, 0.50, 0.22, 0.52], plan="p3C"),
            element("s2", "sink", [0.70, 0.50, 0.72, 0.52], plan="p3D"),
            element("t1", "toilet", [0.25, 0.50, 0.27, 0.53], plan="p3C"),
        ],
        rooms=[
            room("r1", [0.0, 0.0, 0.2, 0.2], type="bedroom", label="Zimmer", apartment="aA",
                 attrs={"number": "1.01"}),
            room("r2", [0.2, 0.0, 0.4, 0.2], type="bathroom", label="Bad", apartment="aA",
                 attrs={"number": "1.02"}),
            room("r3", [0.4, 0.0, 0.5, 0.2], type="balcony", label="Balkon", apartment="aA",
                 outdoor=True, attrs={"number": "1.03"}),
            room("r4", [0.5, 0.0, 0.6, 0.2], type="shaft", label="Treppenhaus", apartment="aA",
                 attrs={"number": "1.04"}),
            room("r5", [0.6, 0.0, 0.8, 0.2], type="bathroom", label="BAD", apartment="aB",
                 attrs={"number": "2.01"}),
            room("r6", [0.8, 0.0, 1.0, 0.2], type="other", label="Lift"),
            room("r7", [0.0, 0.5, 0.2, 0.7], label="Küche 0.1",
                 attrs={"ifc_name": "0.1", "ifc_long_name": "Küche"}),
        ],
        apartments=[{"id": "aA", "label": "A"}, {"id": "aB", "label": "B"}],
    )  # fmt: skip


def picked(question: str, type_: str) -> list[str]:
    subject = subject_of(question, type_)
    assert isinstance(subject, Subject), subject
    return [target.id for target in targets(subject, gold())]


def test_each_rule_picks_its_gold_items() -> None:
    assert picked("How many doors are drawn?", "count") == ["d1", "d2"]
    assert picked("How many showers and bathtubs are drawn?", "count") == []
    assert picked("How many bathrooms are there?", "count") == ["r2", "r5"]
    assert picked("How many rooms labelled 'bad' are there?", "count") == ["r2", "r5"]  # any case
    assert picked("What is the net floor area of room 1.02 ('Bad') in m²?", "area") == ["r2"]
    # an apartment's indoor rooms: no balcony, no shaft
    assert picked("What is the net floor area of apartment A in m²?", "area") == ["r1", "r2"]
    # numbered and indoor: the shaft counts here (as the swiss totals do), the unnumbered lift not
    numbered = picked("What is the total net floor area of all numbered indoor rooms?", "area")
    assert numbered == ["r1", "r2", "r4", "r5"]
    for name in ("Küche 0.1", "Küche", "0.1", "Küche (0.1)"):  # label, IFC long name and name
        assert picked(f"What is the net floor area of the room '{name}' on 'EG'?", "area") == ["r7"]
    assert picked("How many floors (storeys) does this floor plan show?", "count") == [
        "p3C",
        "p3D",
    ]
    assert picked("How many lavatories are drawn in enlarged plan 3C?", "count") == ["s1"]
    assert picked("How many water closets are drawn in enlarged plan 3D?", "count") == []


def test_the_hit_is_the_box_centre_in_the_gold_box() -> None:
    target = Target("d1", 1, (0.10, 0.10, 0.20, 0.20))

    def at(box: tuple[float, float, float, float], page: int = 1, file: str = PLAN) -> bool:
        return hits(Evidence(file=file, page=page, box=box), PLAN, target)

    assert at((0.12, 0.12, 0.18, 0.18))  # inside
    assert at((0.0, 0.0, 0.2, 0.2))  # centre (0.1, 0.1): on the corner, edges count
    assert not at((0.0, 0.0, 0.19, 0.19))  # centre just outside
    assert at((0.0, 0.0, 0.3, 0.3))  # larger box, centre inside
    assert not at((0.12, 0.12, 0.18, 0.18), page=2)
    assert not at((0.12, 0.12, 0.18, 0.18), file="data/swiss_dwellings/other.pdf")


def item(id_: int, question: str, type_: QuestionType = "count", path: str = PLAN) -> GoldenItem:
    unit = "count" if type_ == "count" else None if type_ in ("text", "other") else "m2"
    answer = "x" if type_ in ("text", "other") else 1
    return GoldenItem(
        id=id_, path=path, question=question, answer=answer, unit=unit, type=type_,
        source=path.split("/")[1], language="en", template=question, group="g", split="dev",
    )  # fmt: skip


QUESTIONS = [
    item(1, "How many doors are drawn on this floor plan?"),
    item(2, "How many sinks are drawn on this floor plan?"),
    item(3, "What is the net floor area of apartment A in m²?", "area"),
]


def answer(id_: int, boxes: list[Evidence]) -> Answer:
    return Answer(id=id_, answer=1, unit="count", evidence=boxes, method="t", cost_usd=0.0,
                  latency_s=0.0)  # fmt: skip


def answers_from(shift: float = 0.0, only: int | None = None) -> dict[int, Answer]:
    """The oracle's evidence, every box (or the first `only` per answer) moved down by `shift`."""
    found: dict[int, Answer] = {}
    files = {PLAN: gold()}
    for question in QUESTIONS:
        boxes = oracle_evidence(question, files)
        moved = [
            Evidence(file=box.file, page=box.page,
                     box=(box.box[0], box.box[1] + shift, box.box[2], box.box[3] + shift))
            if only is None or n < only else box
            for n, box in enumerate(boxes)
        ]  # fmt: skip
        found[question.id] = answer(question.id, moved)
    return found


def test_oracle_evidence_scores_full_and_a_shifted_copy_drops() -> None:
    files = {PLAN: gold()}
    perfect = score_evidence(QUESTIONS, answers_from(), files)
    assert perfect.overall.precision.accuracy == 1.0 and perfect.overall.recall.accuracy == 1.0
    assert perfect.overall.recall.n == 6  # 2 doors, 2 sinks, 2 rooms of apartment A
    assert perfect.overall.questions == perfect.overall.with_evidence == 3
    nudged = score_evidence(QUESTIONS, answers_from(shift=0.005), files)  # centres stay inside
    assert nudged.overall.precision.accuracy == 1.0 and nudged.overall.recall.accuracy == 1.0
    away = score_evidence(QUESTIONS, answers_from(shift=0.3), files)  # off every item
    assert away.overall.precision.correct == 0 and away.overall.recall.correct == 0
    half = score_evidence(QUESTIONS, answers_from(shift=0.3, only=1), files)
    assert half.overall.precision.correct == half.overall.recall.correct == 3
    assert half.by_source_family["swiss_dwellings/door"].recall.correct == 1


def test_precision_and_recall_count_boxes_and_items() -> None:
    files = {PLAN: gold()}
    door = Evidence(file=PLAN, page=1, box=(0.10, 0.10, 0.12, 0.14))
    window = Evidence(file=PLAN, page=1, box=(0.30, 0.00, 0.40, 0.01))
    other_file = Evidence(file="data/swiss_dwellings/other.pdf", page=1, box=door.box)
    whole_plan = Evidence(file=PLAN, page=1, box=(0.0, 0.0, 1.0, 1.0))  # centre on no door
    result = score_evidence(
        QUESTIONS[:1], {1: answer(1, [door, door, window, other_file, whole_plan])}, files
    )
    [scored] = result.items
    assert (scored.boxes, scored.boxes_hit, scored.boxes_off_file) == (5, 2, 1)
    assert (scored.targets, scored.targets_hit) == (2, 1)  # the repeated box finds one door
    none = score_evidence(QUESTIONS[:1], {}, files)  # no answer line: recall 0, no boxes
    assert none.overall.precision.n == 0 and none.overall.recall.accuracy == 0.0
    assert none.overall.with_evidence == 0


def test_questions_without_item_boxes_are_counted_by_reason() -> None:
    counts = extraction(file="data/cubicasa5k/c.png", truth="counts", counts={"door": 1})
    files = {PLAN: gold(), counts.file: counts}
    questions = [
        item(1, "How many doors are drawn?"),
        item(2, "How many doors are drawn?", path=counts.file),
        item(3, "How many doors are there in the model 'Haus'?"),
        item(4, "How many apartments are shown?"),
        item(5, "Which room is largest?", "text"),
        item(6, "How many cats are drawn?"),
        item(7, "How many doors are drawn?", path="data/swiss_dwellings/no-gold.pdf"),
        item(8, "How many water closets are drawn in enlarged plan 9Z?"),
    ]
    result = score_evidence(questions, {}, files)
    assert [scored.id for scored in result.items] == [1]
    assert result.not_scored == {
        APARTMENT_COUNT: 1,
        UNKNOWN: 1,
        WHOLE_MODEL: 1,
        "enlarged plan not in the gold": 1,
        "free-text question": 1,
        "gold truth counts (no item boxes)": 1,
        "no Part 1 gold for the file": 1,
    }
    assert oracle_evidence(questions[1], files) == []

"""The proof an answer carries (app/core/review/proof.py), on synthetic drawings."""

from app.core.drawing.model import Drawing, ModelObject, Page, Scale, Table, TableRow
from app.core.pipeline.model import QuantityConflict
from app.core.review.model import MarkView, MethodValue, Row, RuleText, Scope
from app.core.review.proof import colour, schedule_proof, storey_table, takeoff_proof

PAGE = Page(page=1, width=100, height=100, unit="pt")
SHEET = Drawing(file="x.pdf", pages=(PAGE,), scale=Scale(status="no_scale"))


def mark(
    at: int, label: str, value: float | None, state: str = "counted", why: str = ""
) -> MarkView:
    box = (0.1 * at, 0.1, 0.1 * at + 0.05, 0.2)
    return MarkView.model_validate(
        {"id": f"{'x' if why else 'm'}{at}", "n": at if state == "counted" else None, "page": 1,
         "box": box, "polygon": None, "state": state, "value": value, "label": label,
         "ref": None, "reason": why or None}
    )  # fmt: skip


def a_row(key: str, measure: str, subject: str, value: float, unit: str, *marks: MarkView,
          rule: str = "each-once", scope: Scope | None = None) -> Row:  # fmt: skip
    return Row.model_validate(
        {"key": key, "label": key, "measure": measure, "subject": subject,
         "scope": scope or Scope(), "value": value, "unit": unit, "original_value": value,
         "status": "single", "needs_person": False, "rule": RuleText(id=rule, text=rule),
         "estimate": None, "first": None, "second": None, "conflict": None, "settled": None,
         "marks": marks, "signed": None}
    )  # fmt: skip


def test_a_count_has_one_fixed_colour_per_class_and_adds_up_its_classes() -> None:
    marks = (mark(1, "shower", 1), mark(2, "bathtub", 1), mark(3, "shower", 1))
    found = takeoff_proof(
        a_row("shower+bathtub", "count", "shower+bathtub", 3, "count", *marks), SHEET
    )
    assert found.kind == "count"
    assert [(key.label, key.colour, key.count) for key in found.legend] == [
        ("shower", colour("shower"), 2),
        ("bathtub", colour("bathtub"), 1),
    ]
    assert found.arithmetic == "2 shower + 1 bathtub = 3"
    assert colour("Door") == colour("door") == "#d62728"  # a door is red in every answer


def test_a_sum_writes_out_its_parts_and_names_what_the_rule_left_out() -> None:
    marks = (
        mark(1, "Küche", 12.5),
        mark(2, "Bad", 4.25),
        mark(3, "Balkon", 6.0, state="excluded", why="outdoor: not in an indoor total"),
    )
    found = takeoff_proof(a_row("area:room|indoor", "area", "room", 16.75, "m2", *marks), SHEET)
    assert found.kind == "sum"
    assert found.arithmetic == (
        "12.5 + 4.25 = 16.75 m²; left out: Balkon 6 (outdoor: not in an indoor total)"
    )


def test_every_unit_the_proof_writes_is_the_unit_people_read() -> None:
    for unit, shown in (("m2", "m²"), ("m3", "m³"), ("m", "m")):
        row = a_row("area:room|indoor", "area", "room", 2.0, unit, mark(1, "Küche", 2.0))
        assert takeoff_proof(row, SHEET).arithmetic == f"2 = 2 {shown}"


def test_a_model_fact_lists_the_objects_with_global_ids_and_the_storey_table() -> None:
    objects = tuple(
        ModelObject.model_validate(
            {
                "id": f"o{at}",
                "class": cls,
                "storey": storey,
                "global_id": f"G{at}",
                "name": f"n{at}",
            }
        )
        for at, (cls, storey) in enumerate(
            [
                ("window", "Erdgeschoss"),
                ("window", "Erdgeschoss"),
                ("window", "Dach"),
                ("door", "Dach"),
            ],
            start=1,
        )
    )
    model = Drawing(file="m.ifc", pages=(), scale=Scale(status="no_scale"), model_objects=objects)
    found = takeoff_proof(
        a_row("window|storey=erdgeschoss", "count", "window", 2, "count", rule="model-objects",
              scope=Scope(storey="erdgeschoss")),
        model,
    )  # fmt: skip
    assert found.kind == "model"
    assert [(item.global_id, item.storey) for item in found.objects or ()] == [
        ("G1", "Erdgeschoss"),
        ("G2", "Erdgeschoss"),
    ]
    assert found.arithmetic == "2 window objects in the model on Erdgeschoss"
    assert [(row.storey, row.counts) for row in found.storeys or ()] == [
        ("Erdgeschoss", {"window": 2}),
        ("Dach", {"door": 1, "window": 1}),
    ]
    assert storey_table(()) == ()


def test_a_model_count_that_is_not_what_the_objects_give_shows_no_list() -> None:
    model = Drawing(
        file="m.ifc",
        pages=(),
        scale=Scale(status="no_scale"),
        model_objects=(
            ModelObject.model_validate({"id": "o1", "class": "door", "global_id": "G"}),
        ),
    )
    found = takeoff_proof(
        a_row("door|model", "count", "door", 5, "count", rule="model-objects"), model
    )
    assert (found.objects, found.arithmetic) == (None, None)


def test_a_schedule_answer_shows_its_rows_cells_and_how_many_of_the_table() -> None:
    rows = tuple(
        TableRow(cells=(f"10{at}", kind), box=(0.1, 0.1 * at, 0.5, 0.1 * at + 0.05))
        for at, kind in enumerate(["A1", "B1", "A1"], start=1)
    )
    table = Table(id="t1", page=1, box=(0.1, 0.1, 0.5, 0.5), title="DOOR SCHEDULE",
                  columns=("NO.", "TYPE"), rows=rows)  # fmt: skip
    marks = tuple(
        MarkView.model_validate(
            {
                "id": f"e{n}",
                "n": n,
                "page": 1,
                "box": rows[at].box,
                "polygon": None,
                "state": "counted",
                "value": None,
                "label": None,
                "ref": None,
                "reason": None,
            }
        )
        for n, at in enumerate((0, 2), start=1)
    )
    found = schedule_proof(marks, (table,), 2)
    assert found.kind == "schedule" and found.schedule is not None
    assert [(row.n, row.cells) for row in found.schedule.rows] == [
        (1, ("101", "A1")),
        (2, ("103", "A1")),
    ]
    assert (found.schedule.title, found.schedule.of) == ("DOOR SCHEDULE", 3)
    assert found.arithmetic == "2 of the 3 rows of DOOR SCHEDULE = 2"


def test_a_count_names_what_a_second_reader_counted_without_a_mark_in_its_legend() -> None:
    marks = (mark(1, "shower", 1), mark(2, "bathtub", 1))
    found = a_row("shower+bathtub", "count", "shower+bathtub", 4, "count", *marks)
    found = found.model_copy(update={"unlocated": {"shower": 2}})
    proof = takeoff_proof(found, SHEET)
    assert [(key.label, key.count, key.unlocated, key.note) for key in proof.legend] == [
        ("shower", 3, 2, "2 counted without a mark (second reader)"),
        ("bathtub", 1, 0, None),
    ]
    assert proof.arithmetic == "3 shower + 1 bathtub = 4"
    only = a_row("toilet", "count", "toilet", 2, "count").model_copy(
        update={"unlocated": {"toilet": 2}}
    )  # every one unlocated: a key all the same, and no mark to draw
    assert [(key.label, key.count, key.note) for key in takeoff_proof(only, SHEET).legend] == [
        ("toilet", 2, "2 counted without a mark (second reader)")
    ]


def test_a_value_two_methods_measured_says_how_it_was_checked() -> None:
    walls = a_row("wall", "count", "wall", 72, "count", mark(1, "wall", 1))
    disputed = QuantityConflict.model_validate(
        {"values": [{"value": 72, "method": "plan_drawing"}, {"value": 86, "method": "ifc_model"}],
         "resolution": {"rule": "count what the sheet draws", "value": 72}}
    )  # fmt: skip
    measured = {
        "first": MethodValue(method="plan_drawing", value=72),
        "second": MethodValue(method="ifc_model", value=86),
    }
    found = walls.model_copy(update={**measured, "conflict": disputed})
    assert takeoff_proof(found, SHEET).check == (
        "Checked twice, they disagree: the sheet 72, the IFC model 86; kept 72: count what the "
        "sheet draws"
    )
    open_ = found.model_copy(update={"conflict": disputed.model_copy(update={"resolution": None})})
    assert takeoff_proof(open_, SHEET).check == (
        "Checked twice, they disagree: the sheet 72, the IFC model 86; no rule decides, a person "
        "must settle it"
    )
    agree = {"first": measured["first"], "second": MethodValue(method="ifc_model", value=72)}
    assert takeoff_proof(walls.model_copy(update=agree), SHEET).check == (
        "Checked twice, both agree: the sheet 72, the IFC model 72"
    )
    assert takeoff_proof(walls, SHEET).check is None  # measured once

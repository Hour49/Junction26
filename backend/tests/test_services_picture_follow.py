"""A plan edit followed on a services picture (core/services/picture_follow.py): what the picture
shows on or across a removed or added wall, by geometry on the page; what a picture cannot tell.
A synthetic 10 m x 10 m page; no IFC."""

from app.core.ifc_facts import Fact, FactSheet, Spot
from app.core.plan_edit.model import Item, Proposal
from app.core.services.model import DisciplineFollow, ServicesFollow
from app.core.services.picture_follow import CANNOT, Sheet, picture_follow

PLAN = Sheet(drawing_id="d1", page=1, storey="2. krs", size_m=(10.0, 10.0))
# a removed wall strip: x 5.0..5.1 m, y 2..6 m
WALL = Item(
    id="W1",
    polygon=((0.50, 0.20), (0.51, 0.20), (0.51, 0.60), (0.50, 0.60)),
    label="Wall W1, 4.00 m, 0.10 m thick",
)
RADS = (
    Spot(page=1, box=(0.49, 0.25, 0.4995, 0.30), reader="vlm"),  # against the left face
    Spot(page=1, box=(0.511, 0.40, 0.52, 0.45), reader="vlm"),  # against the right face
)
FAR_RAD = Spot(page=1, box=(0.20, 0.80, 0.25, 0.81), reader="vlm")
CROSSING = Spot(page=1, box=(0.40, 0.35, 0.60, 0.352), reader="mask")  # a pipe across the wall
FAR_PIPE = Spot(page=1, box=(0.10, 0.90, 0.30, 0.902), reader="mask")
ALONG = Spot(page=1, box=(0.503, 0.21, 0.507, 0.51), reader="mask")  # 3 m inside the wall


def fact(topic: str, subject: str, spots: tuple[Spot, ...], **more: object) -> Fact:
    return Fact.model_validate(
        {
            "topic": topic,
            "subject": subject,
            "value": len(spots),
            "unit": "count",
            "storey": "2. krs",
            "discipline": "heating",
            "source": "picture:vlm+template",
            "spots": spots,
            **more,
        }
    )


def heating(*pipe: Spot) -> FactSheet:
    return FactSheet(
        model="d1",
        disciplines=["heating"],
        facts=[
            fact("space_heater.count", "Radiator 22-600", (*RADS, FAR_RAD)),
            fact("space_heater.count", "all", (*RADS, FAR_RAD)),  # the same radiators again
            fact("pipe_segment.length", "Heating flow", pipe, unit="m", system="heating"),
            fact("pipe_segment.length", "all", pipe, unit="m", system="heating"),
            fact("pipe_segment.size_length", "DN20", pipe[:1], unit="m", system="heating"),
        ],
    )


def lane(found: ServicesFollow, name: str) -> DisciplineFollow:
    return next(d for d in found.disciplines if d.discipline == name)


def refs_of(found: DisciplineFollow, code: str) -> set[str]:
    return {r for a in found.actions if a.code == code for r in a.refs}


def labels_of(
    found: DisciplineFollow, refs: set[str]
) -> set[tuple[str, tuple[float, float] | None]]:
    return {(m.kind, m.at) for m in found.marks if m.ref in refs}


def test_two_radiators_on_the_removed_wall_a_pipe_crossing_it_and_the_rest_clear() -> None:
    found = picture_follow(
        Proposal(proposal_id="p1", drawing_id="d1", page=1, removed=(WALL,)),
        PLAN,
        [(PLAN, heating(CROSSING, FAR_PIPE))],
    )
    h = lane(found, "heating")
    assert h.status == "checked"
    on = next(a for a in h.actions if a.code == "reseat")
    assert on.status == "needs_decision" and len(on.refs) == 2
    assert "2 radiators" in on.label and "Radiator 22-600" in on.label
    through = next(a for a in h.actions if a.code == "through")
    assert through.status == "stays" and len(through.refs) == 1
    assert "Heating flow" in through.label and "DN20" in through.label
    assert CANNOT in through.label  # what it feeds and whether it can be rerouted
    named = refs_of(h, "reseat") | refs_of(h, "through")
    centres = {m.at for m in h.marks if m.ref in named and m.at}
    assert (0.225, 0.805) not in centres  # the far radiator is in no action
    assert len(h.actions) == 2 and h.summary.needs_decision == 1 and h.summary.stays == 1
    assert h.line.startswith("Heating: ")
    assert any("picture" in u for u in found.unknowns)
    assert found.storey == "2. krs"
    for other in ("plumbing", "ventilation", "electrical"):
        assert lane(found, other).status == "no_model"


def test_a_run_along_inside_the_removed_wall_goes_with_it() -> None:
    found = picture_follow(
        Proposal(proposal_id="p1", drawing_id="d1", page=1, removed=(WALL,)),
        PLAN,
        [(PLAN, heating(ALONG))],
    )
    along = next(a for a in lane(found, "heating").actions if a.code == "in_wall")
    assert along.status == "needs_decision" and "3.0 m" in along.label and CANNOT in along.label


def test_an_added_partition_needs_an_opening_where_a_pipe_crosses_it() -> None:
    added = Item(id="N1", polygon=WALL.polygon, label="New partition, 4.00 m")
    found = picture_follow(
        Proposal(proposal_id="p1", drawing_id="d1", page=1, added=(added,)),
        PLAN,
        [(PLAN, heating(CROSSING))],
    )
    codes = {(a.code, a.status) for a in lane(found, "heating").actions}
    assert codes == {("opening", "follows"), ("under", "needs_decision")}  # the pipe; the radiators


def test_nothing_on_the_walls_says_so() -> None:
    found = picture_follow(
        Proposal(proposal_id="p1", drawing_id="d1", page=1, removed=(WALL,)),
        PLAN,
        [
            (
                PLAN,
                FactSheet(
                    model="d1",
                    disciplines=["heating"],
                    facts=[fact("space_heater.count", "Radiator", (FAR_RAD,))],
                ),
            )
        ],
    )
    h = lane(found, "heating")
    assert h.status == "checked" and h.actions == ()
    assert h.line == "Heating: nothing drawn on this picture is on or crosses the changed walls."


# --- another sheet of the same floor -------------------------------------------------------------

ROOMS = (("Office 1", (0.3, 0.3)), ("Office 2", (0.7, 0.3)), ("Kitchen", (0.5, 0.8)))


def other(**change: object) -> Sheet:
    """The services sheet: the same floor drawn 1 m further right and down on a 12 m page."""
    moved = tuple((name, ((x * 10 + 1) / 12, (y * 10 + 1) / 12)) for name, (x, y) in ROOMS)
    return Sheet.model_validate(
        {"drawing_id": "d2", "page": 1, "storey": "2. KRS", "size_m": (12.0, 12.0), "rooms": moved}
        | change
    )


def shifted(spot: Spot) -> Spot:
    x0, y0, x1, y1 = spot.box
    return spot.model_copy(update={"box": tuple((v * 10 + 1) / 12 for v in (x0, y0, x1, y1))})


def test_another_sheet_of_the_floor_is_laid_over_by_three_room_names_and_the_scales() -> None:
    plan = PLAN.model_copy(update={"rooms": ROOMS})
    sheet = heating(*(shifted(s) for s in (CROSSING,)))
    sheet = sheet.model_copy(
        update={
            "facts": [
                f.model_copy(update={"spots": tuple(shifted(s) for s in f.spots)})
                if f.topic.startswith("space_heater")
                else f
                for f in sheet.facts
            ]
        }
    )
    found = picture_follow(
        Proposal(proposal_id="p1", drawing_id="d1", page=1, removed=(WALL,)),
        plan,
        [(other(), sheet)],
    )
    h = lane(found, "heating")
    assert h.status == "checked" and {a.code for a in h.actions} == {"reseat", "through"}
    rad = next(m for m in h.marks if m.ref in refs_of(h, "reseat"))
    assert rad.at is not None and abs(rad.at[0] - 0.49475) < 1e-3  # back on the plan's page


def test_another_sheet_is_not_laid_over_without_three_room_names_a_scale_or_the_same_floor() -> (
    None
):
    plan = PLAN.model_copy(update={"rooms": ROOMS})
    proposal = Proposal(proposal_id="p1", drawing_id="d1", page=1, removed=(WALL,))
    cases = {
        "only 2 room names appear on both sheets (3 are needed)": other(rooms=other().rooms[:2]),
        "the services picture has no scale": other(size_m=None),
        "the services picture is of another floor (1. krs)": other(storey="1. krs"),
    }
    for reason, sheet in cases.items():
        h = lane(picture_follow(proposal, plan, [(sheet, heating(CROSSING))]), "heating")
        assert (h.status, h.reason) == ("not_aligned", reason), reason
        assert h.line == f"Heating: not checked, {reason}."

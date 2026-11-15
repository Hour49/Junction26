"""A lane a services picture checked carries that picture with the edit in ITS page fractions
(services-follow.md, SFPW-1..4; pics-edit-follow W2). The scenes of test_services_picture_follow."""

import pytest
from test_services_picture_follow import (
    CROSSING,
    PLAN,
    RADS,
    ROOMS,
    WALL,
    heating,
    lane,
    other,
    refs_of,
    shifted,
)

from app.core.ifc_facts import FactSheet
from app.core.plan_edit.model import Item, Proposal
from app.core.services.model import Affine, Pairing
from app.core.services.picture_follow import picture_follow

REMOVE = Proposal(proposal_id="p1", drawing_id="d1", page=1, removed=(WALL,))


def moved(sheet: FactSheet) -> FactSheet:
    """The same marks drawn on the other sheet: 1 m right and down on a 12 m page."""
    return sheet.model_copy(
        update={
            "facts": [
                f.model_copy(update={"spots": tuple(shifted(s) for s in f.spots)})
                for f in sheet.facts
            ]
        }
    )


def test_the_plans_own_page_gives_its_picture_with_the_strip_and_marks_as_drawn() -> None:
    h = lane(picture_follow(REMOVE, PLAN, [(PLAN, heating(CROSSING))]), "heating")
    assert h.picture is not None
    assert (h.picture.drawing_id, h.picture.page) == ("d1", 1)
    assert h.picture.pairing.paired_by == "same_page" and h.picture.pairing.reason
    assert h.picture.removed == (WALL.polygon,) and h.picture.added == ()
    assert {m.ref for m in h.picture.marks} == {m.ref for m in h.marks}
    rad = next(m for m in h.picture.marks if m.ref in refs_of(h, "reseat") and m.at)
    assert rad.at is not None
    assert rad.at[0] == pytest.approx((RADS[0].box[0] + RADS[0].box[2]) / 2, abs=1e-4)


def test_another_sheet_gets_the_edit_in_its_own_fractions() -> None:
    plan = PLAN.model_copy(update={"rooms": ROOMS})
    h = lane(picture_follow(REMOVE, plan, [(other(), moved(heating(CROSSING)))]), "heating")
    assert h.picture is not None and h.picture.drawing_id == "d2"
    assert h.picture.pairing.paired_by == "geometry"
    (strip,) = h.picture.removed
    for (x, y), (px, py) in zip(strip, WALL.polygon, strict=True):  # 1 m on, on a 12 m page
        assert (x, y) == pytest.approx(((px * 10 + 1) / 12, (py * 10 + 1) / 12), abs=1e-4)
    on_plan = {m.ref: m for m in h.marks}
    for mark in h.picture.marks:
        plan_mark = on_plan[mark.ref]
        if mark.at is not None:
            assert plan_mark.at is not None
            x, y = plan_mark.at
            assert mark.at == pytest.approx(((x * 10 + 1) / 12, (y * 10 + 1) / 12), abs=1e-3)
        else:
            assert len(mark.line) == len(plan_mark.line) == 2


def test_an_added_partition_is_drawn_on_the_sheet() -> None:
    wall = Item(id="N1", polygon=((0.3, 0.3), (0.31, 0.3), (0.31, 0.5), (0.3, 0.5)), label="New")
    adding = Proposal(proposal_id="p2", drawing_id="d1", page=1, added=(wall,))
    h = lane(picture_follow(adding, PLAN, [(PLAN, heating(CROSSING))]), "heating")
    assert h.picture is not None
    assert h.picture.removed == () and h.picture.added == (wall.polygon,)


def test_a_lane_not_laid_over_has_no_picture() -> None:
    plan = PLAN.model_copy(update={"rooms": ROOMS})
    found = picture_follow(REMOVE, plan, [(other(size_m=None), heating(CROSSING))])
    assert lane(found, "heating").status == "not_aligned"
    assert all(d.picture is None for d in found.disciplines)


def test_a_pairing_given_by_the_caller_is_the_one_shown() -> None:
    """W1's pair() result goes in as `pairings`, in the sheets' order; a str refuses."""
    plan = PLAN.model_copy(update={"rooms": ROOMS})
    shift = Affine(a=12 / 10, c=-1 / 10, e=12 / 10, f=-1 / 10)  # the other sheet onto the plan
    given = Pairing(drawing_id="d2", page=1, paired_by="metadata", reason="EG on both title blocks",
                    score=0.9, to_plan=shift)  # fmt: skip
    sheets = [(other(), moved(heating(CROSSING)))]
    h = lane(picture_follow(REMOVE, plan, sheets, pairings=[given]), "heating")
    assert h.picture is not None and h.picture.pairing == given
    assert "to_plan" not in h.picture.model_dump()["pairing"]
    refused = lane(picture_follow(REMOVE, plan, sheets, pairings=["not this floor"]), "heating")
    assert (refused.status, refused.reason, refused.picture) == (
        "not_aligned",
        "not this floor",
        None,
    )

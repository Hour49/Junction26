"""A plan-edit proposal checked against the rule packs and the law knowledge base (spec
plan-edit-law-check LC-1..LC-5, LC-9, LC-9b). Synthetic rectangles on a 10 m x 10 m page; the real
packs from app/rules; the real law files for the search cases (a pack without files skips)."""

import json
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.law_index import SqliteLawIndex, load_laws
from app.adapters.plan_tools import PlanStore, run_plan_tool
from app.adapters.rule_packs import load_packs
from app.composition import build_ingest
from app.core.checks.model import RulePack
from app.core.drawing.model import Box, Drawing, Element, Page, Room, RoomType, Scale
from app.core.laws.model import ClauseView, Limit
from app.core.plan_edit.law_check import (
    LawCheck,
    LawNote,
    Verdict,
    _after,
    check_proposal,
    related_query,
    validate_law_note,
)
from app.core.plan_edit.model import Item, Proposal, Ring, RoomChange, Selection
from app.main import create_app
from app.settings import Settings

M = 0.1  # a page fraction is 10 m: the page is 1000 pt at 0.01 m/pt


@cache
def packs() -> dict[str, RulePack]:
    return {pack.id: pack for pack in load_packs(Settings().rule_packs_dir)}


def rect(x0: float, y0: float, x1: float, y1: float) -> Ring:
    """A rectangle in metres from the top left, as a page-fraction ring."""
    return ((x0 * M, y0 * M), (x1 * M, y0 * M), (x1 * M, y1 * M), (x0 * M, y1 * M))


def box(x0: float, y0: float, x1: float, y1: float) -> Box:
    return (x0 * M, y0 * M, x1 * M, y1 * M)


def room(rid: str, kind: RoomType, label: str, at: Box, area: float, **more: object) -> Room:
    x0, y0, x1, y1 = at
    return Room.model_validate(
        {"id": rid, "type": kind, "label": label, "page": 1, "box": at,
         "polygon": ((x0, y0), (x1, y0), (x1, y1), (x0, y1)), "area_m2": area, **more}
    )  # fmt: skip


def window(eid: str, at: Box) -> Element:
    return Element.model_validate({"id": eid, "class": "window", "page": 1, "box": at})


def door(eid: str, at: Box) -> Element:
    return Element.model_validate({"id": eid, "class": "door", "page": 1, "box": at})


def drawing(*rooms: Room, elements: tuple[Element, ...] = ()) -> Drawing:
    return Drawing(
        file="flat.pdf",
        pages=(Page(page=1, width=1000, height=1000, unit="pt"),),
        scale=Scale(status="scaled", m_per_unit=0.01),
        rooms=rooms,
        elements=elements,
    )


def proposal(*rooms: RoomChange, removed: tuple[Item, ...] = (), added: tuple[Item, ...] = ()):
    return Proposal(proposal_id="p1", drawing_id="0123456789abcdef", page=1, rooms=rooms,
                    removed=removed, added=added)  # fmt: skip


# A 12 m2 bedroom (4 x 3 m) with a window on its left wall
BEDROOM = room("r1", "bedroom", "Schlafzimmer", box(1, 1, 5, 4), 12.0)
LEFT_WINDOW = window("e1", box(0.95, 2, 1.05, 2.5))


def storage_in_bedroom(bedroom: Room = BEDROOM, width_m: float = 1.0) -> Proposal:
    """place_room's shape: a storage room at the bedroom's right end, the bedroom shrunk."""
    x0, y0, x1, y1 = (v / M for v in bedroom.box)
    depth = y1 - y0
    before = (x1 - x0) * depth
    return proposal(
        RoomChange(id="N1", label="Storage", polygon=rect(x1 - width_m, y0, x1, y1),
                   area_before_m2=0.0, area_after_m2=width_m * depth, was=(bedroom.id,)),
        RoomChange(id=bedroom.id, label="Schlafzimmer", polygon=rect(x0, y0, x1 - width_m, y1),
                   area_before_m2=before, area_after_m2=before - width_m * depth,
                   was=(bedroom.id,)),
    )  # fmt: skip


def test_lc1_a_storage_box_makes_a_12_m2_bedroom_fail_zurich_but_not_finland() -> None:
    plan = drawing(BEDROOM, elements=(LEFT_WINDOW,))
    zh = check_proposal(plan, storage_in_bedroom(), packs()["ch-zh"], "vector")
    (area,) = [f for f in zh.findings if f.rule_id == "ch-zh-room-area"]
    assert (area.change, area.subject, area.subject_ref) == ("newly_fails", "Schlafzimmer", "r1")
    assert (area.before.status, area.before.value) == ("pass", 12.0)
    assert (area.after.status, area.after.value, area.limit, area.unit) == ("fail", 9.0, 10, "m2")
    assert area.comparison_text == "at least" and "§ 303" in area.clause.ref
    fi = check_proposal(plan, storage_in_bedroom(), packs()["fi"], "vector")
    assert {(f.rule_id, f.change) for f in fi.findings} == {
        ("fi-habitable-room-area", "still_passes"), ("fi-habitable-room-window", "still_passes")
    }  # fmt: skip


def test_lc3_still_passes_on_touched_room() -> None:
    """The same box on a 20 m2 bedroom: its area (16 m2) and window still pass, shown as
    still_passes; an untouched living room's two passes stay in `unchanged`."""
    big = room("r1", "bedroom", "Schlafzimmer", box(1, 1, 6, 5), 20.0)
    living = room("r3", "living", "Wohnen", box(6.1, 1, 10, 5), 15.6)
    far_window = window("e2", box(9.95, 2, 10, 2.5))
    law = check_proposal(drawing(big, living, elements=(LEFT_WINDOW, far_window)),
                         storage_in_bedroom(big), packs()["ch-zh"], "vector")  # fmt: skip
    assert {(f.rule_id, f.change, f.subject_ref) for f in law.findings} == {
        ("ch-zh-room-area", "still_passes", "r1"), ("ch-zh-room-window", "still_passes", "r1")
    }  # fmt: skip
    assert law.unchanged == 2
    (area,) = [f for f in law.findings if f.rule_id == "ch-zh-room-area"]
    assert (area.before.value, area.after.value) == (20.0, 16.0)


def test_lc1_lc4_a_door_item_drops_its_element_and_wall_strips_change_no_element() -> None:
    hall = room("r2", "hall", "Korridor", box(5.1, 1, 8, 4), 8.7)
    plan = drawing(BEDROOM, hall, elements=(LEFT_WINDOW, door("e6", box(5, 2, 5.1, 2.9))))
    merge = proposal(
        RoomChange(id="r1+r2", label="Schlafzimmer + Korridor", polygon=rect(1, 1, 8, 4),
                   area_before_m2=20.7, area_after_m2=21.0, was=("r1", "r2")),
        removed=(Item(id="W1", polygon=rect(5, 1, 5.1, 2), label="Wall W1"),
                 Item(id="W1.2", polygon=rect(5, 2.9, 5.1, 4), label="Wall W1"),
                 Item(id="e6", polygon=rect(5, 2, 5.1, 2.9), label="door, no longer needed")),
    )  # fmt: skip
    after, _ = _after(plan, merge, "vector")
    assert [e.id for e in after.elements] == ["e1"]
    walls_only = merge.model_copy(update={"removed": merge.removed[:2]})
    assert _after(plan, walls_only, "vector")[0].elements == plan.elements


def test_lc2_a_merged_room_is_checked_as_each_type_it_came_from() -> None:
    small = room("r1", "bedroom", "Stanza", box(1, 1, 4, 4), 9.0)
    bath = room("r2", "bathroom", "Bagno", box(4.1, 1, 6.1, 4), 6.0)
    merge = proposal(
        RoomChange(id="r1+r2", label="Stanza + Bagno", polygon=rect(1, 1, 6.1, 4),
                   area_before_m2=15.0, area_after_m2=15.3, was=("r1", "r2")),
    )  # fmt: skip
    plan = drawing(small, bath, elements=(LEFT_WINDOW,))
    after, _ = _after(plan, merge, "vector")
    assert sorted((r.id, r.type) for r in after.rooms) == [
        ("r1+r2:bathroom", "bathroom"), ("r1+r2:bedroom", "bedroom")
    ]  # fmt: skip
    assert {r.area_m2 for r in after.rooms} == {15.3}  # (9 + 6) x 15.3 / 15
    law = check_proposal(plan, merge, packs()["ch-zh"], "vector")
    (area,) = [f for f in law.findings if f.rule_id == "ch-zh-room-area"]
    assert (area.change, area.subject, area.subject_ref) == (
        "now_passes",
        "Stanza + Bagno",
        "r1+r2",
    )
    assert (area.before.value, area.after.value) == (9.0, 15.3)


NEW_ROOM_HALL = room("r2", "hall", "Korridor", box(1, 5, 5, 8), 12.0)


@pytest.mark.parametrize(
    ("name", "kind"),
    [("Schlafzimmer", "bedroom"), ("storage", "storage"), ("Abstellraum", "storage"),
     ("Varasto", "storage"), ("Ripostiglio", "storage"), ("Hobbyraum", "other")],
)  # fmt: skip
def test_lc2_a_new_room_takes_its_type_from_its_name(name: str, kind: str) -> None:
    change = proposal(
        RoomChange(id="N1", label=name, polygon=rect(1, 5, 4, 8), area_before_m2=0.0,
                   area_after_m2=9.0, was=("r2",)),
        RoomChange(id="r2", label="Korridor", polygon=rect(4.1, 5, 5, 8), area_before_m2=12.0,
                   area_after_m2=2.7, was=("r2",)),
    )  # fmt: skip
    after, _ = _after(drawing(NEW_ROOM_HALL), change, "vector")
    (new,) = [r for r in after.rooms if r.id == "N1"]
    assert new.type == kind and new.area_m2 == 9.0 and new.area_status is None


def schlafzimmer_in_hall(name: str = "Schlafzimmer") -> Proposal:
    return proposal(
        RoomChange(id="N1", label=name, polygon=rect(1, 5, 4, 8), area_before_m2=0.0,
                   area_after_m2=9.0, was=("r2",)),
        RoomChange(id="r2", label="Korridor", polygon=rect(4.1, 5, 5, 8), area_before_m2=12.0,
                   area_after_m2=2.7, was=("r2",)),
    )  # fmt: skip


def test_lc2_a_new_schlafzimmer_with_no_window_newly_fails_its_window_and_area() -> None:
    plan = drawing(BEDROOM, NEW_ROOM_HALL, elements=(LEFT_WINDOW,))
    law = check_proposal(plan, schlafzimmer_in_hall(), packs()["ch-zh"], "vector")
    found = {(f.rule_id, f.change, f.subject_ref) for f in law.findings}
    assert found == {("ch-zh-room-window", "newly_fails", "N1"),
                     ("ch-zh-room-area", "newly_fails", "N1")}  # fmt: skip
    assert all(f.before.status == "not_applicable" for f in law.findings)


def test_lc2_lc4_on_a_picture_a_new_room_is_never_a_fail() -> None:
    plan = drawing(BEDROOM, NEW_ROOM_HALL, elements=(LEFT_WINDOW,))
    law = check_proposal(plan, schlafzimmer_in_hall(), packs()["ch-zh"], "raster")
    assert law.findings and all(f.change == "newly_cannot_tell" for f in law.findings)


def test_lc2_a_new_room_of_a_kind_we_cannot_tell_makes_the_room_rules_cannot_tell() -> None:
    kitchen = room("r3", "kitchen", "Küche", box(6, 1, 9, 4), 9.0)
    law = check_proposal(drawing(kitchen, NEW_ROOM_HALL), schlafzimmer_in_hall("Hobbyraum"),
                         packs()["ch-zh"], "vector")  # fmt: skip
    assert {(f.rule_id, f.change, f.subject) for f in law.findings} == {
        ("ch-zh-room-area", "newly_cannot_tell", "Hobbyraum"),
        ("ch-zh-room-window", "newly_cannot_tell", "Hobbyraum"),
    }
    assert all("could not tell" in (f.after.why or "") for f in law.findings)


# LC-4: Stanza 1.02 prints 16.48 m2; its outline measures 16.40 and 8.88 after the box
STANZA = room("r2", "bedroom", "Stanza", box(1, 1, 5.1, 5), 16.48, attrs={"number": "1.02"})


def shrunk_stanza(stanza: Room = STANZA) -> Proposal:
    return proposal(
        RoomChange(id="N1", label="Ripostiglio", polygon=rect(3.3, 1, 5.1, 5),
                   area_before_m2=0.0, area_after_m2=7.2, was=("r2",)),
        RoomChange(id="r2", label="Stanza 1.02", polygon=rect(1, 1, 3.22, 5),
                   area_before_m2=16.40, area_after_m2=8.88, was=("r2",)),
    )  # fmt: skip


def test_lc4_a_printed_area_shrinks_on_its_own_basis_and_fails_zurich() -> None:
    law = check_proposal(drawing(STANZA, elements=(LEFT_WINDOW,)), shrunk_stanza(),
                         packs()["ch-zh"], "vector")  # fmt: skip
    (area,) = [f for f in law.findings if f.rule_id == "ch-zh-room-area"]
    assert area.change == "newly_fails" and area.subject == "Stanza 1.02"
    assert area.before.value == 16.48 and area.after.value == pytest.approx(8.92, abs=0.01)


def test_lc4_an_estimated_area_is_cannot_tell_never_a_fail() -> None:
    guessed = STANZA.model_copy(update={"area_status": "estimated", "area_uncertainty": 0.05})
    law = check_proposal(drawing(guessed, elements=(LEFT_WINDOW,)), shrunk_stanza(guessed),
                         packs()["ch-zh"], "vector")  # fmt: skip
    (area,) = [f for f in law.findings if f.rule_id == "ch-zh-room-area"]
    assert (area.change, area.after.status) == ("newly_cannot_tell", "cannot_tell")
    assert not [f for f in law.findings if f.after.status == "fail"]


def test_lc3_lc5_findings_are_ordered_and_the_note_names_the_pack() -> None:
    plan = drawing(STANZA, NEW_ROOM_HALL, elements=(LEFT_WINDOW,))
    shrink_and_new = proposal(*shrunk_stanza().rooms[1:], *schlafzimmer_in_hall().rooms)
    law = check_proposal(plan, shrink_and_new, packs()["ch-zh"], "vector")
    order = ["newly_fails", "still_fails", "newly_cannot_tell", "now_passes", "still_passes"]
    assert [order.index(f.change) for f in law.findings] == sorted(
        order.index(f.change) for f in law.findings
    )
    assert (law.pack, law.pack_name) == ("ch-zh", "Canton of Zürich building act")
    assert law.fail_means == packs()["ch-zh"].fail_means
    assert law.note == (
        "A pre-check of 2 rules from Canton of Zürich building act, not a permit check. "
        "Structure, fire safety, escape routes and services are not checked."
    )


def clause(cid: str = "ch-zh-ls-700-1-303", ref: str = "§ 303", **more: object) -> ClauseView:
    fields: dict[str, object] = {
        "id": cid, "ref": ref, "text": "Wohn- und Schlafräume ... mindestens 10 m2",
        "text_en": "Living and sleeping rooms ... at least 10 m2",
        "summary_en": "Rooms are at least 10 m2.", "keywords": ("room", "area", "Fläche"),
        "topics": ("rooms",), "drawing_checkable": True,
        "limits": (Limit(what="room floor area", comparison=">=", value=10, unit="m2"),),
        "law_id": "ch-zh-ls-700-1", "law_number": "LS 700.1", "law_title": "PBG",
        "law_title_en": "Planning and Building Act of the Canton of Zürich",
        "url": "https://www.zh.ch/pbg", "language": "de", "checked": "2026-11-14",
        "status_note": None,
    }  # fmt: skip
    return ClauseView.model_validate({**fields, **more})


def test_lc9_related_keeps_the_clauses_checkable_with_limits_first() -> None:
    loose = clause("ch-zh-ls-700-1-299", "§ 299", limits=(), drawing_checkable=False)
    law = check_proposal(drawing(BEDROOM, elements=(LEFT_WINDOW,)), storage_in_bedroom(),
                         packs()["ch-zh"], "vector", related=(loose, clause()))  # fmt: skip
    assert [c.id for c in law.related] == ["ch-zh-ls-700-1-303", "ch-zh-ls-700-1-299"]


def test_lc7_for_model_has_no_quotes() -> None:
    law = check_proposal(drawing(BEDROOM, elements=(LEFT_WINDOW,)), storage_in_bedroom(),
                         packs()["ch-zh"], "vector", related=(clause(),))  # fmt: skip
    shown = json.dumps(law.for_model(), ensure_ascii=False)
    assert law.findings[0].clause.quote not in shown and "mindestens" not in shown
    assert "§ 303" in shown and '"limits"' in shown and '"subjects"' in shown


def test_lc9_related_query_says_the_change_in_words() -> None:
    query = related_query(drawing(BEDROOM), storage_in_bedroom())
    assert {"bedroom", "Schlafzimmer", "makuuhuone", "storage", "Abstellraum"} <= set(query.split())
    bath = room("r2", "bathroom", "Bagno", box(5.1, 1, 7, 4), 5.7)
    merge = proposal(
        RoomChange(id="r1+r2", label="Schlafzimmer + Bagno", polygon=rect(1, 1, 7, 4),
                   area_before_m2=17.7, area_after_m2=18.0, was=("r1", "r2")),
        removed=(Item(id="W1", polygon=rect(5, 1, 5.1, 4), label="Wall W1"),),
    )  # fmt: skip
    words = set(related_query(drawing(BEDROOM, bath), merge).split())
    assert {"wall", "wet", "waterproofing", "Nasszelle", "märkätila"} <= words


@cache
def index() -> SqliteLawIndex:
    return SqliteLawIndex(load_laws(Settings().laws_dir))


NEW_DOOR = proposal(added=(Item(id="D1", polygon=rect(5, 2, 5.1, 2.8), label="New door"),))
WALL_BY_BATH = proposal(
    RoomChange(id="r1+r2", label="Schlafzimmer + Bad", polygon=rect(1, 1, 7, 4),
               area_before_m2=17.7, area_after_m2=18.0, was=("r1", "r2")),
    removed=(Item(id="W1", polygon=rect(5, 1, 5.1, 4), label="Wall W1"),),
)  # fmt: skip
BATH = room("r2", "bathroom", "Bad", box(5.1, 1, 7, 4), 5.7)
SEARCHES = [
    ("fi", drawing(BEDROOM), storage_in_bedroom(), "fi-631-2024-4-2"),
    ("ch-zh", drawing(BEDROOM), storage_in_bedroom(), "ch-zh-ls-700-1-303"),
    ("fi", drawing(BEDROOM), NEW_DOOR, "fi-241-2017-4-2"),
    ("fi", drawing(BEDROOM, BATH), WALL_BY_BATH, "fi-782-2017-28-1"),
]


@pytest.mark.parametrize(("pack", "plan", "change", "expected"), SEARCHES)
def test_lc9_related_query_finds_the_clause_in_the_real_law_files(
    pack: str, plan: Drawing, change: Proposal, expected: str
) -> None:
    if not index().toc(pack):
        pytest.skip(f"no {pack} law files in app/laws")
    index().clause(expected)
    found = [hit.id for hit in index().search(pack, related_query(plan, change), limit=8)]
    assert expected in found, found


# LC-9b: the shrunk 12 m2 bedroom checked on the fi pack (so no rule-pack finding cites § 303),
# and the model's reading of PBG § 303
def checked() -> LawCheck:
    return check_proposal(drawing(BEDROOM, elements=(LEFT_WINDOW,)), storage_in_bedroom(),
                          packs()["fi"], "vector")  # fmt: skip


GOOD = LawNote(clause_id="ch-zh-ls-700-1-303", subject="Schlafzimmer", value=9.0, comparison=">=",
               limit=10, unit="m2", verdict="would_not_meet")  # fmt: skip


def test_lc9b_a_correct_note_is_kept_with_the_server_filled_clause() -> None:
    kept = validate_law_note(GOOD, checked(), {"ch-zh-ls-700-1-303": clause()}, [9.0, 3.0])
    assert kept is not None and kept.verdict == "would_not_meet" and kept.basis == "ai_reading"
    assert (kept.ref, kept.url) == ("§ 303", "https://www.zh.ch/pbg")
    assert kept.quote.startswith("Wohn-") and kept.quote_en and kept.law.startswith("Planning")


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ({"limit": 8}, "a limit the clause does not have"),
        ({"unit": "m"}, "a unit the clause does not have"),
        ({"clause_id": "ch-zh-ls-700-1-302-2"}, "a clause not from this turn"),
        ({"value": 8.5}, "a value no tool returned"),
        ({"verdict": "meets"}, "a verdict that contradicts its numbers"),
        ({"subject": "Wohnzimmer"}, "a room the proposal does not change"),
        ({"value": None}, "no value but a verdict"),
    ],
)
def test_lc9b_a_note_that_does_not_stand_is_dropped(change: dict[str, object], why: str) -> None:
    note = GOOD.model_copy(update=change)
    assert validate_law_note(note, checked(), {GOOD.clause_id: clause()}, [9.0]) is None, why


def test_lc9b_a_note_without_a_value_is_a_check() -> None:
    note = GOOD.model_copy(update={"value": None, "verdict": "check"})
    kept = validate_law_note(note, checked(), {GOOD.clause_id: clause()}, [])
    assert kept is not None and kept.verdict == "check"


def test_lc9b_a_door_width_in_mm_is_compared_with_the_tools_metres() -> None:
    door_clause = clause("fi-241-2017-4-2", "4 § 2 mom.", law_number="241/2017",
                         limits=(Limit(what="clear door width", comparison=">=", value=800,
                                       unit="mm"),))  # fmt: skip
    new_door = proposal(added=(Item(id="D1", polygon=rect(5, 2, 5.7, 2.1), label="New door"),))
    law = check_proposal(drawing(BEDROOM), new_door, packs()["fi"], "vector")
    assert law.subject_values == {"D1": [0.7]}  # its long side, 0.7 m at the drawing's scale
    note = LawNote(clause_id=door_clause.id, subject="new door D1", value=700, comparison=">=",
                   limit=800, unit="mm", verdict="would_not_meet")  # fmt: skip
    kept = validate_law_note(note, law, {door_clause.id: door_clause}, [])
    assert kept is not None and kept.verdict == "would_not_meet"


def test_lc9b_another_rooms_area_for_this_room_is_dropped() -> None:
    """The storage room is 3 m2 and the bedroom 9 m2: 3 m2 said of the bedroom is no value of
    its own, though a tool gave it this turn."""
    law = checked()
    assert law.subject_values["r1"] == law.subject_values["Schlafzimmer"] == [9.0]
    assert law.subject_values["Storage"] == [3.0]
    note = GOOD.model_copy(update={"value": 3.0})
    assert validate_law_note(note, law, {GOOD.clause_id: clause()}, [9.0, 3.0]) is None


def test_lc9b_a_note_that_repeats_a_rule_pack_finding_is_dropped() -> None:
    law = check_proposal(drawing(BEDROOM, elements=(LEFT_WINDOW,)), storage_in_bedroom(),
                         packs()["ch-zh"], "vector")  # fmt: skip
    pbg = clause(ref="§ 303 Abs. 1")  # the pack cites "... (PBG, LS 700.1), § 303 Abs. 1"
    assert validate_law_note(GOOD, law, {GOOD.clause_id: pbg}, [9.0]) is None


# lawai-2: a limit per dwelling (building, storey, in total) is not one room's: the storage
# room's 3 m2 against Zurich's "8 m2 of storage per dwelling" is a check, the rest unknown
def storage_note(what: str, verdict: Verdict = "would_not_meet") -> tuple[LawNote, ClauseView]:
    limits = (Limit(what=what, comparison=">=", value=8, unit="m2"),)
    bbv = clause("ch-zh-ls-700-21-39", "§ 39", limits=limits)
    note = LawNote(clause_id=bbv.id, subject="Storage", value=3.0, comparison=">=", limit=8,
                   unit="m2", verdict=verdict)  # fmt: skip
    return note, bbv


def test_lawai2_per_dwelling_limit_on_one_room_is_check() -> None:
    note, bbv = storage_note("storage floor area per dwelling")
    kept = validate_law_note(note, checked(), {bbv.id: bbv}, [])
    assert kept is not None and kept.verdict == "check" and kept.value == 3.0


@pytest.mark.parametrize(
    "what",
    [
        "storage floor area per dwelling with at most two rooms",  # ch-zh, as in the law files
        "total sales area of a shopping centre",
        "Abstellfläche pro Wohnung",
        "varastotilaa asuntoa kohden",
        "surface de rangement par logement",
        "dwelling unit floor area",  # fi, as in the law files from here on
        "student flat floor area with suitable shared spaces",
        "floor area, two-storey building",
        "floor area of a small building",  # ch-zh
    ],
)
def test_lawai2_aggregate_limits_are_check_whatever_the_model_said(what: str) -> None:
    said: Verdict
    for said in ("would_not_meet", "meets", "check"):
        note, bbv = storage_note(what, said)
        kept = validate_law_note(note, checked(), {bbv.id: bbv}, [])
        assert kept is not None and kept.verdict == "check", (what, said)


@pytest.mark.parametrize(
    "what",
    [
        "storage room floor area",
        "habitable room area",
        "door clear width",
        "room floor area (not single-family houses)",  # ch-zh, as in the law files from here on
        "kitchen floor area in one-room dwellings",
        "clear width of doors and openings on internal routes, stairwell-to-dwelling doors",  # fi
        "reduced dwelling exit width with lift in existing building",
        "reduced exit width (exit area up to 60 persons, or small residential building)",
        "turning space diameter in dwelling hall and kitchen",
    ],
)
def test_lawai2_a_per_room_limit_still_would_not_meet(what: str) -> None:
    note, bbv = storage_note(what)
    kept = validate_law_note(note, checked(), {bbv.id: bbv}, [])
    assert kept is not None and kept.verdict == "would_not_meet"
    assert validate_law_note(note.model_copy(update={"verdict": "check"}), checked(),
                             {bbv.id: bbv}, []) is None  # fmt: skip


# The golden path (spec §1 steps 1-4) on the real sheet, when the dataset is on this machine
FLOOR = (
    Path(__file__).parents[2]
    / "data/stoa/full/junction-dataset/data/swiss_dwellings/site980_bldg2055_floor9178.pdf"
)


def call(store: PlanStore, tool: str, **arguments: object) -> Any:
    return json.loads(run_plan_tool(store, tool, json.dumps(arguments)))


def test_golden_path_floor9178_a_storage_room_in_stanza_1_02(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not FLOOR.exists():
        pytest.skip("the dataset is not on this machine")
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        projects_dir=tmp_path / "projects",
        sample_archive=tmp_path / "s.zip",
        credit_dataset=tmp_path / "dataset",
        credit_photos=tmp_path / "photos",
    )
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )  # fmt: skip
    pid = client.post("/api/projects", params={"name": FLOOR.name}, content=FLOOR.read_bytes())
    project = pid.json()["id"]
    drawing_id = client.get(f"/api/projects/{project}").json()["drawings"][0]["drawing_id"]
    store = PlanStore.of_app(client.app, project)
    walls = call(store, "list_walls", drawing_id=drawing_id, page=1)
    (stanza,) = [r for r in walls["rooms"] if r["label"] == "Stanza 1.02"]
    x0, y0, x1, y1 = stanza["box"]
    region = (x0 + (x1 - x0) * 0.7, y0 + 0.002, x1 - 0.002, y1 - 0.002)  # its right 30%
    store.selections["sel_1"] = Selection(
        id="sel_1", kind="region", drawing_id=drawing_id, page=1, box=region
    )
    change = Proposal.model_validate(
        call(store, "propose_room", selection_id="sel_1", name="Ripostiglio")["proposal"]
    )
    plan = store.pipeline.ingest.drawing(drawing_id)
    zh = check_proposal(plan, change, packs()["ch-zh"], "vector")
    (area,) = [f for f in zh.findings if f.rule_id == "ch-zh-room-area"]
    assert (area.change, area.subject, area.before.value) == ("newly_fails", "Stanza 1.02", 16.48)
    assert 7 < (area.after.value or 0) < 10
    fi = check_proposal(plan, change, packs()["fi"], "vector")
    (meets,) = [f for f in fi.findings if f.rule_id == "fi-habitable-room-area"]
    assert (meets.change, meets.subject) == ("still_passes", "Stanza 1.02")  # step 4: ✓ Meets


def run_fresh(code: str) -> None:
    """`code` in a new interpreter, from backend/, so no module is imported yet."""
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=Path(__file__).parents[1], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr


def test_law_check_imports_after_the_plan_edit_model_in_a_fresh_interpreter() -> None:
    run_fresh("import app.core.plan_edit.model\nimport app.core.plan_edit.law_check")


def test_the_plan_edit_model_can_import_law_check_at_its_top() -> None:
    """law_check never imports plan_edit.model at runtime, so model.py's `law: LawCheck | None`
    field (agent-chat side) is no cycle; a model with that field builds and round-trips."""
    run_fresh(
        "import sys\n"
        "from app.core.plan_edit.law_check import LawCheck\n"
        "assert 'app.core.plan_edit.model' not in sys.modules, 'law_check imports the model'\n"
        "from app.core.model import Frozen\n"
        "class Proposal(Frozen):\n"
        "    law: LawCheck | None = None\n"
        "law = LawCheck(pack='fi', pack_name='Finland', fail_means=None, findings=(), unchanged=0,"
        " note='n')\n"
        "assert Proposal.model_validate_json(Proposal(law=law).model_dump_json()).law == law\n"
    )

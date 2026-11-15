"""Which services picture is the plan's floor (docs/specs/backend/services-follow.md, SFP-9..15):
`pair` reads the sheets' floor words, sheet numbers and file names first, then lays the sheet over
the plan by its register (the room-name shift by default)."""

from app.core.plan_edit.walls import PlanPage
from app.core.services.model import Affine, Pairing
from app.core.services.pairing import (
    Register,
    by_room_names,
    by_walls,
    either,
    pair,
    plan_wall_lines,
)
from app.core.services.picture_follow import Sheet
from app.core.services.register import Segment

ROOMS = (("Office 1", (0.3, 0.3)), ("Office 2", (0.7, 0.3)), ("Kitchen", (0.5, 0.8)))
MOVED = tuple((name, ((x * 10 + 1) / 12, (y * 10 + 1) / 12)) for name, (x, y) in ROOMS)

PLAN = Sheet(
    drawing_id="d1",
    page=1,
    size_m=(10.0, 10.0),
    rooms=ROOMS,
    name="A-101 Floor 1 plan.pdf",
)


def sheet(drawing_id: str = "d2", **change: object) -> Sheet:
    """A heating picture of floor 1, 1 m off on a 12 m page, its room names printed."""
    base: dict[str, object] = {
        "drawing_id": drawing_id,
        "page": 1,
        "size_m": (12.0, 12.0),
        "rooms": MOVED,
        "name": "set/H-101 Floor 1 heating.png",
        "disciplines": ("heating",),
    }
    return Sheet.model_validate(base | change)


def one(plan: Sheet, candidate: Sheet) -> Pairing | str:
    [found] = pair(plan, [candidate])
    return found


def test_the_plans_own_page_pairs_same_page() -> None:
    found = one(PLAN, PLAN.model_copy(update={"disciplines": ("heating",)}))
    assert isinstance(found, Pairing)
    assert (found.paired_by, found.score, found.to_plan) == ("same_page", None, Affine())
    assert found.reason == "the plan's own page"


def test_same_floor_and_sheet_number_and_rooms() -> None:
    found = one(PLAN, sheet())
    assert isinstance(found, Pairing)
    assert (found.drawing_id, found.page, found.paired_by, found.score) == (
        "d2",
        1,
        "metadata",
        0.9,
    )
    assert "floor 1" in found.reason.casefold()
    assert "A-101 / H-101" in found.reason
    assert "3 room names" in found.reason
    assert found.to_plan is not None
    x, y = found.to_plan.apply(MOVED[0][1])
    assert abs(x - 0.3) < 1e-6 and abs(y - 0.3) < 1e-6


def test_another_floor_is_refused_whatever_the_rooms() -> None:
    found = one(PLAN, sheet(name="H-102 Floor 2 heating.png"))
    assert isinstance(found, str) and found.startswith("another floor")
    assert "Floor 2" in found
    eg = PLAN.model_copy(update={"name": "plan.pdf", "storey": "EG"})
    found = one(eg, sheet(name="heating.png", storey="OG 1"))
    assert found == "another floor: 'OG 1' against 'EG'"
    # the same floor in two languages' words pairs
    found = one(eg, sheet(name="heating.png", storey="Erdgeschoss"))
    assert isinstance(found, Pairing) and found.paired_by == "metadata"


def test_same_floor_without_rooms_is_laid_page_to_page_only_on_the_same_sheet_size() -> None:
    found = one(PLAN, sheet(rooms=(), size_m=(10.1, 9.95)))
    assert isinstance(found, Pairing)
    assert (found.paired_by, found.score, found.to_plan) == ("metadata", 0.7, Affine())
    assert "page to page" in found.reason
    found = one(PLAN, sheet(rooms=()))
    assert isinstance(found, str)
    assert found.startswith("same floor (")
    assert found.endswith(
        "but it cannot be laid over the plan: only 0 room names appear on both sheets "
        "(3 are needed)"
    )


def test_no_hint_falls_back_to_geometry() -> None:
    plain = PLAN.model_copy(update={"name": "plan.pdf"})
    found = one(plain, sheet(name="scan_0042.png"))
    assert isinstance(found, Pairing)
    assert (found.paired_by, found.score) == ("geometry", 0.6)
    assert "3 room names" in found.reason
    found = one(plain, sheet(name="scan_0042.png", rooms=MOVED[:2]))
    assert found == "only 2 room names appear on both sheets (3 are needed)"


def test_the_best_of_two_heating_sheets_wins_and_names_the_other() -> None:
    weak = sheet("d3", name="scan_0042.png")  # geometry only, 0.6
    strong = sheet("d2")  # metadata and rooms, 0.9
    first, second = pair(PLAN, [weak, strong])
    assert isinstance(second, Pairing) and second.drawing_id == "d2"
    assert "scan_0042.png" in second.reason
    assert first == "another heating picture was taken: H-101 Floor 1 heating.png"


def test_the_register_plugs_in() -> None:
    turned = Affine(a=0.0, b=-1.0, c=1.0, d=1.0, e=0.0, f=0.0)

    def walls(plan: Sheet, candidate: Sheet) -> tuple[Affine, str] | str:
        return turned, "walls match: 41 of 47 wall lines within 0.2 m after rotation 90 deg"

    plain = PLAN.model_copy(update={"name": "plan.pdf", "rooms": ()})
    [found] = pair(plain, [sheet(name="scan.png", rooms=())], register=walls)
    assert isinstance(found, Pairing)
    assert (found.paired_by, found.to_plan) == ("geometry", turned)
    assert found.reason == "walls match: 41 of 47 wall lines within 0.2 m after rotation 90 deg"


def test_floor_words_of_several_languages() -> None:
    from app.core.services.pairing import _floors  # pyright: ignore[reportPrivateUsage]

    cases = {
        "EG": "0", "Erdgeschoss": "0", "Ground floor": "0", "1. OG": "1", "OG1": "1",
        "Level 02": "2", "2nd floor": "2", "3F": "3", "2. krs": "2", "KRS1": "1", "Kellari": "-1",
        "B1": "-1", "ullakko": "roof",
        "plan-02-e00-okrd": "0", "E01_OKRD": "1", "B01": "-1", "A-101 plan.pdf": None,
    }  # fmt: skip
    for words, key in cases.items():
        found = _floors(Sheet(drawing_id="d", page=1, storey=words))
        assert (next(iter(found)) if found else None) == key, words


def test_sheets_of_two_folders_are_two_sets() -> None:
    plan = PLAN.model_copy(update={"name": "A/plan.pdf"})
    assert one(plan, sheet(name="B/heating.png")) == "another set: folder 'B' against 'A'"
    plain = PLAN.model_copy(update={"name": "plan.pdf"})
    found = one(plain, sheet(name="B/heating.png"))
    assert isinstance(found, Pairing) and found.paired_by == "geometry"


# --- laid over by walls (SFP-18, SFP-19) -------------------------------------------------------

# A floor 10 m x 8 m on a 12 m x 10 m page, walls as centre lines in metres; no symmetry.
WALLS_M = (
    ((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0)),
    ((4, 0), (4, 8)), ((4, 5), (10, 5)), ((7, 5), (7, 8)), ((0, 3), (2, 3)),
)  # fmt: skip
PAGE_PX = (500.0, 600.0)


def on_sheet(p: tuple[float, float]) -> tuple[float, float]:
    """The services sheet draws the floor turned a quarter, 50 px a metre."""
    return (450 - 50 * p[1], 50 + 50 * p[0])


def segments(lines: object) -> list[Segment]:
    return [Segment(a=a, b=b) for a, b in lines]  # type: ignore[union-attr]


def laid_with(register: Register, plan: Sheet, picture: Sheet) -> tuple[Affine, str]:
    found = register(plan, picture)
    assert not isinstance(found, str), found
    return found


def test_walls_lay_a_turned_half_size_sheet_over_the_plan() -> None:
    plan = PLAN.model_copy(update={"name": "plan.pdf", "rooms": (), "size_m": (12.0, 10.0)})
    picture = sheet(name="scan.png", rooms=(), size_m=None)
    drawn = segments((on_sheet(a), on_sheet(b)) for a, b in WALLS_M)
    walls = by_walls(segments(WALLS_M), lambda _: (drawn, PAGE_PX))
    laid = walls(plan, picture)
    assert not isinstance(laid, str), laid
    to_plan, how = laid
    assert how.startswith("walls match: 8 of 8 within 0.2 m after rotation")
    for corner in ((0, 0), (10, 0), (10, 8), (4, 5)):
        x, y = on_sheet(corner)
        fx, fy = to_plan.apply((x / PAGE_PX[0], y / PAGE_PX[1]))
        assert abs(fx - corner[0] / 12) < 0.005 and abs(fy - corner[1] / 10) < 0.005, corner
    # a scale bar that agrees says nothing; one 20 % off is named, not picked silently
    _, agreed = laid_with(walls, plan, picture.model_copy(update={"size_m": (10.0, 12.0)}))
    assert agreed == how
    _, named = laid_with(walls, plan, picture.model_copy(update={"size_m": (12.0, 14.4)}))
    assert named.endswith("; its scale says 24.0 mm a pixel, the walls 20.0 mm: laid by the walls")
    # the follower's register: room names first, then walls
    [found] = pair(plan, [picture], register=either(by_room_names, walls))
    assert isinstance(found, Pairing) and found.paired_by == "geometry"
    assert found.reason == how
    blind = by_walls(segments(WALLS_M), lambda _: "no wall lines were read on the sheet")
    [found] = pair(plan, [picture], register=either(by_room_names, blind))
    assert found == ("the services picture has no scale; no wall lines were read on the sheet")


def test_the_plans_wall_lines_are_centre_lines() -> None:
    w, h = 12.0, 10.0

    def ring(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[float, float], ...]:
        return ((x0 / w, y0 / h), (x1 / w, y0 / h), (x1 / w, y1 / h), (x0 / w, y1 / h))

    page = PlanPage(
        drawing_id="d1", page=1, width_m=w, height_m=h, rooms=(),
        mass=((ring(0, 0, 10, 8), (ring(0.2, 0.2, 9.8, 7.8),)),),
    )  # fmt: skip
    found = {
        frozenset((tuple(round(v, 2) for v in s.a), tuple(round(v, 2) for v in s.b)))
        for s in plan_wall_lines(page)
    }
    assert found == {
        frozenset(((0.2, 0.1), (9.8, 0.1))), frozenset(((9.9, 0.2), (9.9, 7.8))),
        frozenset(((0.2, 7.9), (9.8, 7.9))), frozenset(((0.1, 0.2), (0.1, 7.8))),
    }  # fmt: skip


# --- review-495: a wrong floor is refused, not paired with a confident reason (SFP-21..25) -----


def test_floor_words_that_differ_refuse_even_when_one_is_shared() -> None:
    # the set's building folder "B1" is on both; the floors are 1 and 2 (review-495 M1)
    plan = PLAN.model_copy(update={"name": "B1/A-101 Floor 1 plan.pdf"})
    found = one(plan, sheet(name="B1/H-102 Floor 2 heating.png"))
    assert found == "another floor: 'Floor 2' against 'Floor 1'"
    no_rooms = sheet(name="B1/H-102 Floor 2 heating.png", rooms=(), size_m=(10.0, 10.0))
    found = one(plan.model_copy(update={"rooms": ()}), no_rooms)
    assert found == "another floor: 'Floor 2' against 'Floor 1'"
    # a floor word one sheet names and the other doesn't is no disagreement
    found = one(plan, sheet(name="B1/H-101 heating.png", storey="Floor 1"))
    assert isinstance(found, Pairing) and found.paired_by == "metadata"


def test_an_electrical_sheet_number_is_not_a_level_code() -> None:
    # E01 is the first electrical sheet, not level 1 (review-495 M2); E00/E01 levels still read
    found = one(PLAN, sheet(name="E01 Elektro.png", disciplines=("electrical",)))
    assert isinstance(found, Pairing) and found.paired_by == "geometry"
    found = one(PLAN, sheet(name="set/E01 heating.png", sheet_number="E01"))
    assert isinstance(found, Pairing) and found.paired_by == "geometry"
    found = one(PLAN, sheet(name="digitalhub_plan-02-e00-okrd heating.png"))
    assert found == "another floor: 'e00' against 'Floor 1'"
    found = one(PLAN, sheet(name="heating.png", storey="E01_OKRD"))
    assert isinstance(found, Pairing) and found.paired_by == "metadata"


def test_two_floors_that_fit_alike_and_name_no_floor_are_both_refused() -> None:
    # a plan with no floor hint; two heating sheets print the same room names (review-495 M3)
    plain = PLAN.model_copy(update={"name": "plan.pdf"})
    found = pair(plain, [sheet("d2", name="heating-a.png"), sheet("d3", name="heating-b.png")])
    said = (
        "2 heating pictures fit this plan alike and none names its floor "
        "(heating-a.png, heating-b.png): which one is this floor is not known"
    )
    assert found == [said, said]
    # one that names the plan's floor still wins over one laid by geometry alone
    named = pair(PLAN, [sheet("d3", name="heating-b.png"), sheet("d2")])
    assert isinstance(named[1], Pairing) and named[1].paired_by == "metadata"


def test_discipline_folders_are_one_set() -> None:
    # review-495 S1: folders by discipline are one delivery, not two sets
    plan = PLAN.model_copy(update={"name": "Architektur/A-101 Floor 1 plan.pdf"})
    found = one(plan, sheet(name="Heizung/H-101 Floor 1 heating.png"))
    assert isinstance(found, Pairing) and found.paired_by == "metadata"
    found = one(PLAN.model_copy(update={"name": "ARK/plan.pdf"}), sheet(name="LVI/heating.png"))
    assert isinstance(found, Pairing)


def test_sheets_drawn_years_apart_still_pair() -> None:
    # a real set's services sheets are often redrawn years after the plan (USCG building 110: as
    # built 1965, heating 1958, electrical 1981, one basement), so years refuse nothing
    plan = PLAN.model_copy(update={"name": "Building 110 Basement Plan As Built, 1965.png"})
    found = one(plan, sheet(name="Building 110 Basement Plan Heating, May 26, 1958.png"))
    assert isinstance(found, Pairing) and found.paired_by == "metadata"


def test_written_floor_ordinals_name_a_floor() -> None:
    # "Second Floor" is floor 2 (the USCG sheets): another floor is refused, not laid by geometry
    plan = PLAN.model_copy(update={"name": "Building 407 Second Floor Plan.png"})
    found = one(plan, sheet(name="Building 407 Heating Layout First Floor Plan.png"))
    assert found == "another floor: 'First Floor' against 'Second Floor'"
    found = one(plan, sheet(name="Building 407 Heating Layout Second Floor Plan.png"))
    assert isinstance(found, Pairing) and found.paired_by == "metadata"


def test_a_project_year_is_not_a_sheet_number() -> None:
    # review-495 N1: "KOY_2019" on both files is the project, not floor 2019 of each
    plan = PLAN.model_copy(update={"name": "KOY_2019 plan.pdf", "rooms": ()})
    found = one(plan, sheet(name="KOY_2019 heating.png", rooms=(), size_m=(10.0, 10.0)))
    assert found == "only 0 room names appear on both sheets (3 are needed)"

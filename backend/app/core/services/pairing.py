"""Which services picture is the plan's floor (docs/specs/backend/services-follow.md, SFP-9..):
the sheets' own words first (the floor their titles and file names name, their sheet numbers),
then geometry (the sheet laid over the plan by a register). Pure; every pairing says why in plain
words, and every refusal says why not, so a wrong pairing is visible and can be refused.
"""

import math
import re
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath

from shapely.geometry import LineString, Point

from app.core.plan_edit.walls import PlanPage
from app.core.services.model import Affine, Pairing, Point2
from app.core.services.picture_follow import Sheet, align
from app.core.services.register import Place, Segment, register

# A register lays a sheet over the plan: the map and how it was found, or why it cannot. The
# wall-line fit (rotation and scale, Madalina's side) plugs in here.
Register = Callable[[Sheet, Sheet], tuple[Affine, str] | str]

# A part of a sheet (x0, y0, x1, y1 in its units, pixels) and its wall lines in the part's own
# units (from its corner): the whole page, or a plan view the finder cut out (plan_view.py).
Crop = tuple[tuple[float, float, float, float], Sequence[Segment]]
# A sheet's parts with their wall lines and its page's size in its units, or why none.
SheetWalls = Callable[[Sheet], tuple[Sequence[Crop], Point2] | str]

SCORE_BOTH, SCORE_PAGE, SCORE_GEOMETRY = 0.9, 0.7, 0.6
FACES_M = (0.03, 0.6)  # two parallel faces of the wall mass this far apart are one wall
FACE_MIN_M = 0.3  # shorter faces (door reveals, wall ends) give no wall line
PARALLEL_DEG = 3.0
SCALE_SLACK = 0.05  # a sheet's own scale and the walls' fitted one further apart are named
SAME_SIZE = 0.02  # two sheets this close in metres are taken to share their frame
CROPS_AGREE = (2.0, 0.02)  # two crops' lays agree within this turn (deg) and share of the plan
CROPS_MARGIN = 1.3  # ... else the best must match this many times the other's wall lines

# Floor words -> one key per floor ("0" ground, "1" first upper, "-1" basement, "roof").
# shortcut: one numbering for every set (Finnish "1. krs" is the ground floor, German "EG" is 0);
# a mixed-language set compares wrong: normalise per set when a real one shows it
_FLOORS: tuple[tuple[str, str], ...] = (
    (r"\b(?:eg|erdgeschoss|gf|ground(?:\s+floor)?)\b", "0"),
    (r"\b(?:dg|dachgeschoss|roof|attic|ullakko)\b", "roof"),
    (r"\b(?:ug|kg|untergeschoss|kellergeschoss|keller|kellari|basement|cellar)\b", "-1"),
    (r"\b(\d)f\b", "{}"),
    (r"\bb(\d{1,2})\b", "-{}"),  # B1, B01
    (r"\be(\d{2})\b", "{}"),  # level codes E00, E01 (the DigitalHub sheets)
    (r"\b(\d{1,2})\s*\.?\s*(?:og|obergeschoss|krs|kerros|etage|stock)\b", "{}"),
    (
        r"\b(?:og|floor|fl|level|storey|story|etage|niveau|lvl|l|krs|kerros)\s*[-.]?\s*(\d{1,2})\b",
        "{}",
    ),
    (r"\b(\d{1,2})(?:st|nd|rd|th)\s+floor\b", "{}"),
)
_NUMBER = re.compile(r"\b([A-Z]{1,3})[-_ .]?(\d{3,4})\b")


def by_room_names(plan: Sheet, sheet: Sheet) -> tuple[Affine, str] | str:
    """The default register: the room-name shift (`align`); floors are `pair`'s business."""
    place = align(
        plan.model_copy(update={"storey": None}), sheet.model_copy(update={"storey": None})
    )
    if isinstance(place, str):
        return place
    n = len(_printed_once(plan) & _printed_once(sheet))
    return place, f"laid over by the {n} room names both sheets print"


def by_walls(plan_walls: Sequence[Segment], sheet_walls: SheetWalls) -> Register:
    """The wall-line register (`register`): each part of the sheet's lines laid on the plan's
    walls (metres), the part's corner added back; the best lay as a map of page fractions with
    `register`'s words. Two parts that lay the sheet two ways with no clear winner are refused
    (twin views), as is a cut-out part laid off the sheet's own scale (it has no page to fill)."""

    def laid(plan: Sheet, sheet: Sheet) -> tuple[Affine, str] | str:
        if plan.size_m is None:
            return "the plan has no scale"
        found = sheet_walls(sheet)
        if isinstance(found, str):
            return found
        crops, size = found
        places: list[tuple[Place, bool]] = []
        why: list[str] = []
        for box, lines in crops:
            got = register(plan_walls, lines)
            if isinstance(got, Place):
                whole = box == (0.0, 0.0, size[0], size[1])
                places.append((_from_corner(got, box[:2]), whole))
            else:
                why.append(got.reason)
        if not places:
            return "; ".join(dict.fromkeys(why))
        placed, whole = max(places, key=lambda p: p[0].inliers)
        for other, _ in places:
            if (
                other is not placed
                and not _agree(placed, other, size, plan.size_m)
                and placed.inliers < CROPS_MARGIN * other.inliers
            ):
                return (
                    f"two parts of the sheet lay it two ways ({placed.inliers} and "
                    f"{other.inliers} wall lines match): which view is the plan is a guess"
                )
        how = placed.reason
        if sheet.size_m is not None:  # its own scale (a scale bar): say when the walls disagree
            bar = sheet.size_m[0] / size[0]
            if abs(placed.scale / bar - 1) > SCALE_SLACK:
                said = (
                    f"its scale says {bar * 1000:.1f} mm a pixel, the walls "
                    f"{placed.scale * 1000:.1f} mm"
                )
                if not whole:
                    return f"a part of the sheet matches the walls, but {said}: not laid"
                how += f"; {said}: laid by the walls"
        return _fractions(placed, size, plan.size_m), how

    return laid


def _from_corner(placed: Place, corner: tuple[float, float]) -> Place:
    """`placed` for the page's units, from a crop's whose corner is `corner`: p = sR(u - o) + t."""
    t = math.radians(placed.rotation_deg)
    s, (ox, oy) = placed.scale, corner
    x = placed.shift[0] - s * (math.cos(t) * ox - math.sin(t) * oy)
    y = placed.shift[1] - s * (math.sin(t) * ox + math.cos(t) * oy)
    return placed.model_copy(update={"shift": (x, y)})


def _agree(a: Place, b: Place, size: Point2, plan_m: Point2) -> bool:
    """Whether two lays put the sheet's middle at the same spot of the plan, turned alike."""
    turn = abs((a.rotation_deg - b.rotation_deg + 180.0) % 360.0 - 180.0)
    middle = (size[0] / 2, size[1] / 2)
    return turn <= CROPS_AGREE[0] and math.dist(_lay(a, middle), _lay(b, middle)) <= CROPS_AGREE[
        1
    ] * max(plan_m)


def _lay(placed: Place, q: Point2) -> Point2:
    t = math.radians(placed.rotation_deg)
    x = placed.scale * (math.cos(t) * q[0] - math.sin(t) * q[1]) + placed.shift[0]
    y = placed.scale * (math.sin(t) * q[0] + math.cos(t) * q[1]) + placed.shift[1]
    return (x, y)


def either(*registers: Register) -> Register:
    """The first register that lays the sheet over; else all their reasons."""

    def laid(plan: Sheet, sheet: Sheet) -> tuple[Affine, str] | str:
        why: list[str] = []
        for one in registers:
            found = one(plan, sheet)
            if not isinstance(found, str):
                return found
            why.append(found)
        return "; ".join(why)

    return laid


def plan_wall_lines(page: PlanPage) -> list[Segment]:
    """The plan's walls as centre lines in metres: each two parallel faces of the drawn wall
    mass a wall's thickness apart, outer walls included, along the stretch they share."""
    faces: list[tuple[Point2, Point2]] = []
    for outer, holes in page.mass:
        for ring in (outer, *holes):
            pts = [(x * page.width_m, y * page.height_m) for x, y in ring]
            faces += [
                (a, b)
                for a, b in zip(pts, pts[1:] + pts[:1], strict=True)
                if math.dist(a, b) >= FACE_MIN_M
            ]
    out: list[Segment] = []
    for i, (a, b) in enumerate(faces):
        ux, uy = (b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b)
        for c, d in faces[i + 1 :]:
            vx, vy = (d[0] - c[0]) / math.dist(c, d), (d[1] - c[1]) / math.dist(c, d)
            if abs(ux * vy - uy * vx) > math.sin(math.radians(PARALLEL_DEG)):
                continue
            gap = abs((c[0] - a[0]) * -uy + (c[1] - a[1]) * ux)  # c's distance off a-b's line
            if not FACES_M[0] <= gap <= FACES_M[1]:
                continue
            along = sorted(((c[0] - a[0]) * ux + (c[1] - a[1]) * uy,
                            (d[0] - a[0]) * ux + (d[1] - a[1]) * uy))  # fmt: skip
            lo, hi = max(0.0, along[0]), min(math.dist(a, b), along[1])
            if hi - lo < FACE_MIN_M:
                continue
            other = LineString([c, d])
            ends: list[Point2] = []
            for t in (lo, hi):  # halfway to the other face
                p = Point(a[0] + ux * t, a[1] + uy * t)
                q = other.interpolate(other.project(p))
                ends.append(((p.x + q.x) / 2, (p.y + q.y) / 2))
            out.append(Segment(a=ends[0], b=ends[1]))
    return out


def pair(
    plan: Sheet, candidates: Sequence[Sheet], register: Register = by_room_names
) -> list[Pairing | str]:
    """One result per candidate, in order: how it is the plan's floor, or why it is not taken."""
    found = [_pair(plan, sheet, register) for sheet in candidates]
    # the best per discipline: the plan's own page, then the higher score, then the earlier sheet
    best: dict[str, int] = {}
    for i, (sheet, got) in enumerate(zip(candidates, found, strict=True)):
        if isinstance(got, str):
            continue
        for d in sheet.disciplines:
            j = best.get(d)
            if j is None or _rank(got) > _rank(found[j]):
                best[d] = i
    out: list[Pairing | str] = []
    for i, (sheet, got) in enumerate(zip(candidates, found, strict=True)):
        if isinstance(got, str) or not sheet.disciplines:
            out.append(got)
            continue
        lost = [d for d in sheet.disciplines if best[d] != i]
        # shortcut: a sheet that wins one of its lanes is kept whole; split a sheet's lanes when
        # one picture marks several disciplines and loses some of them
        if len(lost) == len(sheet.disciplines):
            out.append(f"another {lost[0]} picture was taken: {_shown(candidates[best[lost[0]]])}")
            continue
        others = [
            _shown(other)
            for k, (other, theirs) in enumerate(zip(candidates, found, strict=True))
            if k != i
            and not isinstance(theirs, str)
            and set(other.disciplines) & {d for d in sheet.disciplines if best[d] == i}
        ]
        if others:
            got = got.model_copy(
                update={"reason": f"{got.reason} (also offered: {', '.join(others)})"}
            )
        out.append(got)
    return out


def _pair(plan: Sheet, sheet: Sheet, register: Register) -> Pairing | str:
    def made(paired_by: str, reason: str, score: float | None, to_plan: Affine) -> Pairing:
        return Pairing.model_validate(
            {
                "drawing_id": sheet.drawing_id,
                "page": sheet.page,
                "paired_by": paired_by,
                "reason": reason,
                "score": score,
                "to_plan": to_plan,
            }
        )

    if (sheet.drawing_id, sheet.page) == (plan.drawing_id, plan.page):
        return made("same_page", "the plan's own page", None, Affine())
    mine, theirs = _folder(plan), _folder(sheet)
    if mine and theirs and mine != theirs:
        return f"another set: folder '{theirs}' against '{mine}'"
    hints, refused = _metadata(plan, sheet)
    if refused:
        return refused
    laid = register(plan, sheet)
    if hints and not isinstance(laid, str):
        to_plan, how = laid
        return made("metadata", f"same floor: {hints}; {how}", SCORE_BOTH, to_plan)
    if hints and _same_size(plan, sheet):
        assert plan.size_m is not None
        w, h = plan.size_m
        how = f"laid over page to page: both sheets are {w:.1f} by {h:.1f} m"
        return made("metadata", f"same floor: {hints}; {how}", SCORE_PAGE, Affine())
    if hints:
        assert isinstance(laid, str)
        return f"same floor ({hints}), but it cannot be laid over the plan: {laid}"
    if isinstance(laid, str):
        return laid
    to_plan, how = laid
    return made("geometry", how, SCORE_GEOMETRY, to_plan)


def _metadata(plan: Sheet, sheet: Sheet) -> tuple[str, str]:
    """What the two sheets' words agree on ("'Floor 1' on both; sheet numbers A-101 / H-101"),
    "" when they say nothing either way; and the refusal ("another floor: ..."), else ""."""
    mine, theirs = _floors(plan), _floors(sheet)
    agreed: list[str] = []
    if mine and theirs:
        shared = [k for k in theirs if k in mine]
        if not shared:
            first = next(iter(theirs))
            return "", f"another floor: '{theirs[first]}' against '{next(iter(mine.values()))}'"
        a, b = theirs[shared[0]], mine[shared[0]]
        agreed.append(f"'{a}' on both" if a.casefold() == b.casefold() else f"'{a}' and '{b}'")
    n_mine, n_theirs = _number(plan), _number(sheet)
    if n_mine and n_theirs:
        if n_mine[1] == n_theirs[1]:
            agreed.append(f"sheet numbers {n_mine[0]} / {n_theirs[0]}")
        elif not agreed:
            return "", f"another floor: sheet number {n_theirs[0]} against {n_mine[0]}"
    return "; ".join(agreed), ""


def _floors(sheet: Sheet) -> dict[str, str]:
    """The floors a sheet's title, sheet number and file name name: key -> the words as printed."""
    found: dict[str, str] = {}
    for text in (sheet.storey, sheet.sheet_number, sheet.name):
        if not text:
            continue
        spaced = text.replace("_", " ")
        for pattern, key in _FLOORS:
            for m in re.finditer(pattern, spaced, re.IGNORECASE):
                k = key.format(int(m.group(1))) if m.groups() else key
                found.setdefault(k, m.group(0))
    return found


def _number(sheet: Sheet) -> tuple[str, str] | None:
    """The sheet number as printed and its part after the discipline letters (H-101 -> 101)."""
    for text in (sheet.sheet_number, PurePosixPath(sheet.name).name if sheet.name else None):
        m = _NUMBER.search(text or "")
        if m:
            return m.group(0), m.group(2)
    return None


def _fractions(placed: Place, size: Point2, plan_m: Point2) -> Affine:
    """`register`'s similarity (sheet units -> plan metres) as page fractions to page fractions."""
    (w, h), (pw, ph) = size, plan_m
    t = math.radians(placed.rotation_deg)
    cos, sin, s = math.cos(t), math.sin(t), placed.scale
    return Affine(
        a=s * cos * w / pw,
        b=-s * sin * h / pw,
        c=placed.shift[0] / pw,
        d=s * sin * w / ph,
        e=s * cos * h / ph,
        f=placed.shift[1] / ph,
    )


def _folder(sheet: Sheet) -> str | None:
    """The upload's top-level folder (one set of drawings); None at the top."""
    parts = PurePosixPath(sheet.name).parts if sheet.name else ()
    return parts[0] if len(parts) > 1 else None


def _same_size(plan: Sheet, sheet: Sheet) -> bool:
    if plan.size_m is None or sheet.size_m is None:
        return False
    return all(abs(s - p) <= SAME_SIZE * p for p, s in zip(plan.size_m, sheet.size_m, strict=True))


def _printed_once(sheet: Sheet) -> set[str]:
    names = [" ".join(n.casefold().split()) for n, _ in sheet.rooms]
    return {n for n in names if names.count(n) == 1}


def _rank(found: Pairing | str) -> float:
    assert not isinstance(found, str)
    return 2.0 if found.paired_by == "same_page" else (found.score or 0.0)


def _shown(sheet: Sheet) -> str:
    return PurePosixPath(sheet.name).name if sheet.name else sheet.drawing_id

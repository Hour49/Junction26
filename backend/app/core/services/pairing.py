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

# A sheet's wall lines in its own units (pixels) and its page's size in them, or why none.
SheetWalls = Callable[[Sheet], tuple[Sequence[Segment], Point2] | str]

SCORE_BOTH, SCORE_PAGE, SCORE_GEOMETRY = 0.9, 0.7, 0.6
FACES_M = (0.03, 0.6)  # two parallel faces of the wall mass this far apart are one wall
FACE_MIN_M = 0.3  # shorter faces (door reveals, wall ends) give no wall line
PARALLEL_DEG = 3.0
SCALE_SLACK = 0.05  # a sheet's own scale and the walls' fitted one further apart are named
SAME_SIZE = 0.02  # two sheets this close in metres are taken to share their frame

# Floor words -> one key per floor ("0" ground, "1" first upper, "-1" basement, "roof").
# shortcut: one numbering for every set (Finnish "1. krs" is the ground floor, German "EG" is 0);
# a mixed-language set compares wrong: normalise per set when a real one shows it
# Level codes E00, E01 (the DigitalHub sheets); an electrical sheet's number E01 is no level, so
# they are read only from the title's floor and inside a file name, never as its sheet number
# (review-495 M2)
_LEVEL_CODE = (r"\be(\d{2})\b", "{}")
_FLOORS: tuple[tuple[str, str], ...] = (
    (r"\b(?:eg|erdgeschoss|gf|ground(?:\s+floor)?)\b", "0"),
    (r"\b(?:dg|dachgeschoss|attic|ullakko)\b", "attic"),  # not the roof (pics-answer, building 333)
    (r"\broof\b", "roof"),
    (r"\b(?:ug|kg|untergeschoss|kellergeschoss|keller|kellari|basement|cellar)\b", "-1"),
    (r"\b(\d)f\b", "{}"),
    (r"\bb(\d{1,2})\b", "-{}"),  # B1, B01
    _LEVEL_CODE,
    (r"\b(\d{1,2})\s*\.?\s*(?:og|obergeschoss|krs|kerros|etage|stock)\b", "{}"),
    (
        r"\b(?:og|floor|fl|level|storey|story|etage|niveau|lvl|l|krs|kerros)\s*[-.]?\s*(\d{1,2})\b",
        "{}",
    ),
)
# Floors named in words, alone or listed: "First Floor", "2nd floor", "Basement, First and Second
# Floor", "Second Thru Seventh Floors" (the USCG sheets' words; pics-answer, 2026-11-15)
_ORDINALS = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
)
_ITEM = rf"(?:ground|basement|cellar|attic|{'|'.join(_ORDINALS)}|\d{{1,2}}(?:st|nd|rd|th))"
_SEP = r"(?:\s*,\s*(?:and\s+)?|\s+(?:and|&|thru|through|to)\s+|\s*-\s*)"
_PHRASE = re.compile(
    rf"\b{_ITEM}(?:{_SEP}{_ITEM})*\s+(?:floors?|storeys?|story|stories|levels?)\b", re.IGNORECASE
)
_NUMBERED = re.compile(  # "Floors 2-4", "levels 3 to 5"
    r"\b(?:floors|levels|storeys)\s+(\d{1,2})\s*(-|to|thru|through|and|&)\s*(\d{1,2})\b",
    re.IGNORECASE,
)
_RANGE = ("-", "to", "thru", "through")
# A floor the name says that no rule reads: pairing must not fall back to geometry on it
_UNREAD = re.compile(
    r"\b(?:(?:typical|upper|lower|main|top|intermediate|mezzanine|all|other|remaining|each)\s+"
    r"(?:floors?|levels?|storeys?)|[a-z]+\s+(?:floors|levels|storeys|stories))\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\b([A-Z]{1,3})[-_ .]?(\d{3,4})\b")
_YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")  # a year is no sheet number (N1)
# Top-level folders named by discipline are one delivery, not two sets (review-495 S1)
_DISCIPLINE_FOLDERS = frozenset(
    {
        "architektur", "architecture", "architectural", "arch", "ark", "hvac", "hls", "lvi",
        "mep", "tga", "haustechnik", "heizung", "heating", "lüftung", "lueftung", "ventilation",
        "sanitär", "sanitaer", "plumbing", "elektro", "electrical", "sähkö", "sahko", "säh", "sah",
    }
)  # fmt: skip


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
    """The wall-line register (`register`): the sheet's lines laid on the plan's walls (metres),
    the result as a map of page fractions with `register`'s words."""

    def laid(plan: Sheet, sheet: Sheet) -> tuple[Affine, str] | str:
        if plan.size_m is None:
            return "the plan has no scale"
        found = sheet_walls(sheet)
        if isinstance(found, str):
            return found
        lines, size = found
        placed = register(plan_walls, lines)
        if not isinstance(placed, Place):
            return placed.reason
        how = placed.reason
        if sheet.size_m is not None:  # its own scale (a scale bar): say when the walls disagree
            bar = sheet.size_m[0] / size[0]
            if abs(placed.scale / bar - 1) > SCALE_SLACK:
                how += (
                    f"; its scale says {bar * 1000:.1f} mm a pixel, the walls "
                    f"{placed.scale * 1000:.1f} mm: laid by the walls"
                )
        return _fractions(placed, size, plan.size_m), how

    return laid


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
    # Several sheets laid over by geometry alone, none naming a floor, fit alike: the floors
    # of a building print the same room names, so the first upload would be a guess (review-495 M3)
    tied: dict[str, list[int]] = {}
    for d, i in best.items():
        top = found[i]
        if isinstance(top, str) or top.paired_by != "geometry":
            continue
        alike = [
            k
            for k, (other, theirs) in enumerate(zip(candidates, found, strict=True))
            if d in other.disciplines
            and not isinstance(theirs, str)
            and theirs.paired_by == "geometry"
            and theirs.score == top.score
        ]
        if len(alike) > 1:
            tied[d] = alike
    out: list[Pairing | str] = []
    for i, (sheet, got) in enumerate(zip(candidates, found, strict=True)):
        if isinstance(got, str) or not sheet.disciplines:
            out.append(got)
            continue
        won = {d for d in sheet.disciplines if best[d] == i and d not in tied}
        # shortcut: a sheet that wins one of its lanes is kept whole; split a sheet's lanes when
        # one picture marks several disciplines and loses some of them
        if not won:
            d = next((d for d in sheet.disciplines if i in tied.get(d, ())), None)
            if d is not None:
                names = ", ".join(_shown(candidates[k]) for k in tied[d])
                out.append(
                    f"{len(tied[d])} {d} pictures fit this plan alike and none names its floor "
                    f"({names}): which one is this floor is not known"
                )
                continue
            lost = sheet.disciplines[0]
            out.append(f"another {lost} picture was taken: {_shown(candidates[best[lost]])}")
            continue
        others = [
            _shown(other)
            for k, (other, theirs) in enumerate(zip(candidates, found, strict=True))
            if k != i and not isinstance(theirs, str) and set(other.disciplines) & won
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
    if mine and theirs and mine != theirs and not (_by_discipline(mine) and _by_discipline(theirs)):
        return f"another set: folder '{theirs}' against '{mine}'"
    hints, refused = _metadata(plan, sheet)
    if refused:
        return refused
    if not hints:  # geometry alone must not pick a floor the names say but no rule reads
        for who, one in (("the plan", plan), ("the services picture", sheet)):
            if (words := _unread(one)) is not None:
                return f"{who} names a floor that is not read ('{words}'): no floor to pair on"
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
    # A folder's floor words ("EG/", "OG 1/") refuse when they differ, but never agree: a set's
    # folder ("B1/") is on every floor's sheet (review-558)
    every_mine = mine | {k: v for k, v in _floors(plan, folders=True).items() if k not in mine}
    every_theirs = theirs | {
        k: v for k, v in _floors(sheet, folders=True).items() if k not in theirs
    }
    only_mine = [k for k in every_mine if k not in every_theirs]
    only_theirs = [k for k in every_theirs if k not in every_mine]
    if only_mine and only_theirs:
        return (
            "",
            f"another floor: '{every_theirs[only_theirs[0]]}' against '{every_mine[only_mine[0]]}'",
        )
    agreed: list[str] = []
    if mine and theirs:
        # each names a floor the other doesn't: they differ, whatever else both name (a building
        # folder "B1" shared by every floor of the set; review-495 M1)
        only_mine = [k for k in mine if k not in theirs]
        only_theirs = [k for k in theirs if k not in mine]
        if only_mine and only_theirs:
            return "", f"another floor: '{theirs[only_theirs[0]]}' against '{mine[only_mine[0]]}'"
        shared = [k for k in theirs if k in mine]
        a, b = theirs[shared[0]], mine[shared[0]]
        agreed.append(f"'{a}' on both" if a.casefold() == b.casefold() else f"'{a}' and '{b}'")
    n_mine, n_theirs = _number(plan), _number(sheet)
    if n_mine and n_theirs:
        if n_mine[1] == n_theirs[1]:
            agreed.append(f"sheet numbers {n_mine[0]} / {n_theirs[0]}")
        elif not agreed:
            return "", f"another floor: sheet number {n_theirs[0]} against {n_mine[0]}"
    return "; ".join(agreed), ""


def _floors(sheet: Sheet, folders: bool = False) -> dict[str, str]:
    """The floors a sheet's title, sheet number and file name name: key -> the words as printed.
    Not its folders (a set's folder "B1/" is on every floor's sheet, review-558 M1); with
    `folders`, only what its folders name."""
    found: dict[str, str] = {}
    for source, text in _texts(sheet, folders):
        found.update({k: v for k, v in _read(text, source)[0].items() if k not in found})
    return found


def _texts(sheet: Sheet, folders: bool = False) -> list[tuple[str, str]]:
    """Where a sheet's floor is read: its title's floor, its sheet number, its file name; with
    `folders`, its folders only."""
    path = PurePosixPath(sheet.name) if sheet.name else None
    if folders:
        texts = [("folder", " ".join(path.parent.parts) if path else None)]
    else:
        texts = [("title", sheet.storey), ("number", sheet.sheet_number),
                 ("name", path.name if path else None)]  # fmt: skip
    return [(source, text.replace("_", " ")) for source, text in texts if text]


def _read(text: str, source: str) -> tuple[dict[str, str], list[tuple[int, int]]]:
    """The floors one text names (key -> words) and where in it they were read."""
    found: dict[str, str] = {}
    spans: list[tuple[int, int]] = []
    for pattern, key in _FLOORS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            if (pattern, key) == _LEVEL_CODE and not _level_code(source, m.start()):
                continue
            found.setdefault(key.format(int(m.group(1))) if m.groups() else key, m.group(0))
            spans.append(m.span())
    for m in _PHRASE.finditer(text):
        for key in _phrase_keys(m.group(0)):
            found.setdefault(key, m.group(0))
        spans.append(m.span())
    for m in _NUMBERED.finditer(text):
        a, how, b = int(m.group(1)), m.group(2).casefold(), int(m.group(3))
        for n in range(a, b + 1) if how in _RANGE else (a, b):
            found.setdefault(str(n), m.group(0))
        spans.append(m.span())
    return found, spans


def _phrase_keys(words: str) -> list[str]:
    """The floors of a listed phrase: "Basement, First and Second Floor" -> -1, 1, 2; a range
    of numbered floors ("Second Thru Seventh") is every floor between."""
    parts = re.split(rf"({_SEP})", words, flags=re.IGNORECASE)
    keys: list[str] = []
    for i in range(0, len(parts), 2):
        item = re.match(_ITEM, parts[i].strip(), re.IGNORECASE)
        if item is None:
            continue
        key = _item_key(item.group(0))
        joint = parts[i - 1].strip().casefold() if i else ""
        if joint in _RANGE and keys and keys[-1].isdigit() and key.isdigit():
            keys += [str(n) for n in range(int(keys[-1]) + 1, int(key))]
        keys.append(key)
    return keys


def _item_key(word: str) -> str:
    low = word.casefold()
    if low in _ORDINALS:
        return str(_ORDINALS.index(low) + 1)
    if low[:-2].isdigit():
        return str(int(low[:-2]))
    return {"ground": "0", "basement": "-1", "cellar": "-1"}.get(low, low)


def _unread(sheet: Sheet) -> str | None:
    """Words of the sheet that name a floor no rule reads ("Upper Floors", "Typical Floor")."""
    for source, text in _texts(sheet):
        spans = _read(text, source)[1]
        for m in _UNREAD.finditer(text):
            if not any(a <= m.start() < b or a < m.end() <= b for a, b in spans):
                return m.group(0)
    return None


def _number(sheet: Sheet) -> tuple[str, str] | None:
    """The sheet number as printed and its part after the discipline letters (H-101 -> 101)."""
    if sheet.sheet_number and (m := _NUMBER.search(sheet.sheet_number)):
        return m.group(0), m.group(2)
    for m in _NUMBER.finditer(PurePosixPath(sheet.name).name if sheet.name else ""):
        if not _YEAR.fullmatch(m.group(2)):  # "KOY_2019" is the project's year (review-495 N1)
            return m.group(0), m.group(2)
    return None


def _level_code(source: str, at: int) -> bool:
    """Whether an E00/E01 code found at `at` in a sheet's title floor, sheet number or file name
    is a level: always in the title's floor, never as the sheet number, and in the file name only
    inside it (as the name's first word it is the number: "E01 Elektro.png")."""
    return source == "title" or (source == "name" and at != 0)


def _by_discipline(folder: str) -> bool:
    """A folder named by its discipline ("Architektur", "02_HVAC")."""
    return re.sub(r"^[\d\s._-]+", "", folder).casefold() in _DISCIPLINE_FOLDERS


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

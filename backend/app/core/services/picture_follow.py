"""A plan edit followed on a services picture (docs/specs/backend/services-follow.md, pictures):
what a services sheet that is a picture draws on or across a removed or added wall, by geometry
on the page, in the follow-up's own shape (`ServicesFollow`). Pure: the picture's marks come from
its `FactSheet` (app/core/picture_facts.py), one spot per symbol or run piece.

A picture shows where things are drawn, not how they connect or at what height, so nothing here
re-seats, traces or cuts off: a symbol on a removed wall has to move, a run inside it goes with
it, a run across it stays, a run across a new wall needs an opening; each says what the picture
cannot tell.

The services sheet lies over the plan when it is the plan's own page (identity), or another sheet
of the same floor when both have a scale and at least three room names appear on both: then the
two are laid over by the names' places in metres (a shift; the sheets' scales give the size).
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.core.ifc_facts import Discipline, FactSheet, Spot
from app.core.model import Frozen
from app.core.plan_edit.model import Item, Proposal
from app.core.services.follow import LETTER, counted
from app.core.services.model import (
    LANES,
    Affine,
    Code,
    DisciplineFollow,
    FollowPicture,
    Pairing,
    PictureMark,
    Point2,
    ServiceAction,
    ServiceMark,
    ServicesFollow,
    Status,
    Summary,
)

ON_M = 0.15  # a symbol this close to a wall strip is on it (follow.py's ON_M)
IN_M = 0.02  # tolerance of "inside the strip"
PASSAGE_M = 0.5  # more run than this (or twice the wall's thickness) inside a wall runs along it
NEAR_M = 3.0  # how far around the edit the overlay shows the picture's marks
ALIGN_M = 0.5  # the shared room names of two sheets may miss each other by this much
MIN_ROOMS = 3
# Without a scale (the plan's own page only) the same tests in page fractions.
ON_FRAC, IN_FRAC, NEAR_FRAC = 0.005, 0.001, 0.1

CANNOT = "what it feeds and whether it can be rerouted are not shown on a picture"
UNKNOWNS = (
    "A services picture shows where things are drawn, not how they connect: what a run feeds "
    "and whether it can be rerouted are not shown on a picture.",
    "A picture shows no heights: what is drawn on a wall's line may run in the floor or under "
    "the ceiling.",
    "The picture's symbols and runs are read by vision; one the readers missed is not here.",
)
_WORDS = {
    "space_heater": "radiator",
    "outlet": "socket",
    "air_terminal": "air terminal",
    "sanitary_terminal": "sanitary fixture",
    "light_fixture": "light",
    "switching_device": "switch",
    "pipe_segment": "pipe",
    "duct_segment": "duct",
    "cable_carrier_segment": "cable tray",
}


class Sheet(Frozen):
    """Where a page lies: its drawing and page, the floor its title names, its size in metres
    (None: no scale) and the room names it prints with their places (page fractions)."""

    drawing_id: str
    page: int
    storey: str | None = None
    size_m: Point2 | None = None
    rooms: tuple[tuple[str, Point2], ...] = ()


Place = Callable[[Point2], Point2]  # a services page's fractions -> the plan page's fractions


@dataclass(frozen=True, eq=False)  # one per spot, by identity
class _Thing:
    """One symbol or run piece of the picture, in the plan's units (metres, else fractions)."""

    discipline: Discipline
    word: str  # "radiator", "pipe"
    label: str  # the legend's label as printed
    size: str | None
    shape: BaseGeometry
    run: bool
    frac: tuple[Point2, ...]  # its centre (a symbol) or its line (a run), plan fractions
    sheet: tuple[str, int] = ("", 0)  # the drawing and page it is drawn on
    own: tuple[Point2, ...] = ()  # `frac` in that sheet's fractions

    @property
    def name(self) -> str:
        return f"{self.label} ({self.size})" if self.size else self.label


@dataclass
class _Found:
    code: Code
    status: Status
    label: str
    things: list[_Thing]


def align(plan: Sheet, sheet: Sheet) -> Affine | str:
    """How the services sheet's fractions land on the plan's, or why they cannot."""
    if (sheet.drawing_id, sheet.page) == (plan.drawing_id, plan.page):
        return Affine()
    if plan.storey and sheet.storey and _norm(plan.storey) != _norm(sheet.storey):
        return f"the services picture is of another floor ({sheet.storey})"
    if plan.size_m is None:
        return "the plan has no scale"
    if sheet.size_m is None:
        return "the services picture has no scale"
    (pw, ph), (sw, sh) = plan.size_m, sheet.size_m
    mine, theirs = _named(plan.rooms), _named(sheet.rooms)
    shared = sorted(mine.keys() & theirs.keys())
    if len(shared) < MIN_ROOMS:
        n = len(shared)
        return (
            f"only {n} room name{'' if n == 1 else 's'} appear{'s' if n == 1 else ''} on both "
            f"sheets ({MIN_ROOMS} are needed)"
        )
    pairs = [
        ((theirs[k][0] * sw, theirs[k][1] * sh), (mine[k][0] * pw, mine[k][1] * ph)) for k in shared
    ]
    dx = sum(p[0] - s[0] for s, p in pairs) / len(pairs)
    dy = sum(p[1] - s[1] for s, p in pairs) / len(pairs)
    worst = max(((s[0] + dx - p[0]) ** 2 + (s[1] + dy - p[1]) ** 2) ** 0.5 for s, p in pairs)
    if worst > ALIGN_M:
        return f"the room names of the two sheets miss each other by up to {worst:.2f} m"
    # shortcut: a shift only (sheets of one floor share their orientation); fit a rotation when
    # a real pair of sheets needs one
    return Affine(a=sw / pw, c=dx / pw, e=sh / ph, f=dy / ph)


def picture_follow(
    proposal: Proposal,
    plan: Sheet,
    sheets: Sequence[tuple[Sheet, FactSheet]],
    pairings: Sequence[Pairing | str] | None = None,
) -> ServicesFollow:
    """The proposal's removed and added walls followed on every services picture of the floor.
    `pairings`, in the sheets' order: how each lies on the plan, or why it does not (pics W1);
    None: each by `align`."""
    unit = plan.size_m or (1.0, 1.0)
    metres = plan.size_m is not None
    on, inside, near = (ON_M, IN_M, NEAR_M) if metres else (ON_FRAC, IN_FRAC, NEAR_FRAC)
    passage = PASSAGE_M if metres else 0.0
    removed, added = _strips(proposal.removed, unit), _strips(proposal.added, unit)
    changed = unary_union([removed[0], added[0]])
    things: dict[Discipline, list[_Thing]] = defaultdict(list)
    sources: dict[Discipline, list[str]] = defaultdict(list)
    refused: dict[Discipline, str] = {}
    taken: dict[Discipline, Pairing] = {}  # the first sheet laid over, per lane
    for n, (sheet, facts) in enumerate(sheets):
        paired = pairings[n] if pairings is not None else _paired(plan, sheet)
        if isinstance(paired, str):
            for f in facts.facts:
                if f.discipline in LANES and f.spots:
                    refused.setdefault(f.discipline, paired)
            continue
        place = (paired.to_plan or Affine()).apply
        for discipline, found in _things(sheet, facts, place, unit).items():
            things[discipline] += found
            sources[discipline].append(sheet.drawing_id)
            taken.setdefault(discipline, paired)
    lanes: list[DisciplineFollow] = []
    for discipline in LANES:
        name = discipline.capitalize()
        if discipline not in things:
            status = "not_aligned" if discipline in refused else "no_model"
            why = (
                refused.get(discipline) or f"this project has no {discipline} picture of this floor"
            )
            lanes.append(
                DisciplineFollow(
                    discipline=discipline,
                    status=status,
                    reason=why,
                    line=f"{name}: not checked, {why}.",
                )
            )
            continue
        here = things[discipline]
        found = [
            *_on_wall(here, removed, "removed", on, inside, passage),
            *_on_wall(here, added, "added", on, inside, passage),
        ]
        lane = _lane(discipline, here, found, changed, near, sources[discipline])
        lanes.append(
            lane.model_copy(update={"picture": _picture(lane, here, proposal, taken[discipline])})
        )
    return ServicesFollow(
        storey=plan.storey,
        disciplines=tuple(lanes),
        unknowns=UNKNOWNS if any(d.status == "checked" for d in lanes) else (),
    )


def _paired(plan: Sheet, sheet: Sheet) -> Pairing | str:
    """`align` as a pairing: the plan's own page, or a sheet laid over by its room names."""
    place = align(plan, sheet)
    if isinstance(place, str):
        return place
    own = (sheet.drawing_id, sheet.page) == (plan.drawing_id, plan.page)
    return Pairing(
        drawing_id=sheet.drawing_id,
        page=sheet.page,
        paired_by="same_page" if own else "geometry",
        reason="the services marks are on the plan's own page"
        if own
        else f"laid over the plan by the room names both sheets print (within {ALIGN_M} m) "
        "and their scales",
        to_plan=place,
    )


def _picture(
    lane: DisciplineFollow, here: list[_Thing], proposal: Proposal, paired: Pairing
) -> FollowPicture:
    """The lane's sheet with the edit and the lane's marks in that sheet's page fractions."""
    back = (paired.to_plan or Affine()).inverse()
    sheet = (paired.drawing_id, paired.page)

    def mapped(items: Sequence[Item]) -> tuple[tuple[Point2, ...], ...]:
        return tuple(tuple(_round(back.apply(p)) for p in i.polygon) for i in items)

    mine = {t.frac: t for t in here if t.sheet == sheet}  # a mark's plan place gives its thing
    marks: list[PictureMark] = []
    for mark in lane.marks:
        thing = mine.get(mark.line or ((mark.at,) if mark.at else ()))
        if thing is not None:
            line, at = (thing.own, None) if thing.run else ((), thing.own[0])
            marks.append(PictureMark(ref=mark.ref, line=line, at=at))
    return FollowPicture(
        drawing_id=paired.drawing_id,
        page=paired.page,
        pairing=paired,
        removed=mapped(proposal.removed),
        added=mapped(proposal.added),
        marks=tuple(marks),
    )


def _round(p: Point2) -> Point2:
    return (round(p[0], 5), round(p[1], 5))


# --- reading the picture's marks ------------------------------------------------------------------


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def _named(rooms: Sequence[tuple[str, Point2]]) -> dict[str, Point2]:
    """Room names printed once on the sheet with their places (one printed twice is no anchor)."""
    seen: dict[str, list[Point2]] = defaultdict(list)
    for name, at in rooms:
        seen[_norm(name)].append(at)
    return {k: v[0] for k, v in seen.items() if len(v) == 1}


def _things(
    sheet: Sheet, facts: FactSheet, place: Place, unit: Point2
) -> dict[Discipline, list[_Thing]]:
    """The sheet's symbols (per-label counts) and run pieces (per-label lengths), on the plan;
    `all`, per-size and per-group facts repeat the same spots and are skipped."""
    sizes = {
        s.box: f.subject for f in facts.facts if f.topic.endswith(".size_length") for s in f.spots
    }
    out: dict[Discipline, list[_Thing]] = defaultdict(list)
    for f in facts.facts:
        kind, _, measure = f.topic.rpartition(".")
        if f.discipline not in LANES or f.subject == "all" or kind == "category":
            continue
        if measure not in ("count", "length"):
            continue
        for spot in f.spots:
            if spot.page != sheet.page:
                continue
            out[f.discipline].append(
                _thing(
                    f.discipline,
                    kind,
                    f.subject,
                    sizes.get(spot.box),
                    spot,
                    place,
                    unit,
                    measure == "length",
                    (sheet.drawing_id, sheet.page),
                )
            )
    return out


def _thing(
    discipline: Discipline,
    kind: str,
    label: str,
    size: str | None,
    spot: Spot,
    place: Place,
    unit: Point2,
    run: bool,
    sheet: tuple[str, int] = ("", 0),
) -> _Thing:
    sx0, sy0, sx1, sy1 = spot.box
    x0, y0 = place((sx0, sy0))
    x1, y1 = place((sx1, sy1))
    word = _WORDS.get(kind) or (label if kind == "symbol" else kind.replace("_", " "))
    if not run:
        centre = (round((x0 + x1) / 2, 5), round((y0 + y1) / 2, 5))
        shape = box(x0 * unit[0], y0 * unit[1], x1 * unit[0], y1 * unit[1])
        own = (_round(((sx0 + sx1) / 2, (sy0 + sy1) / 2)),)
        return _Thing(discipline, word, label, size, shape, False, (centre,), sheet, own)
    # shortcut: a run piece's spot is its box, so the piece is taken along the box's long side;
    # a diagonal piece reads as its box's long side (pass the piece's ends when readers give them)
    if (x1 - x0) * unit[0] >= (y1 - y0) * unit[1]:
        ends = ((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2))
        own = ((sx0, (sy0 + sy1) / 2), (sx1, (sy0 + sy1) / 2))
    else:
        ends = (((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1))
        own = (((sx0 + sx1) / 2, sy0), ((sx0 + sx1) / 2, sy1))
    line = LineString([(x * unit[0], y * unit[1]) for x, y in ends])
    frac = tuple((round(x, 5), round(y, 5)) for x, y in ends)
    return _Thing(discipline, word, label, size, line, True, frac, sheet, tuple(map(_round, own)))


def _strips(items: Sequence[Item], unit: Point2) -> tuple[BaseGeometry, float]:
    """The walls as one shape in the plan's units, and the thickest wall's thickness."""
    shapes = [Polygon([(x * unit[0], y * unit[1]) for x, y in i.polygon]) for i in items]
    # a long strip's thickness: 2 x area / perimeter (t L / (L + t) for an L x t rectangle)
    thick = max((2 * s.area / s.length for s in shapes if s.length), default=0.0)
    return unary_union(shapes) if shapes else Polygon(), thick


# --- what lies on or crosses a wall ---------------------------------------------------------------


def _on_wall(
    here: list[_Thing],
    strip: tuple[BaseGeometry, float],
    which: str,
    on: float,
    inside: float,
    passage: float,
) -> list[_Found]:
    wall, thick = strip
    if wall.is_empty:
        return []
    groups: dict[tuple[str, str], list[_Thing]] = defaultdict(list)
    metres: dict[tuple[str, str], float] = defaultdict(float)
    for t in here:
        if not t.run:
            if t.shape.distance(wall) <= on:
                groups[("symbol", t.name)].append(t)
            continue
        if t.shape.distance(wall) > inside:
            continue
        length = t.shape.intersection(wall.buffer(inside)).length
        how = "along" if length > max(2 * thick, passage) else "across"
        groups[(how, t.name)].append(t)
        metres[(how, t.name)] += length
    out: list[_Found] = []
    for (how, name), found in groups.items():
        word, n = found[0].word, len(found)
        if how == "symbol" and which == "removed":
            they = "it has" if n == 1 else "they have"
            out.append(
                _Found(
                    "reseat",
                    "needs_decision",
                    f"{counted(n, word)} ({name}) on the removed wall: {they} to move; where to "
                    "and how to reconnect are not shown on a picture.",
                    found,
                )
            )
        elif how == "symbol":
            out.append(
                _Found(
                    "under",
                    "needs_decision",
                    f"{counted(n, word)} ({name}) on the line of the new wall: "
                    f"{'it has' if n == 1 else 'they have'} to move or the wall to shift; "
                    "a picture shows no heights, so it may sit above or below the wall's line.",
                    found,
                )
            )
        elif how == "along":
            where = (
                "inside the removed wall: it goes with the wall"
                if which == "removed"
                else ("along the new wall: the wall or the run has to shift")
            )
            out.append(
                _Found(
                    "in_wall" if which == "removed" else "under",
                    "needs_decision",
                    f"{metres[(how, name)]:.1f} m of {name} {word} runs {where}; {CANNOT}.",
                    found,
                )
            )
        elif which == "removed":
            out.append(
                _Found(
                    "through",
                    "stays",
                    f"{name} {word} crosses the removed wall {_places(n)}: it stays, now open to "
                    f"the merged room; {CANNOT}.",
                    found,
                )
            )
        else:
            out.append(
                _Found(
                    "opening",
                    "follows",
                    f"{name} {word} crosses the new wall {_places(n)}: "
                    f"{'it needs an opening' if n == 1 else 'each crossing needs an opening'}; "
                    f"{CANNOT}.",
                    found,
                )
            )
    return out


def _places(n: int) -> str:
    return "at 1 place" if n == 1 else f"at {n} places"


# --- the lane -------------------------------------------------------------------------------------


def _lane(
    discipline: Discipline,
    here: list[_Thing],
    found: list[_Found],
    changed: BaseGeometry,
    near: float,
    sources: list[str],
) -> DisciplineFollow:
    named = [t for f in found for t in f.things]
    around = changed.buffer(near)
    shown = list(dict.fromkeys([*named, *(t for t in here if t.shape.intersects(around))]))
    shown.sort(key=lambda t: (t.frac[0][1], t.frac[0][0], t.label))
    letter = LETTER.get(discipline, "S")
    refs = {id(t): f"{letter}{n}" for n, t in enumerate(shown, start=1)}
    marks = tuple(
        ServiceMark(
            ref=refs[id(t)],
            global_id="",  # a picture has no model ids
            kind=t.word,
            label=", ".join(filter(None, (t.word, t.label, t.size))),
            line=t.frac if t.run else (),
            at=None if t.run else t.frac[0],
        )
        for t in shown
    )
    actions = tuple(
        ServiceAction(
            id=f"a{n}",
            status=f.status,
            code=f.code,
            label=f.label,
            refs=tuple(dict.fromkeys(refs[id(t)] for t in f.things)),
        )
        for n, f in enumerate(found, start=1)
    )
    summary = Summary(
        follows=sum(f.status == "follows" for f in found),
        stays=sum(f.status == "stays" for f in found),
        needs_decision=sum(f.status == "needs_decision" for f in found),
    )
    return DisciplineFollow(
        discipline=discipline,
        status="checked",
        source=", ".join(dict.fromkeys(sources)),
        elements=len(here),
        line=f"{discipline.capitalize()}: {_line(found, summary)}",
        summary=summary,
        marks=marks,
        actions=actions,
    )


def _line(found: list[_Found], summary: Summary) -> str:
    if not found:
        return "nothing drawn on this picture is on or crosses the changed walls."
    count: dict[str, int] = defaultdict(int)
    for f in found:
        count[f.code] += len(f.things)
    parts = [
        f"{count['reseat']} on the removed wall to move" if count["reseat"] else "",
        f"{counted(count['in_wall'], 'run piece')} inside the removed wall"
        if count["in_wall"]
        else "",
        f"{counted(count['through'], 'run')} passing through" if count["through"] else "",
        f"{counted(count['opening'], 'opening')} needed in the new wall"
        if count["opening"]
        else "",
        f"{count['under']} on or along the new wall" if count["under"] else "",
        f"{summary.needs_decision} for a person to decide" if summary.needs_decision else "",
    ]
    return ", ".join(p for p in parts if p) + "."

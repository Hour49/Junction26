"""Which services picture is the plan's floor (docs/specs/backend/services-follow.md, SFP-9..):
the sheets' own words first (the floor their titles and file names name, their sheet numbers),
then geometry (the sheet laid over the plan by a register). Pure; every pairing says why in plain
words, and every refusal says why not, so a wrong pairing is visible and can be refused.
"""

import re
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath

from app.core.services.model import Affine, Pairing
from app.core.services.picture_follow import Sheet, align

# A register lays a sheet over the plan: the map and how it was found, or why it cannot. The
# wall-line fit (rotation and scale, Madalina's side) plugs in here.
Register = Callable[[Sheet, Sheet], tuple[Affine, str] | str]

SCORE_BOTH, SCORE_PAGE, SCORE_GEOMETRY = 0.9, 0.7, 0.6
SAME_SIZE = 0.02  # two sheets this close in metres are taken to share their frame

# Floor words -> one key per floor ("0" ground, "1" first upper, "-1" basement, "roof").
_FLOORS: tuple[tuple[str, str], ...] = (
    (r"\b(?:eg|erdgeschoss|gf|ground(?:\s+floor)?)\b", "0"),
    (r"\b(?:dg|dachgeschoss|roof|attic)\b", "roof"),
    (r"\b(?:ug|kg|untergeschoss|kellergeschoss|keller|basement|cellar)\b", "-1"),
    (r"\bb(\d)\b", "-{}"),
    (r"\b(\d{1,2})\s*\.?\s*(?:og|obergeschoss|krs|kerros|etage|stock)\b", "{}"),
    (r"\b(?:og|floor|level|storey|story|etage|niveau|lvl|l|krs|kerros)\s*[-.]?\s*(\d{1,2})\b", "{}"),
    (r"\b(\d{1,2})(?:st|nd|rd|th)\s+floor\b", "{}"),
)
_NUMBER = re.compile(r"\b([A-Z]{1,3})[-_ .]?(\d{3,4})\b")


def by_room_names(plan: Sheet, sheet: Sheet) -> tuple[Affine, str] | str:
    """The default register: the room-name shift (`align`); floors are `pair`'s business."""
    place = align(plan.model_copy(update={"storey": None}), sheet.model_copy(update={"storey": None}))
    if isinstance(place, str):
        return place
    n = len(_printed_once(plan) & _printed_once(sheet))
    return place, f"laid over by the {n} room names both sheets print"


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
            out.append(
                f"another {lost[0]} picture was taken: {_shown(candidates[best[lost[0]]])}"
            )
            continue
        others = [
            _shown(other)
            for k, (other, theirs) in enumerate(zip(candidates, found, strict=True))
            if k != i
            and not isinstance(theirs, str)
            and set(other.disciplines) & {d for d in sheet.disciplines if best[d] == i}
        ]
        if others:
            got = got.model_copy(update={"reason": f"{got.reason} (also offered: {', '.join(others)})"})
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
        how = f"laid over page to page: both sheets are {w:.1f} × {h:.1f} m"
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

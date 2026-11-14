"""A plan-edit proposal checked against a country's rule pack, before and after the change, and the
AI's reading of the law checked against the clause's own numbers (spec plan-edit-law-check, LC-1
to LC-5, LC-9, LC-9b).

Pure: the after drawing is a copy of the drawing with the proposal's rooms and doors swapped in,
and both go through 0009's `check_drawing` unchanged, so no verdict is stronger than the engine
gives (a fail stands only on a printed area or a drawn vector outline at a real scale).
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from app.core.checks.check import MEASURED, check_drawing, holds
from app.core.checks.model import (
    COMPARISON_TEXT,
    CheckResult,
    CheckUnit,
    Clause,
    CodeRule,
    RuleCheck,
    RulePack,
    RuleStatus,
)
from app.core.drawing.model import Drawing, Room, RoomType
from app.core.laws.model import ClauseView
from app.core.model import Frozen
from app.core.pipeline.model import Route

if TYPE_CHECKING:  # plan_edit.model imports this module (Proposal.law): no import back at runtime
    from app.core.plan_edit.model import Proposal, RoomChange

Change = Literal["newly_fails", "now_passes", "newly_cannot_tell", "still_fails", "still_passes"]
ORDER: tuple[Change, ...] = (
    "newly_fails", "still_fails", "newly_cannot_tell", "now_passes", "still_passes"
)  # fmt: skip
Verdict = Literal["would_not_meet", "meets", "check"]
LimitComparison = Literal[">=", ">", "<=", "<", "="]
NOTE = (
    "A pre-check of {n} rules from {pack_name}, not a permit check. Structure, fire safety, "
    "escape routes and services are not checked."
)
# A new room's type from its name. shortcut: the readers' own tables are adapters
# (vector_pdf/ifc_render.py ROOM_WORDS, swiss.py ROOM_TYPES); move one to core if they drift.
ROOM_WORDS: tuple[tuple[RoomType, str], ...] = (
    ("wc", r"\bwc\b|toilet|aseo|\bvs\b|\bwc-"),
    ("sauna", r"sauna|\bsaun\b"),
    ("bathroom", r"\bbad\b|bath|bagno|\bbain\b|kylpy|pesuhuone|\bkph\b|\bph\b|dusche|douche"),
    ("storage", r"storage|abstell|\breduit|réduit|ripostiglio|varasto|\bvar\b|lager|cantina|cave"),
    ("bedroom", r"bedroom|schlaf|\bzimmer\b|stanza|camera|chambre|\bpièce\b|makuu|\bmh\b"),
    ("kitchen", r"kitchen|küche|kuche|cucina|cuisine|keitti|\bk\b|\bkt\b"),
    ("living", r"living|wohn|soggiorno|séjour|olohuone|\boh\b"),
    ("hall", r"\bhall|corridor|korridor|flur|corridoio|couloir|eteinen|käytävä|\bet\b"),
    ("balcony", r"balcon|balkon|parveke|terrace|terrass|loggia"),
)
# The change in words for the law search (LC-9): English, then the packs' languages (de, fi).
QUERY_WORDS: dict[str, str] = {
    "bedroom": "bedroom habitable room area minimum window Schlafzimmer Wohnraum Fläche "
    "makuuhuone asuinhuone",
    "living": "living room habitable room area minimum window Wohnzimmer Wohnraum Fläche "
    "olohuone asuinhuone",
    "kitchen": "kitchen area Küche keittiö",
    "bathroom": "bathroom wet room waterproofing sanitary Bad Nasszelle märkätila kylpyhuone",
    "wc": "WC toilet wet room sanitary Toilette märkätila",
    "sauna": "sauna wet room waterproofing märkätila",
    "storage": "storage room area Abstellraum varasto",
    "hall": "corridor width Korridor käytävä",
    "wall": "remove wall",
    "door": "door clear width Tür Türbreite ovi oviaukko",
}
WET: frozenset[str] = frozenset({"bathroom", "wc", "sauna"})
# A note's value in the clause's unit, back to the tools' metres
TO_TOOL_UNIT: dict[str, float] = {"mm": 0.001, "cm": 0.01}
TOLERANCE = 0.01  # values to the cm or the hundredth of a m2, as the tools round them


class Before(Frozen):
    status: RuleStatus  # not_applicable for a room the proposal makes
    value: float | None


class After(Frozen):
    status: RuleStatus
    value: float | None
    why: str | None


class Finding(Frozen):
    """One rule on one room or door whose result the proposal changes, or that still fails on a
    room or door it touches (LC-3). `ev`: the chat's evidence id, set by the agent loop."""

    ev: str | None = None
    rule_id: str
    title: str
    change: Change
    subject: str  # the room or door as the check names it ("Stanza 1.02")
    subject_ref: str | None  # its id: a room, a RoomChange or a door element; None: the sheet
    before: Before
    after: After
    comparison_text: str
    limit: float
    unit: CheckUnit
    clause: Clause


class LawNote(Frozen):
    """The model's reading of one law clause against the proposal (LC-9a), before the server
    checks it."""

    clause_id: str
    subject: str
    value: float | None = None  # None only with verdict check
    comparison: LimitComparison
    limit: float
    unit: str
    verdict: Verdict


class AiFinding(LawNote):
    """A law note the server kept (LC-9b): its verdict recomputed, its clause filled in."""

    ref: str
    law: str  # the law's title in English
    url: str
    quote: str
    quote_en: str | None
    basis: Literal["ai_reading"] = "ai_reading"


class LawCheck(Frozen):
    pack: str
    pack_name: str
    fail_means: str | None
    findings: tuple[Finding, ...]
    unchanged: int
    related: tuple[ClauseView, ...] = ()
    ai_findings: tuple[AiFinding, ...] = ()
    # The rooms and doors the proposal changes, by label and id: a law note's subject is one
    subjects: tuple[str, ...] = ()
    # The numbers of each changed room and new door, by its id and its label: its area after (on
    # the drawing's basis and as the geometry measures it), a door's width. A law note's value
    # must be one of its own subject's (LC-9b)
    subject_values: dict[str, list[float]] = Field(default_factory=dict[str, list[float]])
    note: str

    def for_model(self) -> dict[str, Any]:
        """LC-7: what the model reads, without the clauses' quotes."""
        return {
            "pack": self.pack,
            "pack_name": self.pack_name,
            "findings": [
                {
                    **finding.model_dump(exclude={"clause", "subject_ref"}),
                    "clause_ref": finding.clause.ref,
                }
                for finding in self.findings
            ],
            "unchanged": self.unchanged,
            "related": [
                {
                    "id": clause.id,
                    "ref": clause.ref,
                    "law": clause.law_title_en,
                    "summary": clause.summary_en,
                    "limits": [limit.model_dump() for limit in clause.limits],
                }
                for clause in self.related
            ],
            "ai_findings": [
                finding.model_dump(exclude={"quote", "quote_en"}) for finding in self.ai_findings
            ],
            "subjects": list(self.subjects),
            "subject_values": self.subject_values,
            "note": self.note,
        }


def check_proposal(
    drawing: Drawing,
    proposal: Proposal,
    pack: RulePack,
    route: Route | None,
    related: Sequence[ClauseView] = (),
) -> LawCheck:
    """The rule pack's results on the drawing as read and as the proposal would leave it, and
    what differs (LC-1..LC-5). `related`: the law clauses the caller found for the change."""
    after, origin = _after(drawing, proposal, route)
    before_checks = check_drawing(drawing, pack, route)
    after_checks = check_drawing(after, pack, route)
    touched = {
        *(change.id for change in proposal.rooms),
        *(rid for change in proposal.rooms for rid in change.was),
        *(item.id for item in (*proposal.removed, *proposal.added)),
        *origin,
    }
    rules = {rule.id: rule for rule in pack.rules}
    findings: list[Finding] = []
    unchanged = 0
    for was, now in zip(before_checks, after_checks, strict=True):
        rule = rules[now.rule_id]
        earlier = {result.subject.ref: result for result in was.results}
        for result in now.results:
            ref = result.subject.ref
            source = origin.get(ref or "", (ref, None))
            old = earlier.get(source[0]) if source[0] is not None else None
            before = Before(
                status=old.status if old else "not_applicable", value=old.value if old else None
            )
            change = _change(before.status, result.status, ref in touched)
            if change is None:
                unchanged += 1
                continue
            findings.append(_finding(rule, result, source[1] or ref, before, change))
        if not now.results and now.status != was.status:  # the rule as a whole (0009's S1)
            findings += _rule_finding(rule, was, now, proposal, origin)
    findings.sort(key=lambda finding: ORDER.index(finding.change))
    return LawCheck(
        pack=pack.id,
        pack_name=pack.name,
        fail_means=pack.fail_means,
        findings=tuple(findings),
        unchanged=unchanged,
        related=tuple(sorted(related, key=lambda clause: not _checkable(clause))),
        subjects=_subjects(drawing, proposal),
        subject_values=_subject_values(drawing, after, origin, proposal),
        note=NOTE.format(n=len(pack.rules), pack_name=pack.name),
    )


def related_query(drawing: Drawing, proposal: Proposal) -> str:
    """The change in words for `LawIndex.search` (LC-9): the changed rooms' types, a removed
    wall, a new door, in English, German and Finnish."""
    by_id = {room.id: room for room in drawing.rooms}
    kinds: list[str] = []
    for change in proposal.rooms:
        if change.id in by_id or change.area_before_m2 > 0:  # shrunk or merged, as _after
            kinds += [by_id[rid].type for rid in (change.id, *change.was) if rid in by_id]
        else:
            kinds.append(_type_of(change.label))
    if any(item.id not in _door_ids(drawing) for item in proposal.removed):
        kinds.append("wall")
    if any("door" in item.label.lower() for item in proposal.added):
        kinds.append("door")
    words = " ".join(QUERY_WORDS.get(kind, "") for kind in dict.fromkeys(kinds))
    return " ".join(dict.fromkeys(words.split()))


# A limit's `what` that measures a whole (a dwelling, a building, a sum), not one room or door
# (lawai-2). A wrong `check` is safe, a wrong `would_not_meet` is not, so a bare scope word is
# enough; the words stem-match, as Finnish and German build compounds on them.
AGGREGATE = re.compile(
    r"dwelling|apartment|\bflats?\b|\bunits?\b(?! area)|building|storey|\bhouses?\b|\btotal\b"
    r"|asunto|asuinhuoneisto|rakennus|yhteensä|wohnung|gebäude|insgesamt|logement|bâtiment",
    re.IGNORECASE,
)
# A scope word that only says where the element is ("kitchen floor area in one-room dwellings",
# "stairwell-to-dwelling doors", "room floor area (not single-family houses)", an exit's width "with
# lift in existing building"): cut before AGGREGATE looks.
# shortcut: English only (both corpora's `what`s are English); add DE/FI/FR if a corpus gets them.
WHERE = re.compile(
    r"\b(?:in|inside|within)\s+(?:an?\s+|the\s+)?(?:[\w-]+\s+)?"
    r"(?:dwellings?|houses?|apartments?|flats?)\b"
    r"(?:\s+(?:or|and)\s+[\w-]+\s+(?:units?|dwellings?))?|-to-dwelling\b|\(not [\w\s-]*houses?\)"
    r"|\bdwelling exit\b|\bwith lift in existing building\b|\bor small residential building\b",
    re.IGNORECASE,
)


def _aggregate(what: str) -> bool:
    return AGGREGATE.search(WHERE.sub(" ", what)) is not None


def validate_law_note(
    note: LawNote,
    law_check: LawCheck,
    clauses: Mapping[str, ClauseView],
    tool_values: Collection[float],
) -> AiFinding | None:
    """LC-9b: the note as the server keeps it, or None when it does not stand. `clauses`: every
    clause of this turn by id. A value must be one of its subject's own (`law_check.
    subject_values`), so another room's area cannot stand for it; `tool_values` (the turn's
    numbers, untied to a subject) is not read and stays for the posted signature. The verdict is
    recomputed from the numbers, never taken from the model, and is `check` for a limit on a
    whole (`_aggregate`): the subject is one room or door."""
    clause = clauses.get(note.clause_id)
    if clause is None:
        return None
    limit = next(
        (
            limit
            for limit in clause.limits
            if limit.comparison == note.comparison
            and limit.unit == note.unit
            and math.isclose(limit.value, note.limit)
        ),
        None,
    )
    if limit is None:
        return None
    if not _subject_known(note.subject, law_check.subjects):
        return None
    if _repeats(clause, law_check.findings):
        return None
    if note.value is None:
        if note.verdict != "check":
            return None
        verdict: Verdict = "check"
    else:
        known = _values_of(note.subject, law_check.subject_values)
        scale = TO_TOOL_UNIT.get(note.unit, 1.0)
        if not any(math.isclose(note.value * scale, value, abs_tol=TOLERANCE) for value in known):
            return None
        verdict = "meets" if _holds(note.value, note.comparison, note.limit) else "would_not_meet"
        if _aggregate(limit.what):  # lawai-2: one room is not the dwelling's whole
            verdict = "check"
        elif note.verdict != verdict:
            return None
    return AiFinding(
        **note.model_dump(exclude={"verdict"}),
        verdict=verdict,
        ref=clause.ref,
        law=clause.law_title_en,
        url=clause.url,
        quote=clause.text,
        quote_en=clause.text_en,
    )


def _after(
    drawing: Drawing, proposal: Proposal, route: Route | None
) -> tuple[Drawing, dict[str, tuple[str | None, str]]]:
    """The drawing as the proposal leaves it, and per after room id that is not a drawing room's
    own: (the drawing room it is checked against, None for a new one; the RoomChange id).

    A RoomChange with a drawing room's id replaces it (shrunk); one with another id and an area
    before is a merge of its `was` rooms, added once per type they had (LC-2); one with no area
    before is a new room, typed by its name. Every `was` room goes. Ring and box stay page
    fractions, the drawing's own positions. A door in `removed` is dropped; a wall strip is no
    element (LC-1)."""
    by_id = {room.id: room for room in drawing.rooms}
    gone = {rid for change in proposal.rooms for rid in (change.id, *change.was)}
    added: list[Room] = []
    origin: dict[str, tuple[str | None, str]] = {}
    for change in proposal.rooms:
        if change.area_after_m2 <= 0:  # all of it taken by the new room
            continue
        if change.id in by_id:
            added.append(_room(by_id[change.id], change, [by_id[change.id]], change.id))
        elif change.area_before_m2 > 0 and (
            sources := [by_id[r] for r in change.was if r in by_id]
        ):
            kinds = {room.type: room for room in sources}
            for kind, first in kinds.items():
                rid = change.id if len(kinds) == 1 else f"{change.id}:{kind}"
                shown = first.model_copy(update={"label": change.label, "attrs": {}})
                added.append(_room(shown, change, sources, rid))
                origin[rid] = (first.id, change.id)
        else:
            exact = route in MEASURED and drawing.scale.status == "scaled"
            template = Room(id=change.id, type=_type_of(change.label), label=change.label,
                            page=proposal.page, box=(0, 0, 1, 1))  # fmt: skip
            room = _room(template, change, [], change.id)
            added.append(room.model_copy(update={"area_status": None if exact else "estimated"}))
            origin[change.id] = (None, change.id)
    removed = {item.id for item in proposal.removed}
    return drawing.model_copy(
        update={
            "rooms": (*(room for room in drawing.rooms if room.id not in gone), *added),
            "elements": tuple(
                e for e in drawing.elements if not (e.class_ == "door" and e.id in removed)
            ),
        }
    ), origin


def _room(source: Room, change: RoomChange, was: Sequence[Room], rid: str) -> Room:
    """`source` with the change's outline and its area on the drawing's own basis (LC-4): the
    rooms' areas times the share the geometry kept, so a printed area and a measured one never
    make a false change."""
    ring = tuple((min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)) for x, y in change.polygon)
    xs, ys = [x for x, _ in ring], [y for _, y in ring]
    areas = [room.area_m2 for room in was]
    if was and change.area_before_m2 > 0 and all(area is not None for area in areas):
        area = sum(a for a in areas if a is not None) * change.area_after_m2 / change.area_before_m2
    else:
        area = change.area_after_m2
    estimated = [room for room in was if room.area_status == "estimated"]
    spreads = [room.area_uncertainty for room in estimated]
    known = [spread for spread in spreads if spread is not None]
    return source.model_copy(
        update={
            "id": rid,
            "polygon": ring if len(ring) >= 3 else None,
            "box": (min(xs), min(ys), max(xs), max(ys)) if ring else source.box,
            "area_m2": round(area, 3),
            "area_source": "geometry_x_scale",
            "area_status": "estimated" if estimated else (was[0].area_status if was else None),
            "area_uncertainty": max(known) if known and len(known) == len(spreads) else None,
        }
    )


def _change(before: RuleStatus, after: RuleStatus, touched: bool) -> Change | None:
    """How a result moved; a fail or a pass that stays is shown only on what the proposal
    touches."""
    if after == "fail":
        return "newly_fails" if before != "fail" else "still_fails" if touched else None
    if after == before:
        return "still_passes" if after == "pass" and touched else None
    if after == "cannot_tell":
        return "newly_cannot_tell"
    return "now_passes" if after == "pass" else None


def _finding(
    rule: CodeRule, result: CheckResult, ref: str | None, before: Before, change: Change
) -> Finding:
    return Finding(
        rule_id=rule.id,
        title=rule.title,
        change=change,
        subject=result.subject.label,
        subject_ref=ref,
        before=before,
        after=After(status=result.status, value=result.value, why=result.why),
        comparison_text=result.comparison_text,
        limit=result.limit,
        unit=result.unit,
        clause=rule.clause,
    )


def _rule_finding(
    rule: CodeRule,
    was: RuleCheck,
    now: RuleCheck,
    proposal: Proposal,
    origin: Mapping[str, tuple[str | None, str]],
) -> list[Finding]:
    """A rule with no result after the change whose status still changed: a new room of a kind
    we could not tell makes it cannot tell (0009's S1)."""
    change = _change(was.status, now.status, True)
    if change is None:
        return []
    new = [c for c in proposal.rooms if c.id in origin and origin[c.id][0] is None]
    return [
        Finding(
            rule_id=rule.id,
            title=rule.title,
            change=change,
            subject=", ".join(c.label for c in new) or "the plan",
            subject_ref=new[0].id if len(new) == 1 else None,
            before=Before(status=was.status, value=None),
            after=After(status=now.status, value=None, why=now.why),
            comparison_text=COMPARISON_TEXT[rule.comparison],
            limit=rule.limit,
            unit=rule.unit,
            clause=rule.clause,
        )
    ]


def _type_of(name: str) -> RoomType:
    low = name.lower()
    for kind, pattern in ROOM_WORDS:
        if re.search(pattern, low):
            return kind
    return "other"


def _door_ids(drawing: Drawing) -> set[str]:
    return {element.id for element in drawing.elements if element.class_ == "door"}


def _checkable(clause: ClauseView) -> bool:
    return clause.drawing_checkable and bool(clause.limits)


def _subjects(drawing: Drawing, proposal: Proposal) -> tuple[str, ...]:
    by_id = {room.id: room for room in drawing.rooms}
    names: list[str] = []
    for change in proposal.rooms:
        names += [change.label, change.id]
        for rid in change.was:
            if rid in by_id:
                names += [by_id[rid].label or rid, rid]
    for item in (*proposal.removed, *proposal.added):
        names += [item.id]
    return tuple(dict.fromkeys(name for name in names if name))


def _subject_known(subject: str, subjects: Sequence[str]) -> bool:
    """The note names a room or door the proposal changes, by its label or id as a whole word."""
    text = subject.lower()
    return any(re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", text) for name in subjects)


def _repeats(clause: ClauseView, findings: Sequence[Finding]) -> bool:
    """The clause is one a rule-pack finding already cites: its law number and its ref."""
    ref = rf"(?<!\w){re.escape(clause.ref.rstrip('.'))}(?!\w)"
    return any(
        clause.law_number in finding.clause.ref and re.search(ref, finding.clause.ref)
        for finding in findings
    )


def _subject_values(
    drawing: Drawing,
    after: Drawing,
    origin: Mapping[str, tuple[str | None, str]],
    proposal: Proposal,
) -> dict[str, list[float]]:
    by_change = {origin.get(room.id, (None, room.id))[1]: room.area_m2 for room in after.rooms}
    values: dict[str, list[float]] = {}
    for change in proposal.rooms:
        found = [v for v in (by_change.get(change.id), change.area_after_m2) if v is not None]
        for key in (change.id, change.label):
            values[key] = list(dict.fromkeys([*values.get(key, []), *found]))
    page = next((p for p in drawing.pages if p.page == proposal.page), None)
    m = drawing.scale.m_per_unit
    for item in proposal.added:
        if "door" in item.label.lower() and page is not None and m is not None and item.polygon:
            xs, ys = [x for x, _ in item.polygon], [y for _, y in item.polygon]
            long_side = max((max(xs) - min(xs)) * page.width, (max(ys) - min(ys)) * page.height)
            values[item.id] = [round(long_side * m, 3)]
    return values


def _values_of(subject: str, values: Mapping[str, Sequence[float]]) -> Sequence[float]:
    """The numbers of the most specific changed room or door the subject names ("Stanza 1.02"
    over "Stanza"); none when it names none."""
    text = subject.lower()
    named = [key for key in values if re.search(rf"(?<!\w){re.escape(key.lower())}(?!\w)", text)]
    return values[max(named, key=len)] if named else ()


def _holds(value: float, comparison: LimitComparison, limit: float) -> bool:
    if comparison == "=":
        return math.isclose(value, limit)
    return holds(value, comparison, limit)

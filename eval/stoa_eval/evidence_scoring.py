"""Evidence hit rate on golden v2 Part 2: does an answer's evidence point at the thing it counted
or measured? (golden-8 brief; Bogdan's key values put transparency first.) Not in the headline.

A numeric question on a file whose Part 1 gold has truth `elements` gets a subject from its wording
(`subject_of`): an element class, a room type, the rooms with a label, number or name, an
apartment's indoor rooms (no outdoor space or shaft, as the swiss apartment areas sum), every
numbered indoor room, every room, or the plans. The subject picks the gold items the answer is about
(`targets`), restricted to an enlarged plan when the question names one. On golden v2 the targets
agree with the gold answer on every count question and every room-area question
(tests/test_real_data.py).

A box hits a gold item when it is on the question's file and the item's page and its centre lies in
the item's gold box (edges included).
- precision: the share of the answer's evidence boxes that hit one of its targets.
- recall: the share of the targets that some evidence box hits.
Both pool boxes and items over the scored questions. A question without evidence (or without an
answer line) adds its targets to recall and nothing to precision.

Why the centre in the gold box, and not IoU >= 0.5 or the gold polygon:
- evidence is there to show a person where; a box whose centre lies on the item points at it,
  whatever its extent (a detector's door box with its swing against the gold leaf).
- IoU on thin items (walls and windows are about 1% of the page tall) fails on sub-percent offsets,
  which measures box tightness, not pointing.
- one box gives one point: a box around the whole plan hits at most the item under its centre, so
  recall can't be bought with big boxes.
- gold polygons are one drawn fragment on IFC sheets (the box covers the object: 738 of 765 IFC
  door boxes have their centre outside the polygon), and the box centre of an L-shaped room can lie
  outside its polygon, so boxes are the region on both sides.

Not scored, counted per reason: free-text questions, files whose gold has truth `counts` or
`tables` (no item boxes), apartment counts (an apartment has no box), questions about a whole IFC
model (the sheet shows one storey), and wordings the rules don't know.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from .extraction import Extraction, Room
from .families import quoted_names, template_of
from .models import FREE_TEXT_TYPES, Answer, Evidence, GoldenItem
from .scoring import Tally

RoomRule = Literal["all", "label", "number", "name", "apartment", "numbered_indoor"]


@dataclass(frozen=True)
class Subject:
    """What a question counts or measures. `family` names it in the report."""

    family: str
    classes: frozenset[str] = frozenset()
    room_types: frozenset[str] = frozenset()
    rooms: RoomRule | None = None
    value: str | None = None  # the label, number, name or apartment letter `rooms` needs
    plans: bool = False
    plan: str | None = None  # an enlarged plan's code ("3C"): only that gold plan's items


class Target(NamedTuple):
    id: str
    page: int
    box: tuple[float, float, float, float]


# Matched against the casefolded template (quoted names and numbers masked), in this order. The
# sink, shower and bathtub rules come before the room types because CubiCasa's sink question says
# "kitchen and bathroom combined"; the bathroom room rule comes before the WC room rule because the
# bathroom question says "not counting separate WC rooms".
_MODEL = re.compile(r"\b(?:model|modell|modelo|modelu|mudelis|modello|modellen|modelul)\b")
_APARTMENTS = re.compile(r"apartments|wohnungen|appartements|appartamenti|lejligheder|mieszka")
_STOREYS = re.compile(r"floors \(storeys\)|kerrosta\b")
_LABELLED = re.compile(r"labelled|bezeichnung|désign|denominazione|denominati")
_NUMBERED = re.compile(r"numbered|nummerierten|numérotées|numerati")
_ALL_ROOMS = re.compile(
    r"all rooms|aller räume|alle rum\b|todos los locales|wszystkich pomieszcze|kõigi ruumide"
    r"|alle ruimtes|tutti i locali"
)
_ONE_ROOM = re.compile(
    r"\broom\b|\braums\b|\brummet\b|pomieszczenia\b|\bruumi\b|\blocal\b|\bruimte\b"
)
_SHOWER = re.compile(r"shower|dusche|douche|docce|doccia|suihku")
_BATHTUB = re.compile(r"bathtub|badewanne|baignoire|vasche da bagno|vasca da bagno|kylpyamme")
_FIXTURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("sink", re.compile(r"\bsinks?\b|wash ?basins?|lavabo|lavabi|lavator|tiskiallas")),
    ("toilet", re.compile(r"toilet bowl|wc seat|wc-istui|toilets \(wc\)|\bwcs\b|\bde wc\b|quanti wc"
                      r"|water closet")),
)  # fmt: skip
_ROOM_TYPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bathroom", re.compile(r"bathrooms|kylpy- tai pesuhuone")),
    ("wc", re.compile(r"wc rooms|wc-tila")),
    ("bedroom", re.compile(r"bedroom|makuuhuone")),
    ("kitchen", re.compile(r"kitchens|keittiö")),
    ("balcony", re.compile(r"balcon|parveke")),
)
# The dataset's sauna count is the sauna stove count (all 60 v2 files with a stove; the gold types a
# sauna room on 2), so a sauna question is about the stoves.
_SAUNA = re.compile(r"\bsaunas?\b|\bsaunaa\b")
_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("door", re.compile(r"\bdoors?\b|türen|\btür\b|\bportes?\b|\bdeur|\bdøre?\b|drzwi|\bust\b|\buks"
                    r"|puertas?|\buși|\bovea\b|\bovi")),
    ("window", re.compile(r"window|ikkuna|fenster|fenêtre|finestr|\bramen\b|\braam\b|vindue|okien"
                      r"|\bokn|\baken|ventana|ferestr")),
    ("wall", re.compile(r"\bwalls?\b|\bwände\b|\bwand\b|\bmurs?\b|\bmuri\b|wanden|vægge?|ścian"
                    r"|\bseina\b|\bmuros?\b|pereți")),
    ("column", re.compile(r"column|stützen?|kolom|søjle|słup|sammas|\bposti\b|pilar|stâlpi")),
    ("stair", re.compile(r"stair|treppe|\btrap|\bscale\b|schod|treppi|escalera|scări")),
    ("beam", re.compile(r"\bbeams?\b|träger|balken|bjælke|belek|belka|\btala\b|vigas?\b|grinzi")),
    ("slab", re.compile(r"slab|decken|bodenplatte|vloer|dæk|plader|płyt|stropy|plaat|losa")),
)  # fmt: skip
_ROOMS = re.compile(r"rooms|räume|\brum\b|locales|pomieszcze|ruumi|ruimtes|locali|stanze")
_APARTMENT = re.compile(r"\b(?:apartment|wohnung|appartement|appartamento)\s+([A-Z])\b", re.I)
_ROOM_NUMBER = re.compile(r"\b(?:room|raum|pièce|locale)\s+(U?\d+(?:\.\d+)*)\s*\(", re.I)
_ENLARGED_PLAN = re.compile(r"\benlarged plan\s+(\w+)", re.I)

WHOLE_MODEL = "about the whole IFC model (the sheet shows one storey)"
APARTMENT_COUNT = "apartment count (an apartment has no box)"
UNKNOWN = "wording the subject rules don't know"


def subject_of(question: str, type_: str) -> Subject | str:
    """The question's subject, or why it has none (a reason from this module)."""
    if type_ not in ("count", "area", "length", "volume"):
        return UNKNOWN
    text = template_of(question).casefold()
    names = quoted_names(question)
    if _MODEL.search(text):
        return WHOLE_MODEL
    if type_ == "count":
        found = _count_subject(text, names)
    else:
        found = _measure_subject(question, text, names)
    plan = _ENLARGED_PLAN.search(question)
    if isinstance(found, Subject) and plan is not None:
        return replace(found, plan=plan[1])
    return found


def _count_subject(text: str, names: list[str]) -> Subject | str:
    if _APARTMENTS.search(text):
        return APARTMENT_COUNT
    if _STOREYS.search(text):
        return Subject("plan", plans=True)
    if _LABELLED.search(text) and names:
        return Subject("rooms labelled", rooms="label", value=names[0])
    for name, pattern in _FIXTURES[:1]:
        if pattern.search(text):
            return Subject(name, classes=frozenset({name}))
    shower, bathtub = bool(_SHOWER.search(text)), bool(_BATHTUB.search(text))
    if shower or bathtub:
        classes = frozenset(name for name, on in (("shower", shower), ("bathtub", bathtub)) if on)
        return Subject("+".join(sorted(classes)), classes=classes)
    for name, pattern in _FIXTURES[1:]:
        if pattern.search(text):
            return Subject(name, classes=frozenset({name}))
    if _SAUNA.search(text):
        return Subject("sauna (stove)", classes=frozenset({"sauna_stove"}))
    for room_type, pattern in _ROOM_TYPES:
        if pattern.search(text):
            return Subject(f"room:{room_type}", room_types=frozenset({room_type}))
    for name, pattern in _CLASSES:
        if pattern.search(text):
            return Subject(name, classes=frozenset({name}))
    if _ROOMS.search(text):
        return Subject("all rooms", rooms="all")
    return UNKNOWN


def _measure_subject(question: str, text: str, names: list[str]) -> Subject | str:
    apartment = _APARTMENT.search(question)
    if apartment:
        return Subject("apartment rooms", rooms="apartment", value=apartment[1].upper())
    if _NUMBERED.search(text):
        return Subject("numbered indoor rooms", rooms="numbered_indoor")
    if _LABELLED.search(text) and names:
        return Subject("rooms labelled", rooms="label", value=names[0])
    number = _ROOM_NUMBER.search(question)
    if number:
        return Subject("room by number", rooms="number", value=number[1])
    if _ALL_ROOMS.search(text):
        return Subject("all rooms", rooms="all")
    if _ONE_ROOM.search(text) and names:
        return Subject("room by name", rooms="name", value=names[0])
    for name, pattern in _CLASSES:
        if name in ("wall", "slab") and pattern.search(text):
            return Subject(name, classes=frozenset({name}))
    return UNKNOWN


def _norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _room_names(attrs: Mapping[str, object], label: str | None) -> set[str]:
    """Every way a question may name a room: its label, IFC name and long name, and
    "<long name> (<name>)" as the IFC questions write it."""
    name, long_name = attrs.get("ifc_name"), attrs.get("ifc_long_name")
    found = {str(value) for value in (label, name, long_name) if value}
    if name and long_name:
        found.add(f"{long_name} ({name})")
    return {_norm(value) for value in found}


def _room_fits(subject: Subject, room: Room, apartments: set[str]) -> bool:
    number = room.attrs.get("number")
    value = _norm(subject.value or "")
    match subject.rooms:
        case None:
            return room.type in subject.room_types
        case "all":
            return True
        case "label":
            return room.label is not None and _norm(room.label) == value
        case "number":
            return number is not None and str(number) == subject.value
        case "name":
            return value in _room_names(room.attrs, room.label)
        case "apartment":
            return room.apartment in apartments and not room.outdoor and room.type != "shaft"
        case "numbered_indoor":
            return number not in (None, "") and not room.outdoor


def plan_ids(gold: Extraction, code: str) -> set[str]:
    """The gold plans an enlarged plan's code names: id `<code>` or `p<code>`, any case."""
    code = code.casefold()
    return {plan.id for plan in gold.plans if plan.id.casefold() in (code, f"p{code}")}


def targets(subject: Subject, gold: Extraction) -> list[Target]:
    """The gold items the subject picks on this file."""
    if subject.plans:
        picked = [Target(plan.id, plan.page, plan.box) for plan in gold.plans]
    elif subject.classes:
        picked = [
            Target(element.id, element.page, element.box)
            for element in gold.elements
            if element.class_ in subject.classes
        ]
    else:
        apartments = {a.id for a in gold.apartments if (a.label or "").upper() == subject.value}
        picked = [
            Target(room.id, room.page, room.box)
            for room in gold.rooms
            if _room_fits(subject, room, apartments)
        ]
    if subject.plan is None:
        return picked
    plans = plan_ids(gold, subject.plan)
    if subject.plans:
        return [target for target in picked if target.id in plans]
    located = {e.id: e.plan for e in gold.elements} | {r.id: r.plan for r in gold.rooms}
    return [target for target in picked if located.get(target.id) in plans]


def hits(box: Evidence, file: str, target: Target) -> bool:
    """The evidence box is on the target's file and page and its centre lies in the target's box."""
    if box.file != file or box.page != target.page:
        return False
    x, y = (box.box[0] + box.box[2]) / 2, (box.box[1] + box.box[3]) / 2
    x0, y0, x1, y1 = target.box
    return x0 <= x <= x1 and y0 <= y <= y1


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    source: str
    family: str
    boxes: int
    boxes_hit: int
    boxes_off_file: int = Field(description="evidence boxes on another file than the question's")
    targets: int
    targets_hit: int


class EvidenceGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: int
    with_evidence: int
    precision: Tally = Field(description="n boxes, correct = boxes that hit a target")
    recall: Tally = Field(description="n gold items, correct = items some box hits")


class EvidenceScore(BaseModel):
    """Evidence hit rate on the golden questions; not in the headline."""

    model_config = ConfigDict(extra="forbid")

    rule: str = Field(description="the hit test, in words")
    overall: EvidenceGroup
    by_source: dict[str, EvidenceGroup]
    by_source_family: dict[str, EvidenceGroup]
    not_scored: dict[str, int] = Field(description="reason -> golden questions")
    items: list[EvidenceItem]


RULE = "box centre inside the gold item's box, same file and page"


def _tally(correct: int, n: int) -> Tally:
    return Tally(n=n, correct=correct, accuracy=correct / n if n else None)


def _group(items: Sequence[EvidenceItem]) -> EvidenceGroup:
    return EvidenceGroup(
        questions=len(items),
        with_evidence=sum(item.boxes > 0 for item in items),
        precision=_tally(sum(i.boxes_hit for i in items), sum(i.boxes for i in items)),
        recall=_tally(sum(i.targets_hit for i in items), sum(i.targets for i in items)),
    )


def scored_targets(
    item: GoldenItem, gold: Mapping[str, Extraction]
) -> tuple[Subject, list[Target]] | str:
    """The question's subject and targets, or why its evidence is not scored."""
    if item.type in FREE_TEXT_TYPES:
        return "free-text question"
    extraction = gold.get(item.path)
    if extraction is None:
        return "no Part 1 gold for the file"
    if extraction.truth != "elements":
        return f"gold truth {extraction.truth} (no item boxes)"
    subject = subject_of(item.question, item.type)
    if isinstance(subject, str):
        return subject
    if subject.plan is not None and not plan_ids(extraction, subject.plan):
        return "enlarged plan not in the gold"
    return subject, targets(subject, extraction)


def score_evidence(
    golden: Sequence[GoldenItem], answers: Mapping[int, Answer], gold: Mapping[str, Extraction]
) -> EvidenceScore:
    items: list[EvidenceItem] = []
    not_scored: Counter[str] = Counter()
    for item in golden:
        found = scored_targets(item, gold)
        if isinstance(found, str):
            not_scored[found] += 1
            continue
        subject, picked = found
        answer = answers.get(item.id)
        boxes = answer.evidence if answer else []
        items.append(
            EvidenceItem(
                id=item.id,
                source=item.source,
                family=subject.family,
                boxes=len(boxes),
                boxes_hit=sum(any(hits(box, item.path, t) for t in picked) for box in boxes),
                boxes_off_file=sum(box.file != item.path for box in boxes),
                targets=len(picked),
                targets_hit=sum(any(hits(box, item.path, t) for box in boxes) for t in picked),
            )
        )
    by_source: dict[str, list[EvidenceItem]] = {}
    by_family: dict[str, list[EvidenceItem]] = {}
    for result in items:
        by_source.setdefault(result.source, []).append(result)
        by_family.setdefault(f"{result.source}/{result.family}", []).append(result)
    return EvidenceScore(
        rule=RULE,
        overall=_group(items),
        by_source={key: _group(group) for key, group in sorted(by_source.items())},
        by_source_family={key: _group(group) for key, group in sorted(by_family.items())},
        not_scored=dict(sorted(not_scored.items())),
        items=items,
    )


def oracle_evidence(item: GoldenItem, gold: Mapping[str, Extraction]) -> list[Evidence]:
    """One box per gold item the question is about (its gold box): the oracle's evidence."""
    found = scored_targets(item, gold)
    if isinstance(found, str):
        return []
    return [Evidence(file=item.path, page=t.page, box=t.box) for t in found[1]]


def _cell(tally: Tally) -> str:
    rate = "n/a" if tally.accuracy is None else f"{tally.accuracy:.1%}"
    return f"{tally.correct}/{tally.n} {rate}"


def format_evidence(score: EvidenceScore) -> str:
    overall = score.overall
    lines = [
        f"evidence hit rate (not in the headline; {score.rule})",
        f"  overall          {overall.questions} questions, {overall.with_evidence} with boxes; "
        f"precision {_cell(overall.precision)} boxes, recall {_cell(overall.recall)} gold items",
        f"  {'source/family':<40} {'questions':>9}  {'precision':>18}  {'recall':>18}",
    ]
    for key, group in (*score.by_source.items(), *score.by_source_family.items()):
        lines.append(
            f"  {key:<40} {group.questions:>9}  {_cell(group.precision):>18}  "
            f"{_cell(group.recall):>18}"
        )
    reasons = ", ".join(f"{reason}: {n}" for reason, n in score.not_scored.items())
    lines.append(f"  not scored       {reasons}")
    return "\n".join(lines)

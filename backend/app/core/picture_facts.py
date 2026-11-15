"""Facts from a services or structural plan that is a picture (docs/specs/backend/
discipline-pictures.md): what two readers saw on the page, double-checked, as the same `FactSheet`
topics an IFC model gives (app/adapters/ifc_model/facts_mep.py), with a spot for every counted
thing. Pure: the readers are adapters behind `PictureReader` (app/core/pipeline/ports.py).

A label a reader did not look for has no fact, never a 0. A value is the first reader's that
looked for the label; a label only one reader looked for, or the two disagree on, is held: its
facts' `source` ends in ":held", and its answers are Low whatever the route's level.
"""

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence

from app.core.discipline import discipline_from_question
from app.core.drawing.model import Box
from app.core.ifc_facts import Discipline, Fact, FactSheet, Spot
from app.core.model import Frozen
from app.core.review.check import NOTHING, CheckPolicy, Disputed, Level, level_of

NO_SCALE = "no scale"  # a reader's note: the sheet has no scale, so its runs have no length
HELD = ":held"  # the end of a held fact's `source`
NO_LEGEND = ":no-legend"
LIMIT = 5  # disputed places per sheet
AGREE_SHARE = 0.9  # of the spots matched one to one, for a count to agree
RUN_TOLERANCE = 0.1  # two lengths of a run agree within this share


class LegendEntry(Frozen):
    label: str  # as printed
    group: str | None  # the legend's heading, e.g. "Heating"
    line: bool  # a line style (a run), not a symbol
    box: Box | None  # where the symbol is drawn in the legend


class Sighting(Frozen):
    label: str  # a LegendEntry.label, or the reader's own words without a legend
    spot: Spot
    score: float | None = None  # the reader's own strength; orders the disputed places


class Run(Frozen):
    label: str
    size: str | None  # printed size, e.g. "DN20", "Ø125"
    length_m: float
    spots: tuple[Spot, ...]


class PictureReading(Frozen):
    reader: str  # "vlm", "template", "paths", "mask"
    legend: tuple[LegendEntry, ...] | None  # None: no legend found
    read: tuple[str, ...] | None  # labels looked for; None: every legend label
    sightings: tuple[Sighting, ...] = ()
    runs: tuple[Run, ...] = ()
    storey: str | None = None
    notes: tuple[str, ...] = ()
    cost_usd: float = 0.0


class Checked(Frozen):
    readings: tuple[PictureReading, ...]
    agreed: dict[str, bool]  # label -> agree
    disputed: tuple[Disputed, ...]  # mark_id None, at most LIMIT, strongest first


# --- kind_of: legend words -> IFC kind --------------------------------------------------------

# kind (snake case, as facts_mep) -> the disciplines it may be, first the default, and its words
# in the dataset's languages. Matched case-blind after a word start, so compounds match their
# first part only when listed whole ("lämpöpatteri"). The first kind that matches wins: a
# "supply air valve" is an air terminal, a "radiator valve" a valve.
_KINDS: tuple[tuple[str, tuple[Discipline, ...], str], ...] = (
    (
        "air_terminal",
        ("ventilation",),
        r"supply air|exhaust air|extract air|return air|air terminal|diffuser|grille|"
        r"tuloilma|poistoilma|siirtoilma|ilmaventtiili|päätelaite|luftauslass|luftdurchlass|"
        r"zuluft|abluft|tilluft|frånluft|luftdon|toevoerlucht|afvoerlucht|luchtrooster|"
        r"diffuseur|bouche|grille d'air|diffusore|bocchetta|difusor|rejilla|õhujaotur|"
        r"sissepuhke|väljatõmbe",
    ),
    (
        "valve",
        ("plumbing", "heating", "fire"),
        r"valve|venttiili|ventil|afsluiter|klep|vanne|robinet|valvola|válvula|ventiil",
    ),
    (
        "space_heater",
        ("heating",),
        r"radiator|heizk[öo]rper|lämpöpatteri|patteri|konvektor|convector|radiateur|"
        r"radiatore|radiador|radiaator|värmeelement",
    ),
    (
        "fire_suppression_terminal",
        ("fire",),
        r"sprinkler|hydrant|hose reel|palopost|sammutusvesi|löschwasser|brandpost|"
        r"bluswater|idrante|hidrante|tuletõrje",
    ),
    (
        "alarm",
        ("fire",),
        r"alarm|siren|sounder|hälytin|palovaroitin|melder|larm|brandmelder|allarme|alarme|"
        r"häire",
    ),
    (
        "outlet",
        ("electrical",),
        r"socket|outlet|receptacle|pistorasia|steckdose|uttag|stopcontact|wandcontactdoos|"
        r"prise de courant|presa|enchufe|toma de corriente|pistikupesa",
    ),
    (
        "switching_device",
        ("electrical",),
        r"switch|kytkin|schalter|strömbrytare|brytare|schakelaar|interrupteur|interruttore|"
        r"interruptor|lüliti",
    ),
    (
        "light_fixture",
        ("electrical",),
        r"luminaire|light|lamp|valaisin|leuchte|armatur|belysning|armatuur|verlichting|"
        r"lampada|apparecchio illuminante|luminaria|valgusti",
    ),
    (
        "electric_distribution_board",
        ("electrical",),
        r"distribution board|switchboard|ryhmäkeskus|sähkökeskus|verteiler|elcentral|"
        r"gruppcentral|verdeelkast|tableau électrique|quadro elettrico|cuadro eléctrico|"
        r"jaotuskilp",
    ),
    (
        "sanitary_terminal",
        ("plumbing",),
        r"wc\b|toilet|wash ?basin|sink|shower|bath|urinal|wc-istuin|pesuallas|allas|suihku|"
        r"waschbecken|waschtisch|dusche|badewanne|tvättställ|dusch|wastafel|douche|"
        r"lavabo|lavandino|doccia|inodoro|ducha|kraanikauss|dušš",
    ),
    (
        "pipe_segment",
        ("plumbing", "heating", "fire"),
        r"pipe|putki|rohr|leitung|rör|leiding|buis|tuyau|canalisation|tubo|tubería|toru",
    ),
    (
        "duct_segment",
        ("ventilation",),
        r"duct|kanava|luftkanal|kanal|kanaal|gaine|condotto|canale|conducto|ventilatsioonitoru",
    ),
    (
        "cable_carrier_segment",
        ("electrical",),
        r"cable tray|cable ladder|kaapelihylly|kaapelihyllyt|kabeltrasse|kabelrinne|kabelstege|"
        r"kabelgoot|chemin de câbles|passerella|bandeja|kaablirenn",
    ),
    ("pump", ("plumbing", "heating", "fire"), r"pump|pumppu|pumpe|pomp|pompe|pompa|bomba"),
    ("fan", ("ventilation",), r"fan\b|puhallin|ventilator|fläkt|ventilateur|ventilatore"),
    (
        "column",
        ("structural",),
        r"column|pilari|stütze|pelare|kolom|poteau|pilastro|pilar|columna|sammas",
    ),
    ("pile", ("structural",), r"pile|paalu|pfahl|påle|paal|pieu|pilote|vai\b"),
    (
        "footing",
        ("structural",),
        r"footing|pad foundation|antura|einzelfundament|fundament|sockel|plintfundering|"
        r"poer|semelle|plinto|zapata|vundament",
    ),
)
_KIND_RES: list[tuple[str, tuple[Discipline, ...], re.Pattern[str]]] = [
    (kind, can, re.compile(rf"\b(?:{words})", re.I)) for kind, can, words in _KINDS
]


def kind_of(label: str, group: str | None) -> tuple[str, Discipline] | None:
    """The IFC kind a legend label names and that kind's discipline; None when it names none. A
    kind several disciplines draw (a valve, a pipe) takes the one its group heading, else the
    label itself, names; else its default."""
    for kind, can, pattern in _KIND_RES:
        if pattern.search(label):
            for text in (group, label):
                named = discipline_from_question(text or "")
                if named in can:
                    return kind, can[can.index(named)]
            return kind, can[0]
    return None


# A storey as a sheet's title prints it ("2ND FLOOR", "2. krs", "1. OG", "Level 3", "Kellari")
_STOREY_WORD = (
    r"floor|level|storey|story|kerros|krs|geschoss|og|ug|etg|etage|étage|vån(?:ing)?|plan|"
    r"verdieping|piso|planta|piano|korrus"
)
_TITLE_STOREY = re.compile(
    rf"\b(?:\d+\s*\.?\s*(?:st|nd|rd|th)?\s*(?:{_STOREY_WORD})|(?:{_STOREY_WORD})\s*-?\d+"
    r"|ground\s+floor|basement|kellari|pohjakerros|erdgeschoss|keller(?:geschoss)?|källare)\b",
    re.I,
)


def storey_of_title(title: str | None) -> str | None:
    """The storey a sheet's title names, as printed; None when it names none (never guessed)."""
    found = _TITLE_STOREY.search(title or "")
    return None if found is None else found[0].strip()


# --- double_check -----------------------------------------------------------------------------


def _labels(reading: PictureReading) -> set[str]:
    """What `reading` looked for (`read`, else every legend label, else what it saw)."""
    if reading.read is not None:
        return set(reading.read)
    if reading.legend is not None:
        return {entry.label for entry in reading.legend}
    return {s.label for s in reading.sightings} | {r.label for r in reading.runs}


def _centre(spot: Spot) -> tuple[float, float]:
    x0, y0, x1, y1 = spot.box
    return (x0 + x1) / 2, (y0 + y1) / 2


def _pairs(
    first: Sequence[Sighting], second: Sequence[Sighting], near: float
) -> list[tuple[int, int]]:
    """One-to-one matches (index in first, index in second), greedy by distance."""
    # shortcut: the diagonal is taken in page fractions (sqrt 2), as if the page were square;
    # upgrade when Spot carries the page size
    reach = near * math.sqrt(2)
    close = sorted(
        (math.dist(_centre(a.spot), _centre(b.spot)), i, j)
        for i, a in enumerate(first)
        for j, b in enumerate(second)
        if a.spot.page == b.spot.page
    )
    taken_a: set[int] = set()
    taken_b: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for distance, i, j in close:
        if distance <= reach and i not in taken_a and j not in taken_b:
            taken_a.add(i)
            taken_b.add(j)
            pairs.append((i, j))
    return pairs


def _place(seen: Sighting, by: str, other: str) -> Disputed:
    return Disputed(
        mark_id=None,
        page=seen.spot.page,
        box=seen.spot.box,
        why=f"{by} sees {seen.label} here, {other} sees nothing.",
        readers={by: seen.label, other: NOTHING},
    )


def double_check(
    first: PictureReading, second: PictureReading | None, near: float = 0.006
) -> Checked:
    """Two readings of one page, label by label. A label both looked for agrees when the counts
    are equal and at least 90% of the spots match one to one within `near` of the page diagonal,
    and its runs' lengths are within 10%; the unmatched spots are the disputed places. A label
    only one looked for never agrees."""
    if second is None:
        return Checked(readings=(first,), agreed=dict.fromkeys(_labels(first), False), disputed=())
    both = _labels(first) & _labels(second)
    names = (first.reader, second.reader)
    agreed = dict.fromkeys(_labels(first) ^ _labels(second), False)
    # (rank, place): reader A's unmatched spots by score, strongest first, then reader B's
    strong: list[tuple[tuple[int, float], Disputed]] = []
    for label in sorted(both):
        a = [s for s in first.sightings if s.label == label]
        b = [s for s in second.sightings if s.label == label]
        pairs = _pairs(a, b, near)
        matched_a = {i for i, _ in pairs}
        matched_b = {j for _, j in pairs}
        counts = len(a) == len(b) and len(pairs) >= AGREE_SHARE * len(a)
        long_a = sum(r.length_m for r in first.runs if r.label == label)
        long_b = sum(r.length_m for r in second.runs if r.label == label)
        runs = abs(long_a - long_b) <= RUN_TOLERANCE * max(long_a, long_b)
        agreed[label] = counts and runs
        strong += [
            ((0, -(s.score if s.score is not None else -math.inf)), _place(s, *names))
            for i, s in enumerate(a)
            if i not in matched_a
        ]
        strong += [
            ((1, -(s.score if s.score is not None else -math.inf)), _place(s, *names[::-1]))
            for j, s in enumerate(b)
            if j not in matched_b
        ]
    strong.sort(key=lambda ranked: ranked[0])
    return Checked(
        readings=(first, second),
        agreed=agreed,
        disputed=tuple(place for _, place in strong[:LIMIT]),
    )


# --- picture_facts ----------------------------------------------------------------------------


class _Unit(Frozen):
    """One label's reading as it becomes facts."""

    label: str
    kind: str | None
    group: str | None
    discipline: Discipline
    readers: tuple[str, ...]  # those that looked for it, the leading one first
    held: bool
    legend: bool  # the leading reading had a legend


def _source(readers: Iterable[str], held: bool, legend: bool) -> str:
    named = "+".join(dict.fromkeys(readers))
    return f"picture:{named}{'' if legend else NO_LEGEND}{HELD if held else ''}"


def _group_of(label: str, readings: Sequence[PictureReading]) -> tuple[str | None, bool]:
    for reading in readings:
        for entry in reading.legend or ():
            if entry.label == label:
                return entry.group, entry.line
    return None, False


def _fact(
    topic: str,
    subject: str,
    value: float,
    units: Sequence[_Unit],
    spots: Sequence[Spot],
    *,
    unit: str,
    system: str | None = None,
    discipline: Discipline | None = None,
) -> Fact:
    return Fact(
        topic=topic,
        subject=subject,
        value=round(value, 3) if unit == "m" else value,
        unit=unit,
        storey=None,  # sheet-wide; picture_facts adds the storey's copies
        system=system,
        discipline=discipline
        or Counter[Discipline](u.discipline for u in units).most_common(1)[0][0],
        source=_source(
            (r for u in units for r in u.readers),
            any(u.held for u in units),
            all(u.legend for u in units),
        ),
        spots=tuple(spots),
    )


def picture_facts(drawing: str, checked: Checked) -> FactSheet:
    """The facts of one checked page, keyed by `drawing` (the drawing id). Counts per label and
    per kind (`all`), per legend group (`category.count`); run lengths per system and per
    printed size, from readings with a scale."""
    readings = checked.readings
    facts: list[Fact] = []
    counted: list[tuple[_Unit, list[Spot]]] = []
    runs: dict[str, list[tuple[str | None, _Unit, Run]]] = defaultdict(list)  # by kind
    for label in sorted({label for r in readings for label in _labels(r)}):
        looked = [r for r in readings if label in _labels(r)]
        lead = looked[0]
        group, line = _group_of(label, readings)
        kind = kind_of(label, group)
        unit = _Unit(
            label=label,
            kind=kind and kind[0],
            group=group,
            discipline=kind[1] if kind else discipline_from_question(group or "") or "other",
            readers=tuple(r.reader for r in looked),
            held=not checked.agreed.get(label, False),
            legend=lead.legend is not None,
        )
        spots = [s.spot for s in lead.sightings if s.label == label]
        drawn = [run for run in lead.runs if run.label == label]
        if not line and not drawn and (spots or len(looked) > 1):  # a 0 only when both looked
            counted.append((unit, spots))
        if drawn and NO_SCALE not in lead.notes:
            runs[unit.kind or "symbol"] += [(group or label, unit, run) for run in drawn]
    by_kind: dict[str, list[tuple[_Unit, list[Spot]]]] = defaultdict(list)
    by_group: dict[str, list[tuple[_Unit, list[Spot]]]] = defaultdict(list)
    for unit, spots in counted:
        kind = unit.kind or "symbol"
        facts.append(_fact(f"{kind}.count", unit.label, len(spots), [unit], spots, unit="count"))
        if unit.kind:
            by_kind[kind].append((unit, spots))
        if unit.group:
            by_group[unit.group].append((unit, spots))
    for kind, found in by_kind.items():
        units = [u for u, _ in found]
        spots = [s for _, ss in found for s in ss]
        facts.append(_fact(f"{kind}.count", "all", len(spots), units, spots, unit="count"))
    for group, found in by_group.items():
        units = [u for u, _ in found]
        spots = [s for _, ss in found for s in ss]
        named = discipline_from_question(group)
        facts.append(
            _fact("category.count", group, len(spots), units, spots, unit="count", discipline=named)
        )
    for kind, found in runs.items():  # the sheet's runs of a kind, then each system's
        facts += _run_facts(kind, None, [(unit, run) for _, unit, run in found])
        for system in dict.fromkeys(system for system, _, _ in found):
            part = [(unit, run) for named, unit, run in found if named == system]
            facts += _run_facts(kind, system, part)
    if storey := next((r.storey for r in readings if r.storey), None):
        facts += [fact.model_copy(update={"storey": storey}) for fact in facts]
    ranked = Counter[Discipline](f.discipline for f in facts).most_common()
    return FactSheet(model=drawing, disciplines=[d for d, _ in ranked], facts=facts)


def _run_facts(kind: str, system: str | None, found: list[tuple[_Unit, Run]]) -> list[Fact]:
    def one(subject: str, part: list[tuple[_Unit, Run]], topic: str, sys: str | None) -> Fact:
        units = [u for u, _ in part]
        spots = [s for _, run in part for s in run.spots]
        length = sum(run.length_m for _, run in part)
        if topic == "with_length":
            return _fact(
                f"{kind}.{topic}", subject, len(part), units, spots, unit="count", system=sys
            )
        return _fact(f"{kind}.{topic}", subject, length, units, spots, unit="m", system=sys)

    out = [one("all", found, measure, system) for measure in ("length", "with_length")]
    for label in dict.fromkeys(u.label for u, _ in found):
        part = [(u, r) for u, r in found if u.label == label]
        out += [one(label, part, measure, system) for measure in ("length", "with_length")]
    for size in dict.fromkeys(r.size for _, r in found if r.size):
        part = [(u, r) for u, r in found if r.size == size]
        out.append(one(size, part, "size_length", system))
    return list(dict.fromkeys(out))


# --- levels -----------------------------------------------------------------------------------


def level_of_fact(policy: CheckPolicy, fact: Fact) -> Level | None:
    """The level of an answer read from `fact` (decision 0011, `level_of` unchanged): never sure;
    the route is the part of `source` before the colon; a held fact is held."""
    return level_of(
        policy,
        sure=False,
        route=fact.source.split(":", 1)[0],
        family=None,
        score=None,
        flags=(),
        held=fact.source.endswith(HELD),
    )

"""Answers from a file's fact sheet (app/core/ifc_facts.py): the fallback the answering core
asks when the takeoff has no key for a question, as it asks a printed schedule (answer.py).

The question is read by rules (app/core/ifc_question.py) and the answer is a text written from a
template; every number in it is a Fact's value, put in words. No model is called. The text is
generous: next to what was asked it states the totals and parts the facts give, since a reader
checks a number more easily than a missing one. An LLM that only rephrases this text would sit
after `fact_text` (out of scope: the brief keeps it deterministic).

These answers are not measured on any gold yet, so they are never sure, and their confidence
level is Low (decision 0011): `sure` stays None and the explanation says so.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from app.core.answering.model import IN_ONE_ROOM, Answer, Evidence, Question
from app.core.discipline import SYSTEM_DISCIPLINE, system_from_question
from app.core.ifc_facts import Fact, FactSheet
from app.core.ifc_question import FactQuery, parse_ifc_question, storey_number
from app.core.services.pairing import file_floors, floors_in

FACTS = "facts"  # `method` of an answer read from the fact sheet
WHY = "read from the file's fact sheet; not yet measured, so confidence is Low"
UNAVAILABLE = "This information is not available in the file"
NOT_AVAILABLE = "not available in it"  # a file that holds none of the thing asked: refused
# A picture's sheet holds facts only of what its legend lists (discipline-pictures.md Outputs)
NOT_READ = "not read on this picture"
PICTURE_ROUTES = ("picture", "vector")  # a Fact.source's route, before its colon
# A picture's run length is an estimate: what each run reader scored on held-out DigitalHub v2
# renders, within 10% of the model's length per system (32 runs per variant; .agents/exp/
# pics-runs.md, scored once at 04:34). Said under every picture length (orchestrator 05:40).
MASK_SPREAD = (
    "Estimate from the drawing's line colours, not measured: on held-out test drawings this"
    " reader's length per system was within 10% for 18 of 32 clean, 4 of 32 photographed and"
    " 0 of 32 scanned runs."
)
GRAPH_SPREAD = (
    "Estimate from the drawing's line colours, not measured: on held-out test drawings this"
    " reader's length per system was within 10% for 21 of 32 clean, 12 of 32 photographed and"
    " 0 of 32 scanned runs."
)
# Only the colour readers: `paths` reads a drawn PDF's lines exactly, and an unscored reader's
# answer is Low with a double-check anyway (review/ask.py FACTS_LEVEL).
_SPREADS = {"mask": MASK_SPREAD, "graph": GRAPH_SPREAD}
# A line style's EN 806 water codes, in the words a question uses: P-101's S_PWC is potable
# water cold, S_PWH_ potable water hot. Only for matching a picture's run styles to the asked
# system; discipline.py feeds lane routing and pairing, so it stays as it is (orchestrator 06:05)
_STYLE_CODES = (
    (re.compile(r"\bpwc\b", re.I), "cold water"),
    (re.compile(r"\bpwh\b", re.I), "hot water"),
)
# a radiator is an IfcSpaceHeater in a model too; a picture names a switch's kind as IFC does
SAME_KIND = {"heat_exchanger": "space_heater", "switch": "switching_device"}
# What a question asks about that is not a drawn thing: never refused as not read
NOT_DRAWN = frozenset({"project", "storey", "space", "system", "discipline", "port"})


class _NoRoomNamed(str):
    """An area total asked by a room word no space's name holds and no room type has ("the total
    area of the offices"): a refusal whatever the question's form, never every space's total."""


class _NoneHeld(str):
    """What a file says when it holds none of the thing asked ("No dampers found in this file
    (not available in it)."): a refusal, not an answer, so a project's answer card never opens on
    a model that lacks it under another model's count (big QA R2 services row 7)."""


class FactSource(Protocol):
    """The fact sheet of a file, by its path, whatever read it (an IFC model parsed, a sheet
    read by vision: each Fact's `source` says how), or None when nothing gives one."""

    def facts(self, file: str) -> FactSheet | None: ...


class FirstSheet:
    """Several fact sources as one: a file's sheet is the first source's that has one."""

    def __init__(self, sources: Sequence[FactSource]) -> None:
        self._sources = tuple(sources)

    def facts(self, file: str) -> FactSheet | None:
        return next((s for f in self._sources if (s := f.facts(file)) is not None), None)


def answer_from_facts(question: Question, sheet: FactSheet, latency_s: float) -> Answer | None:
    """The answer the facts give, or None when the rules can't read the question or the facts
    hold nothing for it."""
    query = parse_ifc_question(question.text)
    if query is None:
        return None
    query, facts = _kind_of_sheet(query, sheet), _Facts(sheet.facts)
    picture = bool(sheet.facts) and all(_picture(fact) for fact in sheet.facts)
    if picture:  # its systems are its runs: "each pipe system" is their length by system
        query = _per_system(query, facts)
    if query.place is not None and (picture or _counted_in_one_room(query)):
        # a picture's facts are whole-sheet counts; a model's count by type and storey, not room
        return Answer(
            id=question.id,
            answer=None,
            unit=None,
            evidence=(),
            method="refused:unsupported-question",  # answer.UNSUPPORTED_QUESTION
            cost_usd=0.0,
            latency_s=latency_s,
            abstain=True,
            explanation=IN_ONE_ROOM,  # never the sheet total for one room (big QA R1 services)
        )
    rows = _picture_rows(query, facts) if picture else None
    unread = rows is None and query.entity not in NOT_DRAWN and not facts.topics(f"{query.entity}.")
    if picture and (unread or (rows is not None and not rows.counted)):
        noun = _plural(_noun(query.entity)) if rows is None else rows.name
        return Answer(
            id=question.id,
            answer=None,
            unit=None,
            evidence=(),
            method="refused:not-read",
            cost_usd=0.0,
            latency_s=latency_s,
            abstain=True,
            explanation=f"{NOT_READ}: its legend lists no {noun}",
        )
    floor = ""
    if picture and query.storey is not None and not _storeys_by_height(facts):
        floor, refused = _picture_floor(query.storey, question.file)
        if refused is not None:
            return Answer(
                id=question.id,
                answer=None,
                unit=None,
                evidence=(),
                method="refused:not-in-drawing",
                cost_usd=0.0,
                latency_s=latency_s,
                abstain=True,
                explanation=refused,
            )
        query = query.model_copy(update={"storey": None})  # the picture is that floor
    text = _written(query, facts) if rows is None else rows.text()
    if text is None:
        return None
    if isinstance(text, _NoRoomNamed) or (isinstance(text, _NoneHeld) and query.how_many):
        # "Which ... are present?" keeps its text
        return Answer(
            id=question.id,
            answer=None,
            unit=None,
            evidence=(),
            method="refused:not-in-drawing",
            cost_usd=0.0,
            latency_s=latency_s,
            abstain=True,
            explanation=str(text),
        )
    if floor:
        text = f"This picture is {floor} by its file name.\n{text}"
    asked = (
        [fact for fact in facts.read if fact.topic.startswith(f"{query.entity}.")]
        if rows is None
        else list(rows.counted)
    )
    seen = dict.fromkeys((s.page, s.box) for fact in asked for s in fact.spots)
    return Answer(
        id=question.id,
        answer=text,
        unit=None,
        evidence=tuple(Evidence(file=question.file, page=p, box=b) for p, b in seen),
        method=FACTS,
        cost_usd=0.0,
        latency_s=latency_s,
        sure=False if picture else None,  # a picture's count is never certified (decision 0011)
        explanation=WHY,
    )


# A length asked per system (big QA R2 services N1: "How long is each pipe system on P-101?" gave
# the sheet total, "each plumbing system" said "holds no systems"). Only on a picture, whose
# systems are its runs; an IFC model answers from its systems' own facts (review-737 M1)
_EACH_SYSTEM = re.compile(r"\b(?:by|per|each)\s+(?:\w+\s+)?systems?\b", re.I)


def _per_system(query: FactQuery, facts: "_Facts") -> FactQuery:
    """A picture's "how long is each (pipe|plumbing) system": its runs' length by system. With no
    runs of that kind on the sheet, the query as asked: its not-available line (review-737 S3)."""
    if "length" not in query.measures or not _EACH_SYSTEM.search(query.asked):
        return query
    if query.entity == "system":
        has = [e for e in ("pipe_segment", "duct_segment") if facts.topics(f"{e}.length")]
        entity = (
            "duct_segment"
            if query.discipline == "ventilation"
            or (query.discipline is None and has == ["duct_segment"])
            else "pipe_segment"
        )  # a duct picture asked "each system" lists its ducts (review-737 S2)
    elif query.entity in ("pipe_segment", "duct_segment"):
        entity = query.entity
    else:
        return query
    if not facts.topics(f"{entity}.length"):
        other = "duct_segment" if entity == "pipe_segment" else "pipe_segment"
        asked = query.system or query.discipline
        if asked is None or not facts.topics(f"{other}.length"):
            return query  # no runs at all: the facts' not-available line (review-737 S3)
        # none of the kind asked, others drawn: "No run on this sheet is labelled as ventilation
        # (not available); its runs by system: ..." (review-741 M1), never "holds no systems"
        return query.model_copy(update={"entity": other, "by": "system", "system": asked})
    return query.model_copy(update={"entity": entity, "by": "system"})


# A picture's legend rows a question's word names (QA big services R1, P4/P8/P9): the words in
# the dataset's languages. A picture has no PredefinedType (_KINDS below), and a symbol no IFC
# kind names is kept as `symbol` (a fire damper: picture_facts.kind_of), so the rows' own labels
# say what they are. (question word, what it is called, label words)
_BASIN = r"wash ?basin|lavator|waschtisch|waschbecken|pesuallas|tvättställ|wastafel|lavabo"
_PICTURE_ROWS: tuple[tuple[str, str, str], ...] = (
    (r"toilets?|wcs?", "toilets", r"\bwc\b|toilet|water ?closet|klosett|inodoro"),
    (r"urinals?", "urinals", r"urinal|pissoir|urinoir|orinatoio|urinario|pisuaari"),
    (r"(?:wash)?basins?|lavator", "washbasins", _BASIN),
    (
        r"sinks?",
        "sinks",
        rf"sink|\bsp(?:ü|ue)le|tiskiallas|diskbänk|gootsteen|évier|fregadero|{_BASIN}",
    ),
    (r"dampers?", "dampers", r"damper|klappe|pelti|spjäll|klep|clapet|serranda|compuerta"),
)
# A word that narrows what is asked, which the label must name too: a "fire damper"
_QUALIFIERS = {"fire": r"fire|brand|palo|feu\b|fuoco|incend|tule"}
# A fixture's mounting frame, drawn and listed as its own row of the same fixtures: "Viega Eco
# Plus-Urinal-Element" beside "Urinal UP Druckspüler" (6 and 6 for 6 urinals, P-101)
_FRAME = re.compile(r"element\b", re.I)


class _Rows:
    def __init__(self, name: str, counted: list[Fact], frames: list[Fact]) -> None:
        self.name, self.counted, self.frames = name, counted, frames

    def text(self) -> str:
        n = sum(int(fact.value) for fact in self.counted)
        lines = [f"Total {self.name}: {n}", *(f"- {f.subject}: {_num(f)}" for f in self.counted)]
        if self.frames:
            said = ", ".join(f"{f.subject}: {_num(f)}" for f in self.frames)
            lines.append(f"Not added, the mounting frames of the same fixtures: {said}")
        return "\n".join(lines)


def _picture_rows(query: FactQuery, facts: "_Facts") -> _Rows | None:
    """The legend rows of a picture whose label names what the question's word names, as a
    count; None when the word is none of _PICTURE_ROWS (the facts answer as before). A frame
    row is left out when the fixture's own row is there; no row at all is a refusal."""
    if "count" not in query.measures or query.by is not None:
        return None
    word = " ".join(query.named)
    found = next(((n, w) for q, n, w in _PICTURE_ROWS if re.fullmatch(q, word, re.I)), None)
    if found is None:
        return None
    name, label = found
    storey = None  # the sheet-wide rows; a reading's storey has its copies (picture_facts)
    if query.storey is not None and _storeys_by_height(facts):
        storey = _storey_of(query.storey, facts)
        if storey is None:
            return None  # the facts say which storeys the picture has
    narrow = [_QUALIFIERS[w] for w in query.words if w in _QUALIFIERS]
    rows = [
        fact
        for topic in (f"{query.entity}.count", "symbol.count")
        for fact in facts.by_topic.get(topic, ())
        if fact.subject != "all"
        and fact.system is None
        and fact.storey == storey
        and all(re.search(p, fact.subject, re.I) for p in (label, *narrow))
    ]
    own = [fact for fact in rows if not _FRAME.search(fact.subject)]
    named = " ".join([*(w for w in query.words if w in _QUALIFIERS), name])
    if own:
        return _Rows(named, own, [fact for fact in rows if _FRAME.search(fact.subject)])
    return _Rows(named, rows, [])


def _picture_floor(asked: str, file: str) -> tuple[str, str | None]:
    """A picture whose reading names no floor, asked about `asked`: the floor its file name
    names, as pairing reads it ("H-101 E00 heating.png" is E00, the ground floor; the sheet
    number H-101 is no floor), and why it is refused when that is not the floor asked or no
    floor is named (live 2026-11-15: "No storey 'ground floor' ... 0 storeys: none")."""
    mine, wanted = file_floors(file), floors_in(asked)
    if not mine:
        return (
            "",
            f"this picture's floor is not stated (not in its reading or its file name), so {asked}"
            " cannot be told",
        )
    word = " / ".join(dict.fromkeys(mine.values()))
    if len(mine) == 1 and set(wanted) == set(mine):
        return word, None
    if not wanted:
        return (
            "",
            f"'{asked}' names no floor a picture can be matched to; this picture is {word} by its"
            " file name",
        )
    return "", f"this picture is {word} by its file name, not {asked}"


def _picture(fact: Fact) -> bool:
    return fact.source.split(":", 1)[0] in PICTURE_ROUTES


def _kind_of_sheet(query: FactQuery, sheet: FactSheet) -> FactQuery:
    """The query about the kind the sheet writes when it has none of the kind asked
    (radiators: heat exchangers in the question's words, space heaters in a model's)."""
    same = SAME_KIND.get(query.entity)
    if same is None or any(f.topic.startswith(f"{query.entity}.") for f in sheet.facts):
        return query
    if not any(f.topic.startswith(f"{same}.") for f in sheet.facts):
        return query
    return query.model_copy(update={"entity": same})


def fact_text(query: FactQuery, sheet: FactSheet) -> str | None:
    return _written(_kind_of_sheet(query, sheet), _Facts(sheet.facts))


def _written(query: FactQuery, facts: "_Facts") -> str | None:
    if query.aggregate == "unavailable":
        return f"{UNAVAILABLE}: a building file does not record it."
    if query.storey is None and query.between is None:
        named = _storeys_named(query.asked, facts)
        if len(named) > 1:  # never one of them, nor the whole file (big QA R1 E13)
            return (
                f"The question names {len(named)} storeys ({', '.join(named)}); this file's"
                " facts answer for one storey at a time (not available for several)."
            )
        if named:  # "on P1": the storey, not a word some space is named (R1 E13)
            asked = {*_tokens(named[0]), named[0].casefold()}
            words = tuple(word for word in query.words if word.casefold() not in asked)
            query = query.model_copy(update={"storey": named[0].lower(), "words": words})
    if query.entity == "space" and _flat_unplaced(query.asked, facts):
        return None  # never every space for one apartment: the question's own refusal stands
    storey = None if query.storey is None else _storey_of(query.storey, facts)
    if query.storey is not None and storey is None:
        n = len(_storeys_by_height(facts))
        said = f"it has {n} {_plural('storey', n)}: {_storey_list(facts)}"
        return f"No storey '{query.storey}' in this file; {said}."
    text = _text(query, facts, storey)
    if text is None and query.entity not in ("project", "port", "baseboard"):
        noun = _plural(_noun(query.entity))
        if query.entity == "discipline":
            noun = f"{query.discipline or 'such'} elements"
        text = _NoneHeld(f"This file holds no {noun}: {NOT_AVAILABLE}.")
    asks = query.yes_no and query.entity not in ("project", "space", "storey")
    if asks and text is not None and (said := _yes_no(query, facts, storey)) is not None:
        text = f"{said}\n{text}"
    if query.derived:
        head = f"{UNAVAILABLE} as such (not directly available); what it holds:"
        return head if text is None else f"{head}\n{text}"
    return text


def _yes_no(query: FactQuery, facts: "_Facts", storey: str | None) -> str | None:
    """Yes when the file has some of what is asked about (of the part asked: "load-bearing"),
    no when it states none; None when it states no count to say either."""
    if "fire_rating" in query.measures:
        rated = facts.get(f"{query.entity}_type.fire_rated_count")
        n = int(any(int(f.value) for f in rated))
    else:
        fact = facts.one(f"{query.entity}.count", query.part, storey)
        if fact is None:
            return None
        n = int(fact.value)
    return "Yes." if n else "No."


def _text(query: FactQuery, facts: "_Facts", storey: str | None) -> str | None:
    match query.entity:
        case "project":
            return _project(facts)
        case "storey":
            return _storeys(query, facts)
        case "space":
            return _spaces(query, facts, storey)
        case "material":
            return _materials(query, facts)
        case "discipline":
            return _discipline(query, facts, storey)
        case "system":
            return _systems(query, facts)
        case "port":
            return _ports(facts)
        case "baseboard":
            return _baseboards(query, facts, storey)
        case _:
            return _elements(query, facts, storey)


class _Facts:
    def __init__(self, facts: Iterable[Fact]) -> None:
        self.by_topic: dict[str, list[Fact]] = defaultdict(list)
        for fact in facts:
            self.by_topic[fact.topic].append(fact)
        self.read: list[Fact] = []  # every fact handed out, in order: the answer's evidence

    def get(
        self,
        topic: str,
        subject: str | None = None,
        storey: str | None = None,
        anywhere: bool = False,
    ) -> list[Fact]:
        """Facts of `topic` (of `subject`), of the whole building or, with `storey`, of that
        storey; with `anywhere`, of any storey. A system's own facts (`system` set) are left
        out: they are asked for by system."""
        found = [
            fact
            for fact in self.by_topic.get(topic, ())
            if (subject is None or fact.subject == subject)
            and (anywhere or fact.storey == storey)
            and fact.system is None
        ]
        self.read += found
        return found

    def one(self, topic: str, subject: str, storey: str | None = None) -> Fact | None:
        found = self.get(topic, subject, storey)
        return found[0] if found else None

    def of_systems(self, topic: str, storey: str | None) -> list[Fact]:
        """A topic's facts of one system each, subject "all" (a picture's runs by line style).
        Not counted as read: the caller reads the ones it says."""
        return [
            f
            for f in self.by_topic.get(topic, ())
            if f.system is not None and f.subject == "all" and f.storey == storey
        ]

    def topics(self, prefix: str) -> list[str]:
        return [topic for topic in self.by_topic if topic.startswith(prefix)]


# --- numbers in words ------------------------------------------------------------------------


def _num(fact: Fact) -> str:
    value = fact.value
    if isinstance(value, str):
        return value
    match fact.unit:
        case "count":
            return f"{int(value)}"
        case "m":
            # both: a reader may have rounded either (0.092 m is "92 mm" and "0.09 m")
            return f"{value * 1000:.0f} mm ({value:.2f} m)" if abs(value) < 1 else f"{value:.2f} m"
        case "m2":
            return f"{value:.2f} m²"
        case "m3":
            return f"{value:.3f} m³" if abs(value) < 10 else f"{value:.2f} m³"
        case "deg":
            return f"{value:.4f}°"
        case _:
            return f"{value:g}" + (f" {fact.unit}" if fact.unit else "")


def _value(value: float, unit: str) -> str:
    return _num(Fact(topic="x", subject="x", value=value, unit=unit, discipline="other", source=""))


def _pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "0%"


def _plural(word: str, n: int | float = 2) -> str:
    word = word.replace("_", " ")
    if n == 1:
        return word
    if word.endswith(("s", "x", "ch")):
        return word + "es"
    return word[:-1] + "ies" if word.endswith("y") and word[-2:-1] not in "aeiou" else word + "s"


_NOUNS = {
    "pipe_segment": "pipe segment",
    "duct_segment": "duct segment",
    "cable_carrier_segment": "cable carrier segment",
    "sanitary_terminal": "sanitary fixture",
    "heat_exchanger": "heat exchanger",
    "fire_suppression_terminal": "fire suppression terminal",
    "furniture": "furniture item",
    "covering": "covering",
    "footing": "footing",
}


def _noun(entity: str) -> str:
    return _NOUNS.get(entity, entity.replace("_", " "))


# --- names ------------------------------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold())


def _stem(word: str) -> str:
    for ending in ("ies", "es", "s"):
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: -len(ending)] + ("y" if ending == "ies" else "")
    return word


def _named(names: Iterable[str], words: Sequence[str]) -> set[str]:
    """The names that hold one of the question's subject words (as a word's start); a word of
    parts ("x-ray") holds them in a row ("X-RAY ALCOVE")."""
    stems = [" ".join(_tokens(_stem(word))) for word in words if len(word) >= 3]
    return {
        name
        for name in names
        if any(re.search(rf"(?:^| ){re.escape(stem)}", " ".join(_tokens(name))) for stem in stems)
    }


# --- storeys ----------------------------------------------------------------------------------


def _storeys_by_height(facts: _Facts) -> list[tuple[str, float]]:
    found = {
        fact.subject: float(fact.value)
        for fact in facts.get("storey.elevation", anywhere=True)
        if not isinstance(fact.value, str)
    }
    if not found:  # a sheet that names its storey but no height (a picture's title)
        found = {f.storey: 0.0 for fs in facts.by_topic.values() for f in fs if f.storey}
    return sorted(found.items(), key=lambda item: (item[1], item[0]))


def _storey_list(facts: _Facts) -> str:
    return ", ".join(name for name, _ in _storeys_by_height(facts)) or "none"


_GROUND = re.compile(r"ground|\beg\b|erdgeschoss|stueetage|begane|gelijkvloers|\b0+\b", re.I)
_ENGLISH_LEVEL = re.compile(r"\b(?:level|floor|storey|story|basement)\b", re.I)
_BELOW = re.compile(r"basement|cellar|underground|k[eæa]ll?der|kjeller|sous.sol|\b[ku]g\b", re.I)


def _numbers(name: str) -> list[int]:
    """The numbers a storey's name holds, a minus sign kept: "-1 Base" is -1, "01 Upper" 1."""
    return [int(n) for n in re.findall(r"(?:(?<!\w)-)?\d+", name)]


def _ground(storeys: Sequence[tuple[str, float]]) -> str:
    """The ground floor: named so, else the storey at elevation 0, else (a file placed above a
    site datum) its lowest floor numbered from 0 up, else the storey nearest 0."""
    if named := [name for name, _ in storeys if _GROUND.search(name)]:
        return named[0]
    nearest = min(storeys, key=lambda item: abs(item[1]))[0]
    if abs(dict(storeys)[nearest]) < 0.5:
        return nearest
    numbered = [
        (min(found), name)
        for name, _ in storeys
        if not _BELOW.search(name) and (found := [n for n in _numbers(name) if n >= 0])
    ]
    return min(numbered)[1] if numbered else nearest


def _label(name: str | None, facts: _Facts) -> str:
    """ "Level 2 (2.OG)": a storey by its place above the ground floor, then as the file names
    it; a name already in those words ("Level 2", "First Floor") stays as it is."""
    storeys = _storeys_by_height(facts)
    names = [n for n, _ in storeys]
    if name is None or name not in names or _ENGLISH_LEVEL.search(name):
        return name or "no storey"
    at = names.index(name) - names.index(_ground(storeys))
    said = "Ground floor" if at == 0 else f"Level {at}" if at > 0 else f"Basement {-at}"
    return f"{said.replace('Basement 1', 'Basement')} ({name})"


def _storeys_named(text: str, facts: _Facts) -> list[str]:
    """The model's storeys a question names by the file's own name or code, the way the
    templates read a drawing's (#702): "on P1", "on E01" (E01_OKRD), "on OG2" (OK OG2), "on the
    Erdgeschoss". A name follows on/in/at, or a named storey with and/or/to ("on P1 and P2"); a
    part of a name counts only with a digit in it; a name of letters only only capitalised, and
    a short one (EG) as written."""
    names = [name for name, _ in _storeys_by_height(facts)]
    found: list[str] = []
    for lead in (r"\b(?:on|in|at)\s+(?:the\s+)?", r"\s*(?:and|or|to|&|,|-)\s*(?:the\s+)?"):
        for name in names:
            parts = [name, *(t for t in re.split(r"[\W_]+", name) if re.search(r"\d", t))]
            for part in dict.fromkeys(p.strip() for p in parts if len(p.strip()) >= 2):
                exact = part.isalpha() and len(part) <= 3  # "EG" never as "eg"
                # a number with a unit after it is a height ("at 12 m"), not storey "12 ..."
                unit = r"(?!\s*(?:mm|cm|m²|m2|m|ft|metres?|meters?|%|°)(?!\w))" * part.isdigit()
                pattern = rf"{lead}(?P<at>{re.escape(part)})(?![\w.]){unit}"
                if lead.startswith(r"\s*") and not found:
                    continue  # "and P2" counts only after a storey named by on/in/at
                hit = re.search(pattern, text, 0 if exact else re.I)
                # a name of letters only is a storey when written as one: "on the Erdgeschoss",
                # never "in the roof construction" for a storey named "Roof"
                if hit and (not part.isalpha() or hit["at"][0].isupper()) and name not in found:
                    found.append(name)
    return found


def _storey_of(phrase: str, facts: _Facts) -> str | None:
    """The storey of the model a question's words name ("level 3" -> "3.etg"), or None."""
    storeys = _storeys_by_height(facts)
    names = [name for name, _ in storeys]
    if not names:
        return None
    compact = re.sub(r"[\s.]", "", phrase)
    if hits := [
        name for name in names if compact and compact in re.sub(r"[\s.]", "", name.lower())
    ]:
        return hits[0]
    word = re.match(r"[a-z]+", phrase)
    ordinal = (
        None if word is None or word[0] in {"level", "floor", "storey", "story", "og"} else word[0]
    )
    if ordinal and len(hits := [name for name in names if ordinal in _tokens(name)]) == 1:
        return hits[0]
    number = storey_number(phrase)
    if number is None:
        return None
    ground = _ground(storeys)
    at_ground = names.index(ground)
    if number == -1:  # the storey named a basement, else the one below the ground floor
        below = storeys[:at_ground]
        if named := [name for name, _ in below if _BELOW.search(name)]:
            return named[-1]
        return below[-1][0] if below and below[-1][1] < storeys[at_ground][1] - 0.5 else None
    if number == 0:
        return ground
    numbered = [name for name in names if number in _numbers(name)]
    if len(numbered) == 1:
        return numbered[0]
    at = at_ground + number
    if numbered:
        first = [name for name in numbered if _numbers(name)[0] == number] or numbered
        if len(first) == 1:
            return first[0]
        # B01_OKRD and E01_OKRD both hold 1: the one that many floors above the ground, else
        # none (the basement's count answered "the first floor", DigitalHub 2026-11-15)
        return names[at] if 0 <= at < len(names) and names[at] in first else None
    return names[at] if 0 <= at < len(names) else None


# --- the model ------------------------------------------------------------------------------


_PROJECT_TOPICS = (
    ("project.software", "Application (software)"),
    ("project.schema", "IFC Schema"),
    ("project.standard", "Standard"),
    ("project.name", "Project Name"),
    ("project.long_name", "Project Long Name"),
    ("project.description", "Project Description"),
    ("project.phase", "Project Phase"),
    ("building.name", "Building Name"),
    ("building.description", "Building description"),
    ("building.object_type", "Building usage"),
    ("building.address", "Address"),
    ("site.name", "Site"),
    ("site.description", "Site description"),
    ("site.latitude", "Latitude"),
    ("site.latitude_dms", "Latitude (as written)"),
    ("site.longitude", "Longitude"),
    ("site.longitude_dms", "Longitude (as written)"),
    ("site.elevation", "Site elevation"),
)


def _project(facts: _Facts) -> str | None:
    lines: list[str] = []
    for topic, label in _PROJECT_TOPICS:
        values = list(dict.fromkeys(_num(fact) for fact in facts.get(topic)))
        if values:
            lines.append(f"{label}: {'; '.join(values)}")
    return "\n".join(lines) or None


def _storeys(query: FactQuery, facts: _Facts) -> str | None:
    storeys = _storeys_by_height(facts)
    if not storeys:
        return None
    if query.between is not None:
        return _between(query.between, facts)
    return "\n".join([f"{len(storeys)} storeys:", *(_storey_line(n, facts) for n, _ in storeys)])


def _storey_line(name: str, facts: _Facts) -> str:
    said = [
        f"{label} {_num(fact)}"
        for topic, label in (
            ("storey.elevation", "elevation"),
            ("storey.height", "floor-to-floor height"),
            ("storey.gross_height", "gross height"),
            ("storey.gross_floor_area", "gross floor area"),
        )
        if (fact := facts.one(topic, name, name)) is not None
    ]
    return f"- {_label(name, facts)}: {', '.join(said)}"


def _between(pair: tuple[str, str], facts: _Facts) -> str:
    """The floor-to-floor height between two storeys the question names: the lower one's
    `storey.height` when they are one apart, else what the file states of each storey between.
    Named beside the ground floor, "first floor" counts from it (one above the ground)."""
    storeys = _storeys_by_height(facts)
    names = [name for name, _ in storeys]
    ground = names.index(_ground(storeys))
    numbers = [storey_number(phrase) for phrase in pair]
    found: list[str] = []
    for phrase, number in zip(pair, numbers, strict=True):
        if 0 in numbers and number is not None and number > 0:
            at = ground + number
            name = names[at] if at < len(names) else None
        else:
            name = _storey_of(phrase, facts)
        if name is None:
            said = f"it has {len(names)} {_plural('storey', len(names))}: {_storey_list(facts)}"
            return f"No storey '{phrase}' in this file; {said}."
        found.append(name)
    low, high = sorted(found, key=names.index)
    span = f"{_label(low, facts)} to {_label(high, facts)}"
    if names.index(high) == names.index(low) + 1:
        if (height := facts.one("storey.height", low, low)) is not None:
            return f"Floor-to-floor height from {span}: {_num(height)}"
        head = f"The file states no floor-to-floor height from {span} (not available); it states:"
    else:
        apart = f"{_label(low, facts)} and {_label(high, facts)}"
        head = f"{apart} are not one storey apart; the file states:"
    between = names[names.index(low) : names.index(high) + 1]
    return "\n".join([head, *(_storey_line(name, facts) for name in between)])


# --- spaces ---------------------------------------------------------------------------------

_HOW_MANY = re.compile(r"\s*how\s+many\b", re.I)
# A question's room word and the room types it counts (space.room_type, the drawing path's
# types). A WC and a bathroom are one family, as people and the dataset read them ("bathrooms/
# toilets: 12"; review-663 M1)
_ROOM_WORDS: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"bathroom", "wc"}), r"bath\w*|toilets?|wcs?|restrooms?|washrooms?|lavator\w*"),
    (frozenset({"bedroom"}), r"bedrooms?"),
    (frozenset({"kitchen"}), r"kitchens?"),
    (frozenset({"living"}), r"living|lounges?"),  # "living room": "room" is no subject word
)


# An apartment the question names ("in apartment B", "flat 2"), and the words that say one
_FLAT = r"apartments?|flats?|dwellings?|units?|suites?|wohnung\w*|appartements?|appartamento|asunto"
_FLAT_NAMED = re.compile(
    rf"\b(?:{_FLAT})\s+(?:no\.?\s*|number\s+|#\s*)?(?P<id>[a-z]|\d+[a-z]?|[a-z]\d+)\b(?![.,]\d)",
    re.I,
)


# A place that is one room: a room word, or a room type ("in the kitchen", "in room 1-2"). "In this
# house", "in the structural walls", "in the roof construction" are not (the golden set's models)
_ONE_ROOM = re.compile(
    "|".join(
        (
            r"rooms?|spaces?|offices?|corridors?|halls?|hallways?|cafeterias?|canteens?|lobby|"
            r"foyers?|entrances?|storage|stores?|garages?|laundry|utility|dining|study|küche|flur",
            *(words for _, words in _ROOM_WORDS),
        )
    ),
    re.I,
)


def _counted_in_one_room(query: FactQuery) -> bool:
    """A model's count of things inside one room ("How many radiators are in the kitchen?"): its
    facts count by type and storey, never by room (sample services-mep: the heating model's 63
    radiators were given for the kitchen). A room's own facts are not refused."""
    room = any(_ONE_ROOM.fullmatch(word) for word in (query.place or "").split())
    return query.how_many and query.entity not in ("space", "storey") and room


def _flat_unplaced(asked: str, facts: _Facts) -> bool:
    """The question names an apartment (demo bug 2026-11-15: "the kitchen in apartment B" gave
    every space) that no space's name says: the facts group no spaces into apartments."""
    flat = _FLAT_NAMED.search(asked)
    if flat is None:
        return False
    said = " ".join(_tokens(flat.group(0)))
    spaces = facts.get("space.long_name", anywhere=True)
    names = [*(str(f.value) for f in spaces), *(f.subject for f in spaces)]
    return not any(f" {said} " in f" {' '.join(_tokens(name))} " for name in names)


def _rooms_said(kinds: Iterable[str]) -> str:
    said = {"wc": "WC", "living": "living room"}
    return " or ".join(said.get(kind, kind) for kind in sorted(kinds))


def _room_kinds(words: Sequence[str]) -> frozenset[str] | None:
    """The room types a question's one room word counts ("bathrooms": bathroom and WC)."""
    word = " ".join(words)
    return next(
        (kinds for kinds, pattern in _ROOM_WORDS if re.fullmatch(pattern, word, re.I)), None
    )


# The noun an area total names ("the total office area", "the total area of the offices"), as the
# templates parser reads it (question_templates.TOTAL_NOUN); a noun that is the model, a floor or
# its spaces names no room
_AREA_OF = re.compile(
    r"\btotal (?P<before>[^\W\d_]+)(?= area\b)"
    r"|\barea (?:of|for) (?:the |all (?:of )?(?:the )?|every |its |this )?(?P<of>[^\W\d_]+)"
    # "rooms labelled 'Büro'": the label is the room word
    r"|\b(?:labell?ed|named|called)\s+(?:as\s+)?[\"'\u2018\u201c\u201e\u00ab]?(?P<label>\w[\w/-]*)",
    re.IGNORECASE,
)
_NOT_A_ROOM = frozenset(
    """
    floor floors plan drawing sheet page storey level layout apartment flat dwelling unit house
    room rooms space spaces indoor interior internal numbered net usable this these whole entire
    gross building model project file each the a an all every its
    """.split()  # noqa: SIM905 (a word list reads better as text)
)


def _area_room_word(asked: str, facts: _Facts) -> str | None:
    """The room word an area total names that is no word for the model, a floor or its spaces,
    nor a word of the model's own project or building name ("the dental clinic")."""
    names = {
        word
        for topic, _ in _PROJECT_TOPICS
        if topic.endswith("name")
        for fact in facts.get(topic)
        for word in _tokens(str(fact.value))
    }
    for found in _AREA_OF.finditer(asked):
        word = (found.group("before") or found.group("of") or found.group("label")).casefold()
        if word not in _NOT_A_ROOM and word not in names:
            return word
    return None


_SPACE_AREAS = ("space.stated_area", "space.net_floor_area", "space.area", "space.gross_floor_area")


def _area_topics(query: FactQuery) -> tuple[str, ...]:
    asked = " ".join(query.asked.lower().split())
    if "gross" in asked or "gfa" in asked:
        return ("space.gross_floor_area", "space.stated_area", "space.area")
    if "net" in asked or "ufa" in asked:
        return ("space.net_floor_area", "space.stated_area", "space.area")
    return _SPACE_AREAS


def _spaces(query: FactQuery, facts: _Facts, storey: str | None) -> str | None:
    if query.guid is not None:  # pic-reg S1: never the all-spaces total for one space's GUID
        return (
            "This file's facts do not list spaces by GlobalId, so a space cannot be found by it"
            " here (not available)."
        )
    names = {fact.subject: fact.storey for fact in facts.get("space.long_name", anywhere=True)}
    for topic in _SPACE_AREAS:
        for fact in facts.get(topic, anywhere=True):
            if fact.subject != "all":  # a sum over spaces, not a space
                names.setdefault(fact.subject, fact.storey)
    if not names:
        return None
    long_name = {f.subject: str(f.value) for f in facts.get("space.long_name", anywhere=True)}
    chosen = [name for name, at in names.items() if storey is None or at == storey]
    labelled = {name: f"{name} {long_name.get(name, '')}" for name in chosen}
    picked = _named(labelled.values(), query.words)
    typed = {f.subject: str(f.value) for f in facts.get("space.room_type", anywhere=True)}
    room = [w for w in query.words if not re.fullmatch(_FLAT, w, re.I)]  # "in the apartment"
    kinds = None if picked else _room_kinds(room)
    if kinds is not None:  # no name holds the word: the spaces its room word types (R1 E6)
        picked = {labelled[name] for name in chosen if typed.get(name) in kinds}
    if picked:
        chosen = [name for name in chosen if labelled[name] in picked]
        if query.measures == ("height",) and query.aggregate == "list":  # asked alone
            return _heights(query, facts, chosen, names, long_name)
    topics = _area_topics(query)
    missing = None
    if topics[0] != _SPACE_AREAS[0] and not facts.get(topics[0], anywhere=True):
        said = topics[0].split(".")[1].replace("_", " ")
        missing = f"The file states no {said} for its spaces (not available); their own areas:"
    area: dict[str, float] = {}
    for name in chosen:
        for topic in topics:
            fact = facts.one(topic, name, names[name])
            if fact is not None and not isinstance(fact.value, str):
                area[name] = float(fact.value)
                break

    def line(name: str) -> str:
        label = _space_label(name, long_name)
        text = f"- {label}: {_value(area[name], 'm2')}" if name in area else f"- {label}"
        if "height" in query.measures and (high := facts.one("space.height", name, names[name])):
            text += f"{',' if name in area else ':'} height {_num(high)}"
        return text

    def total(subject: str, at: str | None, function: bool = False) -> str:
        """A group's count and area as the facts state them (facts_arch sums them); a storey's
        area with its share of all the spaces' area."""
        prefix = "space_function" if function else "space"
        count = facts.one(f"{prefix}.count", subject, at)
        said = "" if count is None else f"{_num(count)} {_plural('space', float(count.value))}"
        for topic in topics:
            measure = topic.split(".")[1]
            if (summed := facts.one(f"{prefix}.{measure}", subject, at)) is not None:
                share = "" if at is None or function else _share(summed, facts.one(topic, "all"))
                area = f"{_num(summed)}{share}"
                return f"{said}, total area {area}" if said else f"total {area}"
        return said

    where = f" on {_label(storey, facts)}" if storey else ""
    if not chosen:
        return f"No such spaces{where} in this file."
    if kinds is not None and not picked and not _HOW_MANY.match(query.asked):
        # a room type no space has: never every space as its answer (review-729 M1)
        named = " ".join(query.words)
        said = f"named '{named}' or typed as {_rooms_said(kinds)}"
        return f"No space{where} in this file is {said} (not available)."
    if not picked and "area" in query.measures and (word := _area_room_word(query.asked, facts)):
        # a room word no space's name holds and no room type has ("the total area of the
        # offices"): never every space as its answer (sample explorers 2026-11-15, 903.07 m²)
        return _NoRoomNamed(f"No space{where} in this file is named '{word}' ({NOT_AVAILABLE}).")
    lines = [missing] if missing else []
    if len(query.words) == 1 and not picked and _HOW_MANY.match(query.asked):
        # "How many offices?" and no space is one: said, then every space
        typed_as = f" or typed as {_rooms_said(kinds)}" if kinds is not None and typed else ""
        lines.insert(
            0,
            f"No space{where} in this file is named '{query.words[0]}'{typed_as} (not available).",
        )
    if picked:  # how many spaces the question's words name: a count of the listed spaces
        n = len(chosen)  # with its noun: "8" before a line "M. TOILET" would read as 8 m
        matched = f"{n} {_plural('space', n)}"
        said = (
            f"Spaces typed as {_rooms_said(kinds)} by their names"
            if kinds is not None
            else f"Spaces matching '{' '.join(query.words)}'"
        )
        lines.insert(0, f"{said}{where}: {matched}")
    else:
        lines.append(f"Spaces{where}: {total('all', storey)}")
    if query.aggregate in ("max", "min"):
        pick = max if query.aggregate == "max" else min
        if area:
            best = pick(area, key=lambda name: area[name])
            word = "largest" if query.aggregate == "max" else "smallest"
            lines.append(f"The {word} is {line(best)[2:]}")
        return "\n".join(lines)
    extras = _space_extras(query, facts, storey, topics)
    tail: list[str] = []
    if picked and extras:  # said last and apart: they would read as the named spaces' own
        tail = [f"All spaces{where} in this file, not only those named:", *extras]
    else:
        lines += extras
    by_type = query.by == "function" and re.search(r"\btypes?\b", query.asked, re.I)
    kinds = {f.subject: str(f.value) for f in facts.get("space.type", anywhere=True)}
    if picked or (query.by == "function" and not (by_type and kinds)):
        # by function (LongName), whose counts and areas facts_arch sums per storey
        groups: dict[str | None, list[str]] = defaultdict(list)
        for name in chosen:
            groups[long_name.get(name)].append(name)
        for function, group in sorted(groups.items(), key=lambda item: str(item[0])):
            head = total(function, storey, function=True) if function else ""
            lines.append(f"{function or 'no function'}: {head}".rstrip(": "))
            lines += ["  " + line(name) for name in group]
    elif query.by == "function":
        groups = defaultdict(list)
        for name in chosen:
            groups[kinds.get(name)].append(name)
        for kind, group in sorted(groups.items(), key=lambda item: str(item[0])):
            lines.append(f"{kind or 'no type'}:")
            lines += ["  " + line(name) for name in group]
    elif query.by == "storey" or (storey is None and len({names[n] for n in chosen}) > 1):
        order = [name for name, _ in _storeys_by_height(facts)]
        groups = defaultdict(list)
        for name in chosen:
            groups[names[name]].append(name)
        if query.by == "storey" and order:  # every storey, the empty ones too
            lines.append(f"Spaces on {len(groups)} of the file's {len(order)} storeys")
            for at in order:
                groups.setdefault(at, [])
        for at in sorted(groups, key=lambda s: order.index(s) if s in order else len(order)):
            head = total("all", at) if groups[at] else f"0 spaces, total area {_value(0, 'm2')}"
            lines.append(f"{_label(at, facts)}: {head}".rstrip(": "))
            lines += ["  " + line(name) for name in groups[at]]
    else:
        lines += [line(name) for name in chosen]
    return "\n".join(lines + tail)


CUT = "its shape is cut (a sloped or clipped ceiling), so its height varies"


def _space_label(name: str, long_name: Mapping[str, str]) -> str:
    said = long_name.get(name)
    return f"Space {name}" if said is None or said == name else f"{said} (Space {name})"


def _heights(
    query: FactQuery,
    facts: _Facts,
    chosen: Sequence[str],
    storey_of: Mapping[str, str | None],
    long_name: Mapping[str, str],
) -> str:
    """The height of the spaces a question names, and no count or area: what was asked
    (Tudor R4-H1). A space whose height the file does not state is said to have none."""
    high = {
        name: fact
        for name in chosen
        if (fact := facts.one("space.height", name, storey_of[name])) is not None
    }
    top = {
        name: fact
        for name in chosen
        if name not in high
        and (fact := facts.one("space.height_up_to", name, storey_of[name])) is not None
    }

    def said(name: str) -> str:
        if name in high:
            return _num(high[name])
        if name in top:  # pic-reg M1: a clipped room has no single height
            return f"up to {_num(top[name])}; {CUT}"
        return "the file states no height (not available)"

    if len(chosen) == 1:
        label = _space_label(chosen[0], long_name)
        if chosen[0] in high:
            return f"Height of {label}: {_num(high[chosen[0]])}"
        if chosen[0] in top:
            return f"{label}: {said(chosen[0])}"
        return f"The file states no height for {label} (not available)."
    lines = [f"Heights of the {len(chosen)} spaces named '{' '.join(query.words)}':"]
    lines += [f"- {_space_label(name, long_name)}: {said(name)}" for name in chosen]
    return "\n".join(lines)


def _space_extras(
    query: FactQuery, facts: _Facts, storey: str | None, topics: tuple[str, ...]
) -> list[str]:
    """The model's own totals: gross floor areas the storeys and the building state."""
    lines: list[str] = []
    building = facts.get("building.gross_floor_area", anywhere=True)
    for fact in building:
        lines.append(f"Building gross floor area: {_num(fact)}")
    per_storey = [
        f"- {_label(name, facts)}: {_num(fact)}{_share(fact, building[0] if building else None)}"
        for name, _ in _storeys_by_height(facts)
        if (fact := facts.one("storey.gross_floor_area", name, name)) is not None and fact.value
    ]
    gross = topics[0] == "space.gross_floor_area" or query.by == "storey"
    if storey is None and per_storey and gross:
        lines += ["Gross floor area by storey:", *per_storey]
    for topic, label in (
        ("space.gross_floor_area", "gross floor area as the file states it"),
        ("space.net_floor_area", "net floor area as the file states it"),
        ("space.stated_area", "stated area"),
        ("space.area", "footprint area from the model's geometry"),  # the takeoff's model-spaces
    ):
        if (fact := facts.one(topic, "all", storey)) is not None:
            lines.append(f"Sum of the spaces' {label}: {_num(fact)}")
    if storey is not None:
        for fact in facts.get("storey.gross_floor_area", storey, storey):
            lines.append(f"Storey gross floor area: {_num(fact)}")
    return lines


# --- elements -------------------------------------------------------------------------------

_SUMMED = {
    "length": ("length",),
    "area": (
        "net_side_area",
        "gross_side_area",
        "net_area",
        "gross_area",
        "area",
        "outer_surface_area",
    ),
    "volume": ("net_volume", "gross_volume", "volume"),
}
_LISTED = {  # per type: the measures a question's words ask for
    "thickness": ("thickness",),
    "width": ("width",),
    "height": ("height",),
    "depth": ("depth",),
    "size": (
        "width",
        "height",
        "depth",
        "thickness",
        "profile_width",
        "profile_depth",
        "profile_diameter",
        "cross_section_area",
        "diameter",
    ),
    "material": ("material",),
    "fire_rating": ("fire_rating",),
}


def _elements(query: FactQuery, facts: _Facts, storey: str | None) -> str | None:
    entity = query.entity
    if query.guid is not None:
        return _by_guid(query, facts)
    if "length" in query.measures and (said := _runs_by_system(query, facts, storey)) is not None:
        return said
    runs = facts.get(f"{entity}.length", "all", storey)  # a picture's runs: lengths, no count
    if (
        not facts.get(f"{entity}.count", "all", storey)
        and not facts.get(f"{entity}_type.count")
        and not runs
    ):
        if _room_kinds(query.named) is not None and facts.get("space.room_type", anywhere=True):
            # "toilets" and no fixture in the file: its WC rooms, never a type whose name holds
            # the word ("Toilettentrennwand", a partition wall; big QA R1 E10)
            return _spaces(query.model_copy(update={"words": query.named}), facts, storey)
        return _by_name(query, facts, storey)
    noun = _noun(entity)
    where = f" on {_label(storey, facts)}" if storey else ""
    part = query.part if facts.get(f"{entity}.count", query.part, storey) else "all"
    said = "" if part == "all" else part.replace("_", "-").replace("non-", "non-") + " "
    total = facts.one(f"{entity}.count", part, storey)
    count = 0 if total is None else int(total.value)
    runs_only = total is None and bool(runs)
    lines = [] if runs_only else [f"Total {said}{_plural(noun)}{where}: {count}"]
    totals = [
        f"{_TOTALS[entity].capitalize()}s in all: {f.topic.split('.')[1]} {_num(f)}"
        for topic in sorted(facts.topics(f"{_TOTALS.get(entity, entity)}."))
        if entity in _TOTALS and topic.endswith(".total")
        for f in facts.get(topic, "all")
    ]
    if not count and not totals and not runs_only:  # the sheet lacks the kind and its groups
        lines.insert(0, f"No {said}{_plural(noun)}{where} in this file.")
    if storey is None:  # the type counts are the whole file's
        lines = _kinds_named(query, facts, noun, count) + lines
    if query.part != part:
        asked = query.part.replace("_", "-")
        lines.insert(0, f"The file does not say which {_plural(noun)} are {asked} (not available).")
    for measure in query.measures:
        summed = [
            f"Total {name.replace('_', ' ')}: {_num(fact)}"
            for name in _SUMMED.get(measure, ())
            if (fact := facts.one(f"{entity}.{name}", part, storey)) is not None
        ]
        named = re.search(_NAMED_BY.get(measure, r"."), query.asked, re.I)  # not "concrete"
        if count and named and measure in _SUMMED and not summed:
            summed = [f"The file states no {measure} for its {_plural(noun)} (not available)."]
        lines += summed
        stated = [
            t
            for t in _LISTED.get(measure, ())
            for group in (entity, f"{entity}_type", f"{entity}_name")
            if facts.get(f"{group}.{t}", anywhere=True)
        ]
        if count and named and measure in _LISTED and measure != "size" and not stated:
            said = measure.replace("_", " ")
            lines.append(f"The file states no {said} for its {_plural(noun)} (not available).")
    words = {w.replace(" ", "").lower() for w in query.words}
    sized = [  # a printed size the question names ("DN20 pipe"): its own length first
        f"Length of {fact.subject}: {_num(fact)}"
        for fact in facts.get(f"{entity}.size_length", storey=storey)
        if fact.subject.replace(" ", "").lower() in words
    ]
    lines = sized + lines
    if query.aggregate == "share" or (query.part != "all" and query.aggregate == "list"):
        lines += _shares(entity, facts, storey)
    if query.aggregate in ("max", "min", "average"):
        lines += _extremes(query, facts, part)
    material, material_named = _by_material(query, facts, storey)
    lines = material + lines if material_named else lines + material  # the asked subject first
    if "glazing" in query.measures:
        lines += _glazing(query, facts)
    lines += _in_spaces(query, facts)
    lines += _aggregates(entity, facts, storey)
    lines += _categories(query, facts, storey)
    lines += totals
    types = _types(query, facts, storey, part)
    if types:
        lines.append(f"{_plural(noun).capitalize()} by type:")
        lines += types
    if query.by == "storey" and storey is None:  # asked per floor: the storeys lead (R1 ifc E3)
        lines = _per_storey(entity, part, facts) + lines
    if "fire_rating" in query.measures:
        lines += _fire(entity, facts)
    if "length" in query.measures:  # a picture's lengths are estimates (orchestrator 05:40)
        runs = [f for f in facts.get(f"{entity}.length", part, storey) if _picture(f)]
        if runs:
            lines += _spread(runs)
    return "\n".join(lines)


def _runs_by_system(query: FactQuery, facts: _Facts, storey: str | None) -> str | None:
    """A picture's run length of each system the question names ("rainwater": S_Regenwasser, by
    the system words in the line style's name or the name itself), or of every system when it
    asks per system; never the sheet's total as one system's (orchestrator 05:40). None: the
    question names no system, or the sheet has no picture runs by system."""
    systems = [f for f in facts.of_systems(f"{query.entity}.length", storey) if _picture(f)]
    if not systems:
        return None
    named = [
        f
        for f in systems
        if f.system is not None
        and (
            (
                query.system is not None
                and system_from_question(_style_words(f.system)) == query.system
            )
            or re.search(rf"(?<![^\W_]){re.escape(f.system)}(?![^\W_])", query.asked, re.I)
        )
    ]
    if named:
        facts.read += named
        lines = [f"{f.system}: {_num(f)}" for f in named]
    elif query.system is not None or query.by == "system":
        facts.read += systems
        lines = [f"- {f.system}: {_num(f)}" for f in systems]
        # a system that is a whole discipline ("heating") asked of a sheet all of that
        # discipline means every run on it, whatever its styles are named (review-652 M1);
        # "cold water" on a plumbing sheet does not: it is one of several systems there
        discipline = SYSTEM_DISCIPLINE.get(query.system)  # type: ignore[call-overload]
        whole = query.system is not None and discipline == query.system
        if query.system is not None and not (
            whole and all(f.discipline == query.system for f in systems)
        ):
            asked = query.system.replace("_", " ")
            head = (
                f"No run on this sheet is labelled as {asked} (not available); its runs by system:"
            )
            lines.insert(0, head)
        elif (total := facts.one(f"{query.entity}.length", "all", storey)) is not None:
            lines.append(f"Total length: {_num(total)}")
    else:
        return None
    return "\n".join([*lines, *_spread(systems)])


def _style_words(style: str) -> str:
    """A line style's name as words for system_from_question: "S_PWC" is "S cold water"."""
    text = style.replace("_", " ")
    for code, words in _STYLE_CODES:
        text = code.sub(words, text)
    return text


def _spread(runs: Sequence[Fact]) -> list[str]:
    """The estimate sentence of the colour reader that measured a picture's runs (the first
    reader its source names); none for another reader."""
    reader = runs[0].source.split(":")[1].split("+")[0] if ":" in runs[0].source else ""
    return [_SPREADS[reader]] if reader in _SPREADS else []


def _by_guid(query: FactQuery, facts: _Facts) -> str:
    """The asked measures of the one element whose GlobalId the question names (Tudor R4-H2),
    never a count of its class; a GUID the file lacks, or a measure it does not state, is said."""
    guid, noun = query.guid, _noun(query.entity)
    listed = facts.get(f"{query.entity}.global_id", anywhere=True)
    if not listed:  # pic-reg M2: the class has no one-by-one facts, so no GUIDs to look in
        return (
            f"This file's facts do not list {_plural(noun)} one by one, so a {noun} cannot be"
            " found by its GlobalId here (not available)."
        )
    held = [f for f in listed if f.value == guid]
    if not held:
        return f"No {noun} in this file has GlobalId {guid} (not available)."
    element = held[0]
    head = f"{noun.capitalize()} {element.subject} (GlobalId {guid})"
    asked = [t for m in query.measures for t in _LISTED.get(m, ())] or list(_LISTED["size"])
    said = [
        f"{t.replace('_', ' ')} {_num(fact)}"
        for t in dict.fromkeys(asked)
        if (fact := facts.one(f"{query.entity}.{t}", element.subject, element.storey)) is not None
    ]
    if said:
        return f"{head}: {', '.join(said)}"
    words = " or ".join(dict.fromkeys(m.replace("_", " ") for m in query.measures))
    return f"{head}: the file states no {words} for it (not available)."


# The PredefinedTypes a word names, per class: "toilets" are some of the sanitary fixtures
_KINDS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "sanitary_terminal": (
        (r"toilets?|wcs?", ("WCSEAT", "TOILETPAN")),
        (r"urinals?", ("URINAL",)),
        (r"(?:wash)?basins?|lavator", ("WASHHANDBASIN",)),
        (r"sinks?", ("SINK", "WASHHANDBASIN")),  # a washbasin is a sink too (R4-C3)
    ),
}


def _kinds_named(query: FactQuery, facts: _Facts, noun: str, count: int) -> list[str]:
    """The count of the kinds the question's word names, by the file's PredefinedType, first:
    the class's total would read as theirs."""
    word = " ".join(query.named)
    kinds = next(
        (k for pattern, k in _KINDS.get(query.entity, ()) if re.fullmatch(pattern, word, re.I)),
        None,
    )
    if kinds is None:
        return []
    found = [
        f"{fact.subject} {_num(fact)}"
        for fact in facts.get(f"{query.entity}.count_by_predefined_type", anywhere=True)
        if fact.subject in kinds
    ]
    if not found:
        return [f"The file does not mark which {_plural(noun)} are {word} (not available)."]
    return [
        f"{word.capitalize()} by the file's type: {', '.join(found)} (of {count} {_plural(noun)})"
    ]


_TOTALS = {"footing": "foundation"}  # the sheet's totals of a wider group than the class
# A measure asked by its own words: "concrete" asks a volume of a material, not the material.
_NAMED_BY = {"material": r"material|made\s+of|composition|layer"}
_GLASS = re.compile(r"glaz|glass|glas\b|pane|ruit|verglas", re.I)


def _glazing(query: FactQuery, facts: _Facts) -> list[str]:
    """What the file states of the glazing: any fact of the kind naming glass or glazing."""
    said = sorted(
        {
            f"- {f.subject}: {f.value}"
            for topic in facts.topics(query.entity)
            for f in facts.get(topic, anywhere=True)
            if isinstance(f.value, str) and (_GLASS.search(f.value) or _GLASS.search(topic))
        }
    )
    noun = _plural(_noun(query.entity))
    return (
        ["Glazing:", *said]
        if said
        else [f"The file states no glazing for its {noun} (not available)."]
    )


# The sheet's splits and means of a kind (facts_mep.py): "count_by_shape", "length_mean"...
_AGGREGATE = re.compile(r"\.(?:(?:count|length|with_length)_by_\w+|length_mean|length_per_storey)$")


def _aggregates(entity: str, facts: _Facts, storey: str | None) -> list[str]:
    lines: list[str] = []
    for topic in sorted(facts.topics(f"{entity}.")):
        if _AGGREGATE.search(topic):
            found = facts.get(topic, storey=storey)
            said = topic.split(".", 1)[1].replace("_", " ")
            if [f.subject for f in found] == ["all"]:
                lines.append(f"{said}: {_num(found[0])}")
            elif found:
                whole = facts.one(f"{entity}.count", "all", storey) if "count" in said else None
                lines.append(f"{said.capitalize()}:")
                lines += [
                    f"- {f.subject}: {_num(f)}{_share(f, whole)}"
                    for f in sorted(found, key=lambda f: (-float(f.value), f.subject))
                    if f.subject != "all"
                ]
    return lines


def _share(fact: Fact, whole: Fact | None) -> str:
    """(31.6%): a count's share of the total it is listed under."""
    if whole is None or isinstance(fact.value, str) or isinstance(whole.value, str):
        return ""
    return f" ({_pct(float(fact.value), float(whole.value))})" if whole.value else ""


def _categories(query: FactQuery, facts: _Facts, storey: str | None) -> list[str]:
    """The file's own categories (Revit's "Ducts", "Mechanical Equipment") the question names."""
    asked = [_stem(word) for word in _tokens(query.asked)]
    lines: list[str] = []
    for fact in sorted(facts.get("category.count", storey=storey), key=lambda f: f.subject):
        words = [_stem(word) for word in _tokens(fact.subject)]
        if words and all(any(a.startswith(w) for a in asked) for w in words):
            said = [_num(fact)] + [
                f"{topic.split('.')[1].replace('_', ' ')} {_num(f)}"
                for topic in (
                    "category.length",
                    "category.length_mean",
                    "category.length_per_storey",
                )
                if (f := facts.one(topic, fact.subject, storey)) is not None
            ]
            lines.append(f"{fact.subject} (category): {', '.join(said)}")
    return lines


def _subject(fact: Fact) -> str:
    return fact.subject


def _in_spaces(query: FactQuery, facts: _Facts) -> list[str]:
    """The asked elements in a space the question names by its number or name ("room A202")."""
    asked = {word.casefold() for word in query.words}
    lines: list[str] = []
    for fact in sorted(facts.get(f"{query.entity}.count_in_space", anywhere=True), key=_subject):
        if fact.subject.casefold() in asked:
            lines.append(f"In space {fact.subject}: {_num(fact)}")
            lines += [
                f"- {f.subject}"
                for f in sorted(facts.get(f"{query.entity}.space", anywhere=True), key=_subject)
                if f.value == fact.subject
            ]
    return lines


def _by_material(query: FactQuery, facts: _Facts, storey: str | None) -> tuple[list[str], bool]:
    """The sheet's splits by material when the question asks for materials or names a kind of
    material the split knows ("concrete"), and whether it names one."""
    lines: list[str] = []
    asked = False
    for split in ("by_material_kind", "by_material"):
        found = [
            f
            for measure in ("count", "volume", "net_volume", "area", "length")
            for f in sorted(
                facts.get(f"{query.entity}.{measure}.{split}", storey=storey),
                key=lambda f: (-float(f.value), f.subject),
            )
        ]
        words = {_stem(w) for w in _tokens(query.asked)}  # "concrete" is a measure's word too
        named = {f.subject for f in found if words & {_stem(t) for t in _tokens(f.subject)}}
        asked = asked or bool(named)
        if found and ("material" in query.measures or named):
            kind = " kind" if split == "by_material_kind" else ""
            lines.append(f"{_plural(_noun(query.entity)).capitalize()} by material{kind}:")
            lines += [
                f"- {f.subject}: {f.topic.split('.')[1].replace('_', ' ')} {_num(f)}"
                for f in found
                if not named or f.subject in named or split == "by_material"
            ]
    return lines, asked


def _shares(entity: str, facts: _Facts, storey: str | None) -> list[str]:
    total = facts.one(f"{entity}.count", "all", storey)
    if total is None or not total.value:
        return []
    lines: list[str] = []
    head = f"Of all {_num(total)} {_plural(_noun(entity))}: "
    for yes, no in (("load_bearing", "non_load_bearing"), ("external", "internal")):
        counts = [facts.one(f"{entity}.count", side, storey) for side in (yes, no)]
        if all(fact is None for fact in counts):
            continue
        whole = float(total.value)
        said = [
            f"{side.replace('_', '-')}: {int(fact.value)} ({_pct(float(fact.value), whole)})"
            for side, fact in zip((yes, no), counts, strict=True)
            if fact is not None
        ]
        lines.append(head + "; ".join(said))
        for name in ("net_volume", "length", "net_side_area"):
            sums = [facts.one(f"{entity}.{name}", side, storey) for side in ("all", yes, no)]
            if sums[0] is not None and sums[1] is not None and float(sums[0].value):
                whole = float(sums[0].value)
                parts = [
                    f"{side.replace('_', '-')} {_num(fact)} ({_pct(float(fact.value), whole)})"
                    for side, fact in zip((yes, no), sums[1:], strict=True)
                    if fact is not None
                ]
                lines.append(
                    f"By {name.replace('_', ' ')} (of {_num(sums[0])}): {'; '.join(parts)}"
                )
    return lines


_PART_SUBJECTS = ("all", "external", "internal", "load_bearing", "non_load_bearing")


def _extremes(query: FactQuery, facts: _Facts, part: str) -> list[str]:
    """Largest, smallest and average of each measure asked, as the sheet states them (else read
    off its elements), naming the elements that hold the largest and the smallest."""
    lines: list[str] = []
    measures = (*_LISTED, *_SUMMED)
    asked = [
        t
        for m in query.measures
        if m in measures
        for t in (*_LISTED.get(m, ()), *_SUMMED.get(m, ()))
    ]
    for name in dict.fromkeys(asked):
        topic = f"{query.entity}.{name}"
        each = [
            f
            for f in facts.get(topic, anywhere=True)
            if not isinstance(f.value, str)
            and f.subject not in _PART_SUBJECTS
            and not f.subject.startswith("predefined:")
        ]
        said: list[str] = []
        for suffix, word, pick in (("max", "largest", max), ("min", "smallest", min)):
            stated = facts.one(f"{topic}.{suffix}", part)
            value = float(stated.value) if stated is not None else None
            if value is None and each:
                value = pick(float(f.value) for f in each)
            if value is not None:
                unit = stated.unit if stated is not None and stated.unit else each[0].unit
                said.append(
                    f"{word} {_value(value, unit or 'm')}{_holders(facts, query, each, value)}"
                )
        for average in facts.get(f"{topic}.average", part):
            said.append(f"average {_num(average)}")
        if said:
            lines.append(f"{name.replace('_', ' ').capitalize()}: {', '.join(said)}")
    return lines


def _holders(facts: _Facts, query: FactQuery, each: Sequence[Fact], value: float) -> str:
    """(W7, Brick 300): the elements with this value and their types, three at most."""
    held = [f.subject for f in each if abs(float(f.value) - value) <= 1e-9 * max(1.0, abs(value))]
    named: list[str] = []
    for subject in dict.fromkeys(held[:3]):
        kind = facts.get(f"{query.entity}.type", subject, anywhere=True)
        named.append(subject if not kind else f"{subject}, {_num(kind[0])}")
    more = f" and {len(held) - 3} more" if len(held) > 3 else ""
    return f" ({'; '.join(named)}{more})" if named else ""


def _groups(facts: _Facts, topic: str, storey: str | None, part: str) -> dict[str, int]:
    """Counts per type (or name) of `part`: facts_arch writes a part's as "<type> | <part>"."""
    counts = facts.get(topic, storey=storey)
    if part == "all":
        found = {f.subject: int(f.value) for f in counts if " | " not in f.subject}
    else:
        suffix = f" | {part}"
        found = {
            f.subject[: -len(suffix)]: int(f.value) for f in counts if f.subject.endswith(suffix)
        }
    # A type stated twice, plain and as Revit's "Family:Type": keep the one naming both.
    for name in [name for name in found if ":" in name]:
        if found.get(plain := name.split(":", 1)[1]) == found[name]:
            del found[plain]
    return found


def _types(query: FactQuery, facts: _Facts, storey: str | None, part: str) -> list[str]:
    entity = query.entity
    group = f"{entity}_type"
    n = _groups(facts, f"{group}.count", storey, part)
    named = _groups(facts, f"{entity}_name.count", storey, part)
    if named and _named(named, query.words) and not _named(n, query.words):
        group, n = f"{entity}_name", named  # the question names elements, not types
    mep = not n and not facts.get(f"{group}.count")
    if mep:  # MEP: a kind's count per type name
        n = {f.subject: int(f.value) for f in facts.get(f"{entity}.count", storey=storey)}
        n.pop("all", None)
    picked = _named(n, query.words)
    if picked:
        n = {name: count for name, count in n.items() if name in picked}
    n = {name: count for name, count in n.items() if count}
    if not n:
        return []
    stated = facts.one(f"{entity}.count", part, storey)
    whole = 0.0 if stated is None else float(stated.value)
    lines: list[str] = []
    for name, count in sorted(n.items(), key=lambda item: (-item[1], item[0])):
        said = [f"{count} ({_pct(count, whole)})" if whole else f"{count}"]
        if not mep:
            said += _type_measures(query, facts, group, name, storey)
        else:
            for fact in facts.get(f"{entity}.length", name):
                said.append(f"length {_num(fact)}")
        lines.append(f"- {name}: {', '.join(said)}")
        if not mep and "material" in query.measures:
            lines += _layers(group, facts, name)
    return lines + _distributions(query, facts)


def _distributions(query: FactQuery, facts: _Facts) -> list[str]:
    """How many elements have each size, width or thickness (facts_arch counts them)."""
    lines: list[str] = []
    for measure, topic, label in (
        ("thickness", "thickness", "thickness"),
        ("size", "size", "size"),
        ("width", "width", "width"),
    ):
        if measure in query.measures and (found := facts.get(f"{query.entity}_{topic}.count")):
            lines.append(f"{_plural(_noun(query.entity)).capitalize()} by {label}:")
            lines += [f"- {f.subject}: {_num(f)}" for f in found]
    return lines


def _type_measures(
    query: FactQuery, facts: _Facts, group: str, name: str, storey: str | None
) -> list[str]:
    said: list[str] = []
    listed = dict.fromkeys(t for measure in query.measures for t in _LISTED.get(measure, ()))
    summed = dict.fromkeys(t for measure in query.measures for t in _SUMMED.get(measure, ()))
    for topic in listed:  # once each: "size" and "width" both list the width
        values = list(dict.fromkeys(_num(f) for f in facts.get(f"{group}.{topic}", name)))
        if values and not (topic == "material" and facts.get(f"{group}.layer")):
            said.append(f"{topic.replace('_', ' ')} {' / '.join(values)}")
    for topic in summed:
        if (fact := facts.one(f"{group}.{topic}", name, storey)) is not None:
            said.append(f"{topic.replace('_', ' ')} {_num(fact)}")
    return said


def _layers(group: str, facts: _Facts, name: str) -> list[str]:
    layers = [f for f in facts.get(f"{group}.layer") if f.subject.startswith(f"{name} | ")]
    if not layers:
        return [f"    material: {_num(f)}" for f in facts.get(f"{group}.material", name)]
    return [
        f"    {number}. {fact.subject.split(' | ', 2)[-1]}: {_num(fact)}"
        for number, fact in enumerate(layers, start=1)
    ]


def _per_storey(entity: str, part: str, facts: _Facts) -> list[str]:
    """The kind's count on each storey; a storey the sheet counts none on holds none."""
    names = [name for name, _ in _storeys_by_height(facts)]
    counts = {name: facts.one(f"{entity}.count", part, name) for name in names}
    if not any(counts.values()):
        return []
    return [f"{_plural(_noun(entity)).capitalize()} by storey:"] + [
        f"- {_label(name, facts)}: {'0' if fact is None else _num(fact)}"
        for name, fact in counts.items()
    ]


def _fire(entity: str, facts: _Facts) -> list[str]:
    rated = [f for f in facts.get(f"{entity}_type.fire_rated_count") if f.value]
    if not rated:
        return [f"No {_noun(entity)} in this file has fire rating information (not available)."]
    lines = [f"{_plural(_noun(entity)).capitalize()} with a fire rating, by type:"]
    for fact in rated:
        ratings = " / ".join(_num(f) for f in facts.get(f"{entity}_type.fire_rating", fact.subject))
        lines.append(f"- {fact.subject}: {ratings} ({_num(fact)})")
    return lines


_SYNONYMS = {"outlet": ("socket", "receptacle", "wcd"), "switch": ("switch", "schakel")}


def _by_name(query: FactQuery, facts: _Facts, storey: str | None) -> str | None:
    """A thing the model has no class for, found by name among the types it counts ("light
    switches" among the electrical fixtures, duct accessories among the categories)."""
    words = [*query.words, *query.named, *_tokens(query.entity), *_SYNONYMS.get(query.entity, ())]
    found: dict[str, int] = {}
    for topic in facts.topics(""):
        if not topic.endswith(".count") or topic.startswith(
            ("space", "storey", "system", "category.")
        ):
            continue
        for fact in facts.get(topic, storey=storey):
            if fact.subject != "all" and fact.subject in _named([fact.subject], words):
                found[f"{fact.subject} ({topic.split('.')[0].replace('_', ' ')})"] = int(fact.value)
    lines = [
        f"- {name}: {count}" for name, count in sorted(found.items(), key=lambda i: (-i[1], i[0]))
    ]
    lines += _categories(query, facts, storey)
    if not lines:
        return _NoneHeld(f"No {_plural(_noun(query.entity))} found in this file ({NOT_AVAILABLE}).")
    return "\n".join(lines)


# --- disciplines, systems, materials --------------------------------------------------------


# Counts of a generic class (a flow segment, any element) restate the specific kinds' counts.
_GROUPS = re.compile(
    r"^(?:element|port|flow_\w+|distribution_\w+|energy_conversion_device|building_element_proxy)\."
)


def _discipline(query: FactQuery, facts: _Facts, storey: str | None) -> str | None:
    building = facts.one("element.count", "typed") or facts.one("element.count", "all")
    if query.by == "storey" and storey is None:  # each storey's components and categories
        blocks = [
            line
            for name, _ in _storeys_by_height(facts)
            if (said := _components(query, facts, name, building))
            for line in [said[0], *(f"  {line}" for line in said if line.startswith("- "))]
        ]
        if blocks:
            return "\n".join([*(_components(query, facts, None, None) or [])[:2], *blocks])
    lines = _components(query, facts, storey, building)
    return None if lines is None else "\n".join(lines)


def _components(
    query: FactQuery, facts: _Facts, storey: str | None, building: Fact | None
) -> list[str] | None:
    """A discipline's elements (of a storey): the counts, by category and by element class; a
    storey's opens with its share of the building's."""
    wanted = query.discipline
    kinds = [
        fact
        for topic in facts.topics("")
        if topic.endswith(".count")
        and "_type." not in topic
        and not _GROUPS.match(topic)
        and not topic.startswith(("space", "storey", "system", "category", "material"))
        for fact in facts.get(topic, "all", storey)
        if wanted is None or fact.discipline == wanted
    ]
    # a storey's share is of all its typed elements, so all its categories are listed
    categories = [
        f
        for f in facts.get("category.count", storey=storey)
        if wanted in (None, f.discipline) or storey is not None
    ]
    if not kinds and not categories:
        return None
    lines: list[str] = []
    every = facts.one("element.count", "all", storey)
    typed = facts.one("element.count", "typed", storey)
    whole = typed or every
    if storey is not None and whole is not None and building is not None:
        lines.append(
            f"{_label(storey, facts)}: {_num(whole)} components"
            f" ({_pct(float(whole.value), float(building.value))} of {_num(building)})"
        )
    if every is not None:
        lines.append(f"Distribution elements in the file: {_num(every)}")
    if typed is not None:
        lines.append(f"Components (elements with a type): {_num(typed)}")
    if categories:
        lines.append("By category:")
        lines += [
            f"- {f.subject}: {_num(f)}{_share(f, whole)}"
            for f in sorted(categories, key=lambda f: (-float(f.value), f.subject))
        ]
    if kinds:
        lines.append("By element class:")
        lines += [
            f"- {_plural(_noun(f.topic.split('.')[0])).capitalize()}: {_num(f)}"
            for f in sorted(kinds, key=lambda f: (-float(f.value), f.topic))
        ]
    return lines


def _systems(query: FactQuery, facts: _Facts) -> str | None:
    stated = facts.one("system.count", "all")
    systems = [f for f in facts.get("system.count", anywhere=True) if f.subject != "all"]
    if query.system is not None:
        discipline = SYSTEM_DISCIPLINE.get(query.system)  # type: ignore[call-overload]
        word = query.system.split("_")[0]
        systems = [f for f in systems if f.discipline == discipline or word in f.subject.lower()]
        if not systems:
            return f"No {query.system.replace('_', ' ')} system found in this file (not available)."
    if not systems:
        return None
    # system.count per subject: how many systems of that type (or name) the file defines
    lines = [f"Systems: {_num(stated)}"] if stated is not None and query.system is None else []
    lines.append(f"{len(systems)} system types:")
    lines += [
        f"- {f.subject}: {_num(f)} {_plural('system', float(f.value))}"
        for f in sorted(systems, key=lambda f: f.subject)
    ]
    return "\n".join(lines)


_CONCRETE = re.compile(r"concrete|beton|\bstb\b|\bc\d{2}/\d{2}|ortbeton|precast|in.?situ", re.I)
_INSULATION = re.compile(r"insul|dämm|daemm|isol|mineral\s*wool|eps\b|xps\b|rockwool", re.I)


def _materials(query: FactQuery, facts: _Facts) -> str | None:
    volumes = {f.subject: f for f in facts.get("material.net_volume")}
    counts = {f.subject: f for f in facts.get("material.element_count")}
    names = set(volumes) | set(counts)
    pattern = None
    if "concrete" in query.words:
        pattern = _CONCRETE
    elif "insulation" in query.words:
        pattern = _INSULATION
    if pattern is not None:
        names = {name for name in names if pattern.search(name)}
    if not names:
        return None
    lines: list[str] = []
    for name in sorted(names, key=lambda n: (-float(volumes[n].value) if n in volumes else 0, n)):
        said = [_num(volumes[name])] if name in volumes else []
        if name in counts:
            said.append(f"in {_num(counts[name])} elements")
        lines.append(f"- {name}: {', '.join(said)}")
    return "\n".join(lines)


def _baseboards(query: FactQuery, facts: _Facts, storey: str | None) -> str | None:
    """The model's own skirting boards when it has them; else that it has none, and the estimate
    facts_finish.py makes from the rooms' outlines (orchestrator's decision, 2026-11-14)."""
    modelled = [
        f"{label}: {_num(fact)}"
        for topic, label in (
            ("covering.skirting_count", "count"),
            ("covering.skirting_length", "length"),
        )
        if (fact := facts.one(topic, "all", storey)) is not None
    ]
    if modelled:
        return "Skirting boards modelled in this file: " + ", ".join(modelled)
    lines = ["Skirting boards are not modelled in this file: not available in the BIM model."]
    estimate = facts.one("space.baseboard_length", "all", storey)
    if estimate is None:
        return lines[0]
    lines.append(
        "Estimated from the room outlines minus floor-reaching doors, wet rooms excluded: "
        f"{_num(estimate)}"
    )
    if storey is None:
        for name, _ in _storeys_by_height(facts):
            if (fact := facts.one("space.baseboard_length", "all", name)) is not None:
                lines.append(f"- {name}: {_num(fact)}")
    if re.search(r"\b(?:each|every|per|by)\s+(?:room|space)", query.asked, re.I):
        lines += [
            f"  {f.subject} ({f.storey}): {_num(f)}"
            for f in facts.get("space.baseboard_length", anywhere=True)
            if f.subject != "all" and (storey is None or f.storey == storey)
        ]
    left = [f for f in facts.get("space.baseboard_excluded", anywhere=True) if f.subject != "all"]
    if left:
        lines.append("Left out: " + "; ".join(f"{f.subject} ({f.source})" for f in left))
    return "\n".join(lines)


def _ports(facts: _Facts) -> str | None:
    total, connected = facts.one("port.count", "all"), facts.one("port.connected", "all")
    if total is None or connected is None:
        return None
    rate = _pct(float(connected.value), float(total.value))
    lines = [
        f"Ports: {_num(total)}",
        f"Connected ports: {_num(connected)}",
        f"Network connectivity rate: {rate}",
    ]
    for topic, subject, label in (
        ("port.per_element", "all", "ports per element"),
        ("element.count", "typed", "elements with a type"),
        ("element.count", "all", "distribution elements"),
    ):
        if (fact := facts.one(topic, subject)) is not None:
            lines.append(f"{label}: {_num(fact)}")
    return "\n".join(lines)

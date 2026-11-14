"""The `templates` question parser (the `QuestionParser` port): a question in any of the dataset's
languages to a `Query`, with no model call.

It reads meaning from words rather than matching whole templates, so a reworded question, a
dropped hint or a typo still parses:

1. Quoted names ('x', „x“, «x», “x”) are taken out first. The words just before each one say
   what it is: a room label ("labelled", "Bezeichnung"...), one room's name ("room", "Raum",
   "ruimte"...), a building model ("model", "Modell"...) or, by default, a storey. A model's
   name only says the question is about the whole model (a sheet has one model behind it).
2. What is measured: volume, length, area or count, from cue words (first match in that order).
3. What it is about: the first subject noun of the question, after parenthesised hints and
   clauses that exclude something ("not counting separate WC rooms", "ohne Balkone") are left
   out. Showers and bathtubs named together are their combined count.
4. Filters: a room number (4.01, U1.05), an apartment letter, "indoor"/"numbered" rooms.

5. Four forms that are not dataset templates: the largest room of a type or printed label by
   area, how long a room is (its longer side), "the apartment" with no letter (the sheet's one
   dwelling), and the sheet's floor area asked plainly ("the total floor area", "the total area
   of all rooms"): Stoa's one sheet total, the net area of its indoor rooms. A gross area, a
   footprint or a building's area is not that, and stays unsupported.

A question it can't place (no measure, no subject, a measure the subject has no quantity for,
any other superlative) is `Unsupported` with the reason, never a guess.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from app.adapters.question_tables import is_table_question, parse_table
from app.core.answering.model import Query, TableQuery, Unsupported
from app.core.pipeline.model import Measure

# Quoted names, as eval/stoa_eval/families.py masks them: an apostrophe inside a word (d'escalier)
# neither opens nor closes one.
QUOTED = re.compile(r"(?<!\w)'(.+?)'(?!\w)|„([^“”]*)[“”]|«([^»]*)»|“([^”]*)”|‘([^’]*)’")  # noqa: RUF001

# Subject nouns, matched at a word start on the casefolded question. The order matters where one
# pattern contains another: a matched span is blanked out before the next pattern runs (WC rooms
# before WC seats, bathtubs before bathrooms, balconies before beams).
SUBJECTS: Sequence[tuple[str, str]] = (
    ("room:wc", r"\bwc[- ]?(?:rooms?|til\w*|räume?)\b|\btoilet rooms?\b|\bseparate wcs?\b"),
    (
        "bathtub",
        r"\bbath ?tubs?\b|\bbadewanne\w*|\bbaignoires?\b|\bvasc(?:a|he) da bagno\b|\bvasche\b"
        r"|\bkylpyam\w*|\bbañeras?\b|\bbadkuip\w*|\bwann(?:a|y|en)\b",
    ),
    (
        "toilet",
        r"\btoilets?\b(?: bowls?)?|\bwc[- ]?(?:seats?|istuin\w*)|\bwcs?\b|\bwater closets?\b"
        r"|\btoalet\w*|\binodoros?\b|\bklosett\w*",
    ),
    (
        "sink",
        r"\bsinks?\b|\bwash ?basins?\b|\blavabos?\b|\blavabi\b|\bpesu-? ja tiski\w*|\btiskial\w*"
        r"|\bpesual\w*|\bwaschbecken\b|\bwaschtisch\w*|\bumywalk\w*|\blavatori\w*|\blavaman\w*"
        r"|\bwastafel\w*|\blavabos\b",
    ),
    (
        "shower",
        r"\bshowers?\b|\bdusche\w*|\bdouches?\b|\bdocc(?:ia|e)\b|\bsuihku\w*|\bduchas?\b"
        r"|\bprysznic\w*",
    ),
    ("sauna", r"\bsauna\w*"),
    ("plan", r"\bfloors\b|\bstoreys\b|\bstories\b|\bkerros(?:ta|ten)?\b|\bfloor levels\b"),
    (
        "room:bedroom",
        r"\bbedrooms?\b|\bmakuuhuone\w*|\bschlafzimmer\b|\bchambres?\b|\bcamer[ae] da letto\b"
        r"|\bdormitorios?\b|\bslaapkamer\w*|\bsypialn\w*",
    ),
    (
        "room:kitchen",
        r"\bkitchens?\b|\bkeittiö\w*|\bküchen?\b|\bcuisines?\b|\bcucin[ae]\b|\bcocinas?\b"
        r"|\bkeuken\w*|\bkuchni\w*",
    ),
    (
        "room:bathroom",
        r"\bbathrooms?\b|\bwashrooms?\b|\bkylpy\w*|\bpesuhuone\w*|\bbadezimmer\b"
        r"|\bsalles? de bains?\b|\bbagni\b|\bbadkamer\w*|\błazien\w*",
    ),
    ("room:balcony", r"\bbalcon\w*|\bparvek\w*|\bbalkon\w*"),
    (
        "room:living",
        r"\bliving ?rooms?\b|\bolohuone\w*|\bwohnzimmer\b|\bwoonkamer\w*|\bsoggiorn[oi]\b"
        r"|\bséjours?\b",
    ),
    (
        "apartment",
        r"\bapartments?\b|\bapartamentos?\b|\bresidential units?\b|\bwohnung\w*"
        r"|\bappartement\w*|\bappartament\w*|\blogements?\b|\bhuoneisto\w*|\basunto\w*"
        r"|\bmieszka\w*",
    ),
    (
        "door",
        r"\bdoors?\b|\bdoorways?\b|\btür\w*|\bportes?\b|\bporta\b|\bdeur(?:en)?\b"
        r"|\bdrzwi\b|\bpuertas?\b|\bd[øo]re?\b|\bovi\w*|\bovea\b|\bust\b|\buks\w*|\buș[ia]\b",
    ),
    (
        "window",
        r"\bwindows?\b|\bfenster\b|\bfenêtres?\b|\bfinestr[ae]\b|\bramen\b|\braam\b"
        r"|\bok(?:ien|na|no)\b|\baken\w*|\bventanas?\b|\bvindu\w*|\bikkun\w*|\bferestre\w*",
    ),
    (
        "wall",
        r"\bwalls?\b|\bwände\b|\bwand(?:en)?\b|\bmur(?:o|os|s)?\b|\bścian\w*"
        r"|\bsein(?:a|u|ad|te)\b|\bvæg\w*|\bpare(?:te|ti)\b|\bmur[oi]\b|\bpere(?:te|ți|ti)\w*",
    ),
    (
        "column",
        r"\bcolumns?\b|\bstütze\w*|\bkolom\w*|\bpilar\w*|\bsłup\w*|\bpost(?:i|e|id)\b"
        r"|\bsøjle\w*|\bcolonn\w*|\bpilastr\w*|\bstâlp\w*",
    ),
    (
        "beam",
        r"\bbeams?\b|\bträger\w*|\bbalk(?:en)?\b|\bvigas?\b|\bbel(?:ek|ki|ka)\b|\btala\b"
        r"|\bbjælk\w*|\bpoutres?\b|\btrav[ei]\b|\bgrinz\w*",
    ),
    (
        "stair",
        r"\bstairs?\b|\bstaircases?\b|\btreppe\w*|\btrap(?:pen|per|pe)?\b|\bescaleras?\b"
        r"|\bschod\w*|\btrepp\w*|\bescaliers?\b|\bportai\w*|\bportaa\w*|\bscări\b|\bscara\b",
    ),
    (
        "slab",
        r"\bslabs?\b|\bdecken?\b|\bbodenplatte\w*|\bvloer(?:en)?\b|\blosas?\b|\bpłyt\w*"
        r"|\bdalles?\b|\bsolai\w*|\bplader?\b|\bdæk\b|\bplăci\b",
    ),
    (
        "room",
        r"\brooms?\b|\bspaces?\b|\w*räume?n?\b|\braums?\b|\bpièces?\b|\blocal[ei]?\b"
        r"|\blocales\b|\bruimtes?\b|\bpomieszcze\w*|\bruum\w*|\brum(?:met)?\b|\bhuone(?:tta|et|ita)\b"
        r"|\bsalles?\b|\bstanz[ae]\b|\bvani\b|\bîncăper\w*|\bspați\w*|\bcamer[ae]\b",
    ),
)
_SUBJECTS = [(subject, re.compile(pattern)) for subject, pattern in SUBJECTS]

# Plain word forms for typo matching: a word one edit (or one swap of neighbours) away from one of
# these names its subject, when no subject was found otherwise.
TYPO_WORDS: dict[str, str] = {
    word: subject
    for subject, words in {
        "door": "doors türen portes porte deuren puertas",
        "window": "window windows fenster fenêtres finestre ventanas ikkunaa",
        "toilet": "toilets toilet",
        "sink": "sinks washbasins lavabos",
        "shower": "shower showers duschen douches docce",
        "bathtub": "bathtub bathtubs badewannen baignoires",
        "room:bedroom": "bedroom bedrooms",
        "room:kitchen": "kitchen kitchens",
        "room:bathroom": "bathroom bathrooms",
        "room:balcony": "balcony balconies",
        "apartment": "apartment apartments wohnungen",
        "wall": "walls wände",
        "column": "columns",
        "stair": "stairs",
        "room": "rooms räume pièces",
    }.items()
    for word in words.split()
}

MEASURES: Sequence[tuple[Measure, re.Pattern[str]]] = (
    ("volume", re.compile(r"volum|m³|\bm3\b|tilavuus|objęto|\bmaht")),
    (
        "length",
        re.compile(
            r"\blength\b|l[äa]nge\b|lengte\b|longueur|lunghezza|longitud|pituus|długoś|pikkus"
            r"|\bhow long\b|\bwie lang\b|længde|lungime|\bkuinka pitkä\b|\bpitkä sivu\b"
        ),
    ),
    (
        "area",
        re.compile(
            r"\barea\b|fläche|surface|superficie|oppervlak|pinta-?ala|powierzchni|pind\b|pinda"
            r"|m²|\bm2\b|square met|neliö|areal|suprafa"
        ),
    ),
    (
        "count",
        re.compile(
            r"how many|number of|\bcount\b|\badd up\b|kuinka monta|montako|\blaske\b|wie viele"
            r"|zähle|anzahl|aus wie vielen|combien|dénombr|nombre de|quant[ie]\b|numero di"
            r"|\bconta\b|hoeveel|\btel\b|aantal|\bile\b|liczba|policz|\bmitu\b|loe kokku"
            r"|cu[aá]nt|número de|hvor mange|\bantal\b|număr"
        ),
    ),
)

# A clause with one of these words names what is left out, so its nouns are not the subject.
EXCLUDING = re.compile(
    r"\b(?:excluding|except|not counting|leaving out|without|other than|not included|ohne"
    r"|ausser|außer|ausgenommen|hors|sans|ni|sauf|esclus\w*|tranne|senza|lukuun ottamatta|pois"
    r"|ei lasketa|paitsi|excepto|sin|zonder|behalve|bez|oprócz|välja arvatud|uden)\b"
)
LABEL_BEFORE = re.compile(
    r"(?:labell?ed|bezeichnung|désignation|désignées?|denominazione|denominat[ie]|named|called"
    r"|nommées?|genannt|benannt)\s*$"
)
ROOM_BEFORE = re.compile(
    r"(?:\broom|\braums?|\bruimte|\blocal|\blocale|\bpomieszczenia|\bruumi|\brummet|\bspace"
    r"|\bpièce|\bsalle|\bîncăperii|\bcamerei|\bspațiului)\s*$"
)
MODEL = re.compile(
    r"\bmodel\b|\bmodell\w*|\bmodelo\b|\bmodelu\b|\bmudelis\b|\bmodèle\b|\bmodello\b"
    r"|\bmodellen\b"
)
ROOM_NUMBER = re.compile(r"(?<![\w.])(U?\d+\.\d+)(?![\w.])")
# A room's printed code in parentheses after its noun, "the living room (OH)": its name.
ROOM_CODE = re.compile(r"\(([A-ZÄÖÜÅ]{1,8})\)")
APARTMENT = re.compile(
    r"(?i:\b(?:apartment|apartamento|wohnung|appartement|appartamento|asunto|huoneisto"
    r"|mieszkani[ae]))\s+([A-Z])\b"
)
INDOOR = re.compile(r"indoor|innenr|intérieur|interni|numbered|nummeriert|numérot|numerat")
# The sheet's floor area asked plainly: the total of its indoor rooms, as Stoa's sheet template
# ("total net floor area ... of all numbered indoor rooms on this floor").
FLOOR_TOTAL = re.compile(r"\bfloor area\b|\btotal (?:\w+ )?area\b")
ALL_ROOMS = re.compile(r"\b(?:all|every) (?:the |of the )?(?:indoor )?rooms\b")
NOT_NET = re.compile(r"\bgross\b|\bfootprint\b|\bbrutto")
SUPERLATIVE = re.compile(r"\b(?:longest|smallest|shortest|längste|kleinste|plus petit|pisin)")
# The one superlative taken off: the largest room by area (of a type, or of a printed label).
LARGEST = re.compile(r"\b(?:largest|biggest|grösste|größte|plus grand|maggiore|suurin)")
QUALIFIED_WALL = re.compile(
    r"exterior|external|outer|interior|internal|load-?bearing|au(?:ß|ss)en|extérieur|intérieur"
    r"|estern|ulko|sisä"
)
SCHEDULE = re.compile(r"schedul|finish|\blisted in\b|zeitplan|\bliste\b|tableau")
# A breakdown, a list, several values asked at once ("what are the key metrics...") or a place
# named without quotes is not one quantity of the sheet.
BREAKDOWN = re.compile(
    r"\beach\b|\bper (?:type|floor|storey|level|room)\b|\bby (?:type|floor|storey|level|size"
    r"|width|system|function)\b|breakdown|distribut|grouped|\btypes\b|\bdifferent\b|\bdistinct\b"
    r"|proportion|\bwhich\b|\bwhere\b|\blist\b|\bwhat are\b|\bmetrics\b|statistic"
)
PLACE = re.compile(
    r"\b(?:ground|first|second|third|fourth|fifth|sixth|top|upper|lower|north|south|east|west)\b"
    r"|\bhouse [a-z]\b|\bfa[cç]ade\b|\bwing\b|\bplan \d+[a-z]?\b"
)
CONDITION = re.compile(  # "rooms that have...": a subset we can't pick
    r"\b(?:rooms?|spaces?|doors?|windows?|walls?)\s+(?:have|has|with|that|containing)\b"
)
BUILDING = re.compile(r"\bbuilding\b|\bproject\b")  # the whole model, not this sheet
# In English the counted thing comes right after these words ("how many X-ray rooms" is not a
# count of rooms); the words in FILLER may come between.
ENGLISH_COUNT = re.compile(r"\b(?:how many|number of|count of|count the|count)\s+")
FILLER = frozenset({"the", "separate", "all"})
PARENTHESES = re.compile(r"\([^()]*\)")
CLAUSES = re.compile(r"[,;:.?!¿¡]")
WORD = re.compile(r"[^\W\d_]+")

AREA_SUBJECTS = frozenset({"room", "apartment", "wall"})
ELEMENT_SUBJECTS = frozenset({"wall", "slab", "column", "beam", "stair", "door", "window"})
# The element classes a sum of lengths, areas or volumes is taken off for (rules.MEASURED).
ELEMENT_MEASURES: dict[Measure, tuple[str, ...]] = {
    "area": ("wall",),
    "length": ("wall",),
    "volume": ("wall", "slab"),
}


@dataclass(frozen=True)
class _Quoted:
    text: str
    role: str  # label, name, model, aside (in parentheses after a room number) or storey


class TemplateParser:
    """The `QuestionParser` port, from words and quoted names (see the module docstring)."""

    def parse(self, text: str) -> Query | TableQuery | Unsupported:
        raw = unicodedata.normalize("NFC", " ".join(text.split()))
        quoted = _quoted(raw)
        bare = QUOTED.sub(" _ ", raw)  # the question without its quoted names
        lower = bare.casefold()
        if is_table_question(raw):
            return parse_table(raw)
        if SCHEDULE.search(lower):
            return Unsupported(reason="schedule (table) questions are not supported yet")
        if SUPERLATIVE.search(lower):
            return Unsupported(reason="a superlative (longest, largest...) is not a takeoff")
        if BREAKDOWN.search(lower):
            return Unsupported(reason="a breakdown or list is not one quantity")
        if PLACE.search(lower):
            return Unsupported(reason="a place named without quotes (ground floor, north facade)")
        if CONDITION.search(lower):
            return Unsupported(reason="a condition on the items (rooms that have...)")
        measure: Measure | None = next((m for m, cue in MEASURES if cue.search(lower)), None)
        if measure is None:
            return Unsupported(reason="no count, area, length or volume asked for")
        body, hits = _subjects(lower)
        model = any(q.role == "model" for q in quoted) or BUILDING.search(lower) is not None
        floor_total = (
            measure == "area"
            and not model
            and NOT_NET.search(lower) is None
            and (FLOOR_TOTAL.search(lower) is not None or ALL_ROOMS.search(lower) is not None)
        )
        if not hits and not floor_total:
            return Unsupported(reason="no element, room or apartment named")
        if hits and not _counted_thing_named(body, hits):
            return Unsupported(reason="the thing counted is not an element, room or apartment")
        subjects = list(dict.fromkeys(subject for _, subject in hits)) or ["room"]
        label = next((q.text for q in quoted if q.role == "label"), None)
        name = next((q.text for q in quoted if q.role == "name"), None)
        storey = next((q.text for q in quoted if q.role == "storey"), None)
        if name is None and (number := ROOM_NUMBER.search(bare)):
            name = number.group(1)
        apartment = APARTMENT.search(bare)
        common = {"storey": storey, "model": model}
        largest = LARGEST.search(lower) is not None
        if largest and measure != "area":
            return Unsupported(reason="only the largest room by area is taken off")
        if measure == "count":
            subject = "shower+bathtub" if {"shower", "bathtub"} <= set(subjects) else subjects[0]
            if label is not None and subject.startswith("room"):
                return Query(measure="count", subject="room", label=label, **common)
            return Query(measure="count", subject=subject, **common)
        if len({s for s in subjects if s in ELEMENT_SUBJECTS}) > 1:
            return Unsupported(reason="one sum over several element classes is not taken off")
        if measure == "area" and apartment is not None:
            return Query(measure="area", subject="apartment", apartment=apartment.group(1))
        subject = next((s for s in subjects if s in AREA_SUBJECTS), subjects[0])
        code = ROOM_CODE.search(bare)
        if largest:
            return _largest_room(subject, label or (code.group(1) if code else None), common)
        if measure == "area" and subject == "apartment":  # "the apartment": the sheet's dwelling
            return Query(measure="area", subject="apartment", **common)
        if measure == "length" and subject.startswith("room"):
            return _room_side(subjects, subject, name or (code.group(1) if code else None), common)
        if measure == "area" and subject.startswith("room") and code and not (name or label):
            return Query(measure="area", subject="room", name=code.group(1), **common)
        if subject == "wall" and QUALIFIED_WALL.search(lower):
            return Unsupported(reason="only all walls together have a length, area or volume")
        if measure == "area" and subject == "room":
            if name is not None:
                return Query(measure="area", subject="room", name=name, **common)
            if label is not None:
                return Query(measure="area", subject="room", label=label, **common)
            if INDOOR.search(lower):
                return Query(measure="area", subject="room", indoor=True, **common)
            if storey is not None:
                return Query(measure="area", subject="room", **common)
            if floor_total and (not hits or ALL_ROOMS.search(lower)):
                return Query(measure="area", subject="room", indoor=True, **common)
            return Unsupported(reason="an area of rooms without saying which rooms")
        if subject in ELEMENT_MEASURES.get(measure, ()):
            return Query(measure=measure, subject=subject, **common)
        return Unsupported(reason=f"no {measure} is taken off for {subject}")


def _largest_room(subject: str, label: str | None, common: dict) -> Query | Unsupported:
    """The largest room with a printed label ("the largest bedroom (MH)"), else of a type."""
    if not subject.startswith("room"):
        return Unsupported(reason="only the largest room by area is taken off")
    if label is not None:
        return Query(measure="area", subject="room", label=label, largest=True, **common)
    if subject != "room":
        return Query(measure="area", subject=subject, largest=True, **common)
    return Unsupported(reason="the largest of rooms without saying which rooms")


def _room_side(
    subjects: Sequence[str], subject: str, name: str | None, common: dict
) -> Query | Unsupported:
    """How long a room is: its longer side, for the room with that name or the one room of
    that type. A length that also names an element class is that class's length, not a room's."""
    if any(s in ELEMENT_SUBJECTS for s in subjects):
        return Unsupported(reason="the length of an element class within a room is not taken off")
    if name is not None:
        return Query(measure="length", subject="room", name=name, **common)
    if subject != "room":
        return Query(measure="length", subject=subject, **common)
    return Unsupported(reason="the length of rooms without saying which room")


def _quoted(raw: str) -> list[_Quoted]:
    found: list[_Quoted] = []
    for match in QUOTED.finditer(raw):
        inner = next(group for group in match.groups() if group is not None).strip()
        before = raw[max(0, match.start() - 40) : match.start()].casefold().rstrip()
        if before.endswith("("):
            role = "aside"
        elif LABEL_BEFORE.search(before):
            role = "label"
        elif ROOM_BEFORE.search(before):
            role = "name"
        elif MODEL.search(before[-20:]):
            role = "model"
        else:
            role = "storey"
        found.append(_Quoted(text=inner, role=role))
    return found


def _subjects(lower: str) -> tuple[str, list[tuple[int, str]]]:
    """The question without parenthesised hints, and the subject nouns in it with their
    positions, in order, leaving out clauses that say what is excluded."""
    body = PARENTHESES.sub(" ", lower)
    hits: list[tuple[int, str]] = []
    offset = 0
    for clause in CLAUSES.split(body):
        start = offset
        offset += len(clause) + 1
        if EXCLUDING.search(clause):
            continue
        rest = clause
        for subject, pattern in _SUBJECTS:
            for match in pattern.finditer(rest):
                hits.append((start + match.start(), subject))
            rest = pattern.sub(lambda m: " " * len(m.group()), rest)
    if not hits:
        hits = [
            (match.start(), subject)
            for match in WORD.finditer(body)
            if (subject := _typo(match.group())) is not None
        ]
    return body, sorted(hits)


def _counted_thing_named(body: str, hits: list[tuple[int, str]]) -> bool:
    """False when an English count names something else first: the first word after "how many"
    (FILLER words skipped) must be where a subject noun starts."""
    cue = ENGLISH_COUNT.search(body)
    if cue is None:
        return True
    starts = {position for position, _ in hits}
    for word in WORD.finditer(body, cue.end()):
        if word.start() in starts:  # a subject may start with a FILLER word ("separate WCs")
            return True
        if word.group() not in FILLER:
            return False
    return True


def _typo(word: str) -> str | None:
    if len(word) < 5:
        return None
    return next((s for known, s in TYPO_WORDS.items() if _one_edit(word, known)), None)


def _one_edit(a: str, b: str) -> bool:
    """One insertion, deletion, substitution or swap of neighbours apart (not equal)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        i, j = diff[0], diff[-1]
        return len(diff) == 2 and j == i + 1 and a[i] == b[j] and a[j] == b[i]
    short, long = (a, b) if len(a) < len(b) else (b, a)
    i = next((k for k in range(len(short)) if short[k] != long[k]), len(short))
    return short[i:] == long[i + 1 :]

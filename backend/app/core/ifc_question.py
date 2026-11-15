"""A free-text question about a building model or a discipline drawing as a lookup over its fact
sheet (app/core/ifc_facts.py), whatever read the facts (an IFC model, a sheet read by vision).

Keyword rules, no model: the thing asked about (`entity`, a fact topic's stem: "wall", "space",
"pipe_segment"), what of it (`measures`: "count", "area", "thickness", "material"...), which part
("external", "load_bearing"), how it is broken down (by type, storey, function, system), and
how the numbers are put together (a list, a total, the largest, a share). The storey and the
space names are kept as the question words them; the answer resolves them against the sheet,
since only the sheet knows that "level 1" is "1.etg" there.

A question about what a building model does not hold (a cost, a lifespan, an energy rating) is read
as `unavailable`: the answer says so instead of a number. English only, as the dev questions.
"""

import re
from typing import Literal

from app.core.discipline import discipline_from_question, system_from_question
from app.core.ifc_facts import Discipline
from app.core.model import Frozen

Aggregate = Literal["list", "total", "max", "min", "average", "share", "unavailable"]
By = Literal["type", "storey", "function", "system", "category"]

# A room named by what it is for ("toilet rooms", "x-ray room") asks about rooms, not toilets.
_ROOM_OF = re.compile(r"\b[\w-]+\s+(?:rooms?|spaces?|areas?)\b")
# (entity, words): the most specific first; the first in the question wins among elements.
_ENTITIES: tuple[tuple[str, str], ...] = (
    ("curtain_wall", r"curtain\s*walls?"),
    ("pipe_fitting", r"pipe\s*fittings?"),
    ("duct_fitting", r"duct\s*fittings?"),
    ("duct_accessory", r"duct\s*accessor(?:y|ies)"),
    ("pipe_segment", r"pip(?:e|es|ing)|plumbing\s*runs?"),
    ("duct_segment", r"ducts?|ductwork"),
    ("air_terminal", r"air\s*terminals?|diffusers?|grilles?"),
    ("light_fixture", r"light(?:ing)?\s*fixtures?|luminaires?|lights?|lamps?"),
    ("switch", r"(?:light\s*)?switch(?:es)?"),
    ("outlet", r"outlets?|receptacles?|sockets?"),
    (
        "sanitary_terminal",
        r"sanitary|plumbing\s*fixtures?|toilets?|wcs?|urinals?|(?:wash)?basins?|sinks?|lavator\w*",
    ),
    ("valve", r"valves?"),
    ("pump", r"pumps?"),
    ("fan", r"fans?"),
    ("boiler", r"boilers?"),
    ("heat_exchanger", r"radiators?|heaters?"),
    ("cable_carrier_segment", r"cable\s*trays?|conduits?"),
    ("junction_box", r"junction\s*box(?:es)?"),
    ("fire_suppression_terminal", r"sprinklers?|fire\s*extinguishers?"),
    ("waste_terminal", r"waste\s*terminals?|drains?"),
    ("damper", r"dampers?"),
    ("controller", r"controllers?|thermostats?"),
    ("port", r"ports?|connectivity"),
    ("pile", r"piles?"),
    ("alarm", r"smoke\s*detectors?|alarms?|detectors?"),
    ("electric_appliance", r"electrical\s*(?:panels?|appliances?|equipment)|panelboards?"),
    (
        "discipline",
        r"(?:electrical|structural|mep|plumbing|data|communication|technical|heating"
        r"|ventilation|hvac)\s+(?:components?|elements?|equipment|devices?|distribution)",
    ),
    ("door", r"doors?|doorknobs?|entrances?"),
    ("window", r"windows?|glazing"),
    ("roof", r"roofs?|roofing"),
    ("stair", r"stairs?|staircases?|stairways?|steps|vertical\s*circulation"),
    ("ramp", r"ramps?"),
    ("railing", r"railings?|handrails?|guardrails?"),
    ("baseboard", r"skirting(?:\s*boards?)?|baseboards?"),
    ("covering", r"ceilings?|coverings?|floor(?:ing)?\s*finish\w*|flooring|tiles?|tiling"),
    ("furniture", r"furniture|furnishings?"),
    ("column", r"columns?"),
    ("beam", r"beams?"),
    ("member", r"members?"),
    ("footing", r"foundations?|footings?"),
    ("slab", r"slabs?"),
    ("wall", r"walls?|fa[cç]ades?"),
    ("equipment", r"mechanical\s+equipment|air\s+handling\s+units?|ahus?"),
    ("system", r"mep|systems?|hvac"),
)
# Asked of the whole model, never of an element: what the file says about itself.
_PROJECT = re.compile(
    r"software|program\b|modell?ing\s+(?:standard|program)|\bifc\s+(?:standard|version|schema)"
    r"|project\s+information|location\s+data|(?:site|project|building)\s+location|address"
    r"|coordinates|phas(?:e|ing)|building\s+name",
    re.I,
)
_STOREY_ENTITY = re.compile(
    r"floor.to.floor|heights?\s+of\s+(?:the\s+)?(?:building\s+)?(?:levels?|storeys?|floors?)"
    r"|elevations?|(?:levels?|storeys?|floors?)\s+(?:are|does|in\s+the\s+building)\b"
    r"|how\s+many\s+(?:levels?|storeys?|stor(?:y|ies)|floors)",
    re.I,
)
# A ceiling's or a room's height is the space's: the file states it there, not on the ceiling.
_ROOM_HEIGHT = re.compile(
    r"(?:ceiling|room|space)\s+heights?|heights?\s+of\s+(?:the\s+)?(?:ceiling|room|space)s?", re.I
)
_SPACE = re.compile(
    r"\b(?:spaces?|rooms?|units?|areas?|offices?|bedrooms?|bathrooms?|restrooms?|kitchens?"
    r"|gfa|ufa|footprint|apartments?|zones?)\b",
    re.I,
)
_MEASURES: tuple[tuple[str, str], ...] = (
    ("count", r"how\s+many|number\s+of|counts?\b|quantit(?:y|ies)|how\s+much|inventory"),
    ("area", r"area|square\s+met|sq\.?\s*m|m2|m²|gfa|ufa|footprint"),
    ("length", r"length|\blong\b|linear|metres\s+of|meters\s+of|skirting"),
    ("volume", r"volume|cubic"),
    ("thickness", r"thick"),
    ("width", r"width|\bwide\b"),
    ("height", r"(?:ceiling\s+)?height|\btall\b|\bhigh\b"),  # "ceiling" names no room
    ("elevation", r"elevation"),
    ("depth", r"depth|\bdeep\b"),
    ("material", r"material|made\s+of|composition|layers?|construction|concrete|insulation|finish"),
    ("fire_rating", r"fire[\s-]*(?:rat|resist)"),
    ("glazing", r"glazing\s+types?|(?:type|kind)s?\s+of\s+glazing|single\s+or\s+double"),
    ("size", r"\bsizes?\b|sizing|dimension|specification"),
)
_BY: tuple[tuple[By, str], ...] = (
    ("function", r"by\s+(?:space\s+)?function|functions?\b|room\s+types?|space\s+types?|usage"),
    ("storey", r"(?:by|per|each|every|on\s+each)\s+(?:building\s+)?(?:level|floor|storey|story)"
     r"|by\s+storey|grouped\s+by\s+(?:level|floor)"
     r"|distribut\w*\s+(?:by|across|over)\s+(?:the\s+)?(?:building\s+)?(?:level|floor)"),
    ("system", r"(?:by|per|each)\s+(?:mep\s+)?system|system\s+types?|systems?\s+they\s+belong"),
    ("category", r"categor"),
    ("type", r"\btypes?\b|\bkinds?\b|which\s+\w+s\b|breakdown|distinct|different"),
)  # fmt: skip
_AGGREGATES: tuple[tuple[Aggregate, str], ...] = (
    ("average", r"average|mean\b|typical"),
    ("max", r"largest|biggest|maximum|max\b|highest|tallest|widest|longest|furthest"),
    ("min", r"smallest|minimum|min\b|lowest|narrowest|shortest"),
    ("share", r"percent|proportion|ratio|share\b|%"),
    ("total", r"total|sum\b|combined|overall|altogether|in\s+all\b"),
)
# What a building model does not hold: the dataset answers these "not available". Words, not
# answers: costs, lifespans, ratings of performance, loads, schedules.
_UNAVAILABLE = re.compile(
    r"\bcosts?\b|price|lifespan|life\s*span|warranty|maintenance\s+schedule|energy\s+consumption"
    r"|embodied\s+carbon|recycl|thermal\s+bridge|air\s*tightness|solar\s+heat|u[-\s]?value"
    r"|sound\s+transmission|\bstc\b|live\s+load|electrical\s+load|efficiency\s+rating"
    r"|renewable|occupan\w+\s+(?:load|capacity)|acoustic|ventilation\s+req",
    re.I,
)
# Asked for a judgement or an estimate over what the model stores: the answer says the model
# does not hold it, then gives the facts it would rest on.
_DERIVED = re.compile(
    r"estimat|potential|fire\s+exits?|emergency|escape|ratio\s+of|clinical|accessib|complian"
    r"|adjacent|connected\s+to|access\s+to\s+outdoor|nearest|distance",
    re.I,
)
_PARTS: tuple[tuple[str, str], ...] = (
    ("non_load_bearing", r"non[\s-]*load[\s-]*bearing|non[\s-]*structural"),
    ("load_bearing", r"load[\s-]*bearing|structural\s+walls?|main\s+structural"),
    ("external", r"exterior|external|outer|outside|fa[cç]ade|envelope"),
    ("internal", r"interior|internal|inner|inside|partition"),
)
_ORDINALS = {
    "ground": 0, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
}  # fmt: skip
_STOREY = re.compile(
    r"\b(?:on|of|in|at|for)\s+(?:the\s+)?(?P<phrase>"
    r"(?:level|floor|storey|story)\s+\d+"
    r"|\d+(?:st|nd|rd|th)?\s*\.?\s*(?:floor|level|storey|story|og|etg|etage|sal)"
    r"|(?:ground|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh"
    r"|twelfth|top|roof|attic)\s*(?:floor|level|storey|story)"
    r"|(?:ground|basement|underground)(?:\s*(?:floor|level|storey|story))?"
    r"|og\s*\d+|eg\b)",
    re.I,
)
# Two storeys a height is between: "between the ground floor and first floor".
_LEVEL = (
    r"(?:(?:level|floor|storey|story)\s+\d+|\d+(?:st|nd|rd|th)?"
    r"|ground|basement|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
    r"|eleventh|twelfth|top|roof)(?:\s+(?:floor|level|storey|story))?"
)
_BETWEEN = re.compile(
    rf"\bbetween\s+(?:the\s+)?(?P<a>{_LEVEL})\s+and\s+(?:the\s+)?(?P<b>{_LEVEL})\b", re.I
)
# An IFC GlobalId: 22 characters of its base-64 alphabet, mixed case and a digit in practice.
_GUID = re.compile(r"(?<![\w$])[0-9A-Za-z_$]{22}(?![\w$])")
_WORD = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*")
# A place inside the sheet the question counts in: "in the plumbing room", "in room 1-15", "in
# the left half of the sheet", "does the cafeteria have". "On the plumbing plan", "in this
# drawing", "in H-101" name the sheet itself (big QA R1 services: a picture's sheet total was
# given for one room)
_IN_PLACE = re.compile(
    r"\b(?:in|inside|within)\s+(?:(?:the|this|that|these|those|a|an|one|each|every)\s+)?"
    r"(?P<place>[^\W_][\w'\u2019-]*(?:\s+(?!(?:of|on|and|or|with|at|for|in|per|that|which|where|"
    r"are|is|has|have|had|carry|carries|show|shows|list|lists|contain|contains)\b)"
    r"[^\W_][\w'\u2019-]*)*)"
    r"|\bdoes\s+(?:the|this|that)\s+(?P<has>[^\W_][\w'\u2019 -]*?)\s+(?:have|contain|hold)\b",
    re.I,
)
_SHEET_WORDS = frozenset(  # the whole sheet, a table on it, or the unit asked in ("in m²")
    """plan plans floorplan drawing drawings sheet sheets page pages picture pictures photo photos
    image images scan scans layout diagram map legend model file building project total all it
    them whole entire set schedule schedules table tables m m² m2 m³ m3 mm cm km sqm metre metres
    meter meters ft feet units system systems network circuit circuits""".split()  # noqa: SIM905
)
# "in Plan image 1", "in P-101 E00 plumbing.png": the drawing by its name or file (review-721 S1)
_FILE_END = re.compile(r"\.(?:png|jpe?g|pdf|tiff?|svg|webp|ifc|dwg|dxf)\b", re.I)
_SHEET_CODE = re.compile(r"[^\W\d_]{1,3}-?\d+[^\W\d_]?")  # H-101, P101, E00: a drawing's own code
_STOP = frozenset(
    """a an and any are as at be by can could do does each for from give have how i in include
    including is it its me model of on or please provide the their there these they this to
    used what where which with within you""".split()  # noqa: SIM905 (a word list reads better as text)
)


# Words of how a question is put, never a name on the sheet.
_GENERIC = frozenset(
    """all available breakdown building buildings categorized clinic complete corresponding
    defined detailed details different distribution each element elements every exist found
    general give grouped house individual information installed list located location model
    modelled names present project provide respective shown specified specific there total used
    where well level levels floor floors storey storeys""".split()  # noqa: SIM905 (as above)
)


class FactQuery(Frozen):
    """What a question asks of a model's facts. `family` names it for the scores."""

    entity: str  # a fact topic's stem: "wall", "space", "pipe_segment", "project", "storey"
    measures: tuple[str, ...] = ("count",)
    part: str = "all"  # "all", "external", "internal", "load_bearing", "non_load_bearing"
    by: By | None = None
    aggregate: Aggregate = "list"
    storey: str | None = None  # as the question words it: "level 3", "ground floor", "2.og"
    words: tuple[str, ...] = ()  # the question's content words, matched to names on the sheet
    system: str | None = None  # discipline.System
    discipline: Discipline | None = None
    asked: str = ""  # the question's text, for the answer to name what it could not find
    named: tuple[str, ...] = ()  # the words the entity was read from: "receptacles"
    guid: str | None = None  # an element's GlobalId the question names
    between: tuple[str, str] | None = None  # two storeys as the question words them
    yes_no: bool = False  # "Are the interior walls load bearing?"
    how_many: bool = False  # asks for a number of things: "How many dampers ...", "number of"
    derived: bool = False  # asks for an estimate or a judgement the model does not store
    place: str | None = None  # a place inside the sheet it counts in (_IN_PLACE), as worded

    def family(self) -> str:
        if self.aggregate == "unavailable":
            return "unavailable"
        return f"{self.entity}.{self.measures[0]}"


# Count wording: a file holding none of the thing is no answer to it (answering/facts.py)
_HOW_MANY = re.compile(r"\bhow\s+many\b|\b(?:total\s+)?(?:number|count)\s+of\b")


def parse_ifc_question(text: str) -> FactQuery | None:
    """The lookup a question asks for, or None when no rule reads it."""
    said = " ".join(text.split())
    lower = said.lower()
    storey_match = _STOREY.search(said)
    storey = None if storey_match is None else storey_match["phrase"].lower()
    rest = lower if storey_match is None else lower.replace(storey_match[0].lower(), " ")
    rest = re.sub(r"\bunit\s+counts?\b", "counts", rest)  # how many, not dwelling units
    base = FactQuery(
        entity="project",
        storey=storey,
        system=system_from_question(said),
        discipline=discipline_from_question(said),
        asked=said,
        # "Can you provide ..." is a request, not a yes/no question
        yes_no=re.match(r"(?:are|is|does|do|has|have|can)\b(?!\s+you\b)", lower) is not None,
        derived=_DERIVED.search(said) is not None,
        how_many=_HOW_MANY.search(lower) is not None,
        place=_place(rest),
        guid=_guid(said),
        between=None
        if (pair := _BETWEEN.search(said)) is None
        else (pair["a"].lower(), pair["b"].lower()),
    )
    if _UNAVAILABLE.search(said):
        return base.model_copy(update={"aggregate": "unavailable"})
    if _PROJECT.search(said):
        return base.model_copy(update={"measures": ("text",)})
    entity = (
        "space"
        if _ROOM_HEIGHT.search(rest)
        else "port"
        if re.search(r"connectivity|connection\s+rate|connected\s+ports", rest)
        else _entity(rest)
    )
    if entity is None:
        return None
    own = dict(_ENTITIES).get(entity)
    measures = tuple(name for name, words in _MEASURES if re.search(words, rest)) or ("count",)
    if entity == "space" and "size" in measures:
        measures = ("area", *measures)
    return base.model_copy(
        update={
            "entity": entity,
            "measures": measures,
            "part": next((name for name, words in _PARTS if re.search(words, rest)), "all"),
            "by": next((name for name, words in _BY if re.search(words, rest)), None),
            "aggregate": next(
                (name for name, words in _AGGREGATES if re.search(words, rest)), "list"
            ),
            "words": _subject_words(rest, entity),
            "named": tuple(
                w for w in _WORD.findall(rest) if own is not None and re.fullmatch(own, w)
            ),
        }
    )


def _place(text: str) -> str | None:
    """The first place inside the sheet the question counts in, or None when every "in the ..."
    names the sheet, a system or the drawing itself: a sheet word or the drawing's code in it ("the
    heating plan", "the waste water system", "Plan image 1", "P-101 E00"), or a file name."""
    for found in _IN_PLACE.finditer(text):
        place = found["place"] or found["has"]
        sheet = any(w in _SHEET_WORDS or _SHEET_CODE.fullmatch(w) for w in place.split())
        if not sheet and not _FILE_END.match(text, found.end()):
            return place
    return None


def _entity(text: str) -> str | None:
    if _STOREY_ENTITY.search(text):
        return "storey"
    elements = _ROOM_OF.sub(" ", text)
    found = [
        (match.start(), -len(match[0]), entity)
        for entity, words in _ENTITIES
        if (match := re.search(rf"\b(?:{words})\b", elements)) is not None
    ]
    if found:
        *_, entity = min(found)  # the first in the question; of two there, the longer
        if entity == "system" and re.search(r"\bcomponents?\b", text):
            return "discipline"  # a system's components: the elements, by discipline
        if entity != "system" or not _SPACE.search(text):
            return entity
    if re.search(r"concrete|insulation|materials?\b", text):
        return "material"
    if _SPACE.search(text) or re.search(r"composition|layout|description|floor\s+area", text):
        return "space"
    if re.search(r"\b(?:levels?|storeys?|stor(?:y|ies)|floors)\b", text):
        return "storey"
    return None


def _guid(text: str) -> str | None:
    return next(
        (
            word
            for word in _GUID.findall(text)
            if re.search(r"\d", word) and re.search(r"[a-z]", word) and re.search(r"[A-Z]", word)
        ),
        None,
    )


def _subject_words(text: str, entity: str) -> tuple[str, ...]:
    """The words left once the rules' own words are taken out: what names a subject on the
    sheet ("kitchen", "meeting", "concrete")."""
    measures = [words for name, words in _MEASURES if name != "material" or entity != "material"]
    patterns = [*measures, *(words for _, words in (*_PARTS, *_BY, *_AGGREGATES))]
    patterns.append(r"spaces?|rooms?|units?|areas?|zones?")  # a kind of room stays: "offices"
    if entity == "space":
        patterns.append(r"ceilings?")  # its height is the room's; a ceiling names no room
    patterns += [words for name, words in _ENTITIES if name == entity]
    for pattern in patterns:
        text = re.sub(rf"\b(?:{pattern})\w*", " ", text, flags=re.I)
    return tuple(w for w in _WORD.findall(text) if w not in _STOP and w not in _GENERIC)


def storey_number(phrase: str) -> int | None:
    """The storey a phrase names, as a number: 0 for the ground floor, -1 below it."""
    if re.search(r"basement|underground", phrase):
        return -1
    if (digits := re.search(r"\d+", phrase)) is not None:
        return int(digits[0])
    if re.fullmatch(r"eg", phrase.strip()):
        return 0
    word = re.match(r"[a-z]+", phrase)
    return None if word is None else _ORDINALS.get(word[0])

"""Which discipline a model, a sheet or a question is about: one taxonomy (ifc_facts.Discipline)
for files and questions, so a question goes to the facts of the model that can answer it.

- A model, by the IFC classes it holds (`discipline_from_census`, counts from
  app/adapters/ifc_model/census.py). A model may carry several disciplines, so the answer is a
  ranking with shares.
- A 2D sheet, by its title-block text (`discipline_from_title`), and a question, by its words
  (`discipline_from_question`, `system_from_question`). Both are rules over words in the
  languages the dataset asks in (EN, FI, DE, SV, NL, ES, FR, IT, ET), and both say None when
  unsure: two disciplines named, or none.

Words come in two tiers. A strong word names a discipline or a system ("ventilation", "Heizung",
"sprinkler", "load-bearing"). A weak one names a thing several disciplines draw: a pipe (plumbing
or heating), a column (structural or architecture), a room or a door (architecture, also the
background of every MEP plan). Strong words decide; weak ones only when no strong word is there.
"""

import re
from collections.abc import Mapping
from typing import Literal

from app.core.ifc_facts import Discipline

System = Literal[
    "heating",
    "cooling",
    "hot_water",
    "cold_water",
    "sewage",
    "rainwater",
    "gas",
    "supply_air",
    "exhaust_air",
    "return_air",
    "outdoor_air",
    "sprinkler",
]

SYSTEM_DISCIPLINE: dict[System, Discipline] = {
    "heating": "heating",
    "cooling": "ventilation",  # chillers and cooling coils: the air side's plant (no "cooling")
    "hot_water": "plumbing",
    "cold_water": "plumbing",
    "sewage": "plumbing",
    "rainwater": "plumbing",
    "gas": "plumbing",
    "supply_air": "ventilation",
    "exhaust_air": "ventilation",
    "return_air": "ventilation",
    "outdoor_air": "ventilation",
    "sprinkler": "fire",
}

# --- models: IFC class counts ----------------------------------------------------------------

# A class name is matched by its stem: lower case, no "Ifc", no "Type"/"Style" (IFC2x3 types),
# no "StandardCase"/"ElementedCase". So IfcPipeSegmentType and IfcPipeSegment both count.
_STEMS: dict[Discipline, str] = {
    "architecture": "door window space covering furnishingelement furniture "
    "systemfurnitureelement railing stair stairflight ramp rampflight curtainwall roof "
    "transportelement shadingdevice",
    "structural": "footing pile",  # and every structural*, reinforc*, tendon* (_stem_of)
    "plumbing": "sanitaryterminal wasteterminal interceptor stackterminal",
    "heating": "spaceheater electricheater boiler burner heatexchanger",
    "ventilation": "ductsegment ductfitting ductsilencer airterminal airterminalbox damper "
    "fan filter airtoairheatrecovery coil humidifier evaporativecooler evaporator condenser "
    "chiller coolingtower unitaryequipment",
    "electrical": "cablesegment cablefitting cablecarriersegment cablecarrierfitting "
    "lightfixture lamp outlet switchingdevice electricdistributionboard "
    "electricdistributionpoint junctionbox protectivedevice protectivedevicetrippingunit "
    "electricappliance electricgenerator electricmotor motorconnection transformer "
    "electricflowstoragedevice electrictimecontrol audiovisualappliance "
    "communicationsappliance solardevice",
    "fire": "firesuppressionterminal alarm",
    "site": "geographicelement civilelement road bridge railway alignment earthworkscut "
    "earthworksfill pavement course kerb marinefacility marinepart mooringdevice bridgepart "
    "roadpart railwaypart facilitypart alignmentsegment alignmenthorizontalsegment "
    "alignmentverticalsegment referent sign signal navigationelement",
}
_SPECIFIC: dict[str, Discipline] = {
    stem: discipline for discipline, stems in _STEMS.items() for stem in stems.split()
}
_MEP: tuple[Discipline, ...] = ("plumbing", "heating", "ventilation", "electrical", "fire")
# Classes several disciplines hold: their count is shared out among the candidates in proportion
# to what the model already scored for each (the first candidate when it scored none). In this
# order, so the generic IFC2x3 flow classes come last and follow the pipes shared out before.
_SHARED: tuple[tuple[frozenset[str], tuple[Discipline, ...]], ...] = (
    (frozenset({"wall", "slab", "plate"}), ("architecture", "structural")),
    (frozenset({"beam", "column", "member"}), ("structural", "architecture")),
    (
        frozenset({"pipesegment", "pipefitting", "valve", "pump", "tank", "flowmeter"}),
        ("plumbing", "heating", "fire"),
    ),
    (
        frozenset(
            [
                *("flowsegment", "flowfitting", "flowterminal", "flowcontroller"),
                *("energyconversiondevice", "flowmovingdevice", "flowstoragedevice"),
                *("flowtreatmentdevice", "distributionflowelement", "distributionchamberelement"),
                *("sensor", "actuator", "controller", "unitarycontrolelement", "flowinstrument"),
            ]
        ),
        _MEP,
    ),
)


def _stem_of(ifc_class: str) -> str:
    stem = ifc_class.lower().removeprefix("ifc")
    for end in ("standardcase", "elementedcase", "type", "style"):
        stem = stem.removesuffix(end)
    if stem.startswith(("structural", "reinforc", "tendon")):
        return "footing"  # any structural class: counts as structural like a footing
    return stem


def discipline_from_census(counts: Mapping[str, int]) -> list[tuple[Discipline, float]]:
    """IFC class counts (`{"IfcPipeSegment": 12, ...}`, any case) → the model's disciplines,
    most first, with their shares of the classes that tell (summing to 1). Empty when no class
    tells (only geometry, proxies or spatial structure)."""
    stems: dict[str, int] = {}
    for ifc_class, count in counts.items():
        stems[_stem_of(ifc_class)] = stems.get(_stem_of(ifc_class), 0) + count
    scores: dict[Discipline, float] = {}
    for stem, count in stems.items():
        if stem in _SPECIFIC:
            scores[_SPECIFIC[stem]] = scores.get(_SPECIFIC[stem], 0) + count
    if stems.get("building", 0) > 1:  # many buildings in one model: a city or site model
        scores["site"] = scores.get("site", 0) + stems["building"] - 1
    for shared, candidates in _SHARED:
        total = sum(stems.get(stem, 0) for stem in shared)
        if not total:
            continue
        known = {d: scores.get(d, 0.0) for d in candidates}
        mass = sum(known.values())
        for discipline in candidates:
            part = known[discipline] / mass if mass else float(discipline == candidates[0])
            if part:
                scores[discipline] = scores.get(discipline, 0) + total * part
    whole = sum(scores.values())
    ranked = sorted(scores.items(), key=lambda item: -item[1])
    return [(discipline, score / whole) for discipline, score in ranked if score > 0]


# --- sheets and questions: words -------------------------------------------------------------

# Matched case-blind after a word start; a pattern may stop mid-word, for compounds and the
# inflections of Finnish and Estonian ("lämmitysverkosto", "huoneen").
_SYSTEMS: tuple[tuple[System, str], ...] = (
    (
        "hot_water",
        r"hot water|domestic hot|dhw\b|water heat|lämmin ?vesi|lämpimän veden|"
        r"lämminkäyttövesi|warmwasser|trinkwarmwasser|varmvatten|warm water|warmwater|"
        r"agua caliente|eau chaude|acqua calda|soe vesi|sooja vee",
    ),
    (
        "cold_water",
        r"cold water|water supply|potable water|drinking water|domestic water|kylmä ?vesi|"
        r"kylmän veden|käyttövesi|kaltwasser|trinkwasser|kallvatten|tappvatten|koud water|"
        r"drinkwater|agua fría|agua potable|eau froide|eau potable|acqua fredda|"
        r"acqua potabile|külm vesi|külma vee|joogivesi",
    ),
    (
        "sewage",
        r"sewage|sewer|waste ?water|drainage|soil pipe|waste pipe|jätevesi|jäteveden|"
        r"viemär|abwasser|schmutzwasser|avlopp|spillvatten|riool|afvalwater|vuilwater|"
        r"aguas residuales|saneamiento|eaux usées|fognatur|scarico|kanalisatsioon|reovesi",
    ),
    (
        "rainwater",
        r"rain ?water|storm ?water|roof drain|sadevesi|sadeveden|hulevesi|regenwasser|"
        r"dagvatten|regenwater|hemelwater|aguas pluviales|eaux pluviales|acque piovane|sadevee",
    ),
    ("gas", r"gas (?:pipe|piping|supply|line|system|installation)|kaasu|gasleitung|gasledning"),
    (
        "supply_air",
        r"supply air|tuloilma|zuluft|tilluft|toevoerlucht|aire de impulsión|air soufflé|"
        r"aria di mandata|sissepuhke",
    ),
    (
        "exhaust_air",
        r"exhaust air|extract air|poistoilma|abluft|frånluft|afvoerlucht|aire de extracción|"
        r"air extrait|air vicié|aria di ripresa|väljatõmme",
    ),
    ("return_air", r"return air|palautusilma|umluft|återluft|retourlucht|recirculat"),
    (
        "outdoor_air",
        r"outdoor air|outside air|fresh air|ulkoilma|außenluft|aussenluft|uteluft|buitenlucht",
    ),
    (
        "sprinkler",
        r"sprinkler|fire suppression|fire extinguish|hydrant|sammutus|löschanlage|feuerlösch|"
        r"brandsläck|blusinstallatie|rociador|extinción|extincteur|estintor",
    ),
    (
        "cooling",
        r"cooling|chiller|jäähdyt|kälte|kühl|kyla|kylning|koeling|refrigeraci|refroidissement|"
        r"raffreddamento|jahutus",
    ),
    (
        "heating",
        r"(?<!water )heating|radiator|boiler|hydronic|thermostat|space heater|heat pump|"
        r"district heat|lämmity|"
        r"lämpöpatter|patteri|lattialämm|kaukolämpö|heizung|heizkörper|värme(?!återvinning)|"
        r"verwarming|calefacción|chauffage|riscaldamento|termosifon|küte|kütte|ogrzewan",
    ),
)

# Strong words for each discipline besides its systems'. Architecture has none: rooms, doors and
# walls are on every plan, so they are weak words.
_STRONG: tuple[tuple[Discipline, str], ...] = (
    (
        "plumbing",
        r"plumbing|sanitary|waste terminal|sanitär|sanitair|sanitet|sanitar|water pipe|"
        r"water piping|"
        r"wc\b|toilets?\b|lavator|washbasin|shower|bathtub|urinal|"
        r"vesi- ja viemäri|vesijohto|fontaner|plomberie|idraulic|veevarustus",
    ),
    (
        "ventilation",
        r"ventilat|duct|air terminal|air handling|ahu\b|diffuser|damper|heat recovery|"
        r"fans?\b|coils?\b|"
        r"ilmanvaihto|iv-kone|ilmakanav|tuloilmakoje|lämmöntalteenotto|lüftung|luftkanal|"
        r"wärmerückgewinnung|värmeåtervinning|luftbehandling|ventilation|luchtbehandeling|"
        r"warmteterugwinning|conducto|gaine|canalizzazion|ventilatsioon|õhukanal",
    ),
    (
        "electrical",
        r"electric|lighting|light fixture|luminaire|lamps?\b|socket|power outlet|conduit|"
        r"junction|"
        r"electrical outlet|switch|cable|wiring|distribution board|switchboard|panel ?board|"
        r"data device|communication device|telecom|sähkö|valaisin|valaistus|pistorasi|kaapel|"
        r"elektr|beleuchtung|leuchte|steckdose|kabel|belysning|eluttag|elcentral|verlichting|"
        r"stopcontact|iluminaci|eléctric|électri|éclairage|elettric|illuminazion|valgusti",
    ),
    (
        "fire",
        r"fire alarm|smoke detect|smoke alarm|fire protection|fire detection|fire hose|"
        r"palovaroitin|paloilmoit|brandschutz|brandmelde|rauchmelder|brandskydd|brandlarm|"
        r"brandbeveiliging|brandmeld|protección contra incendios|détection incendie|"
        r"antincendio|tulekahju",
    ),
    (
        "structural",
        r"structural|load[- ]?bearing|bearing wall|foundation|footing|piles?\b|piling|"
        r"reinforc|rebar|kantava|kantavat|perustu|paalu|raudoit|tragwerk|tragend|tragwand|"
        r"statik|fundament|bewehrung|bärande|grundläggning|armering|dragend|wapening|"
        r"constructie|estructur|cimentaci|armadura|fondation|ferraillage|portante|"
        r"fondazion|armatur|kandev|vundament|sarrus",
    ),
    (
        "site",
        r"site plan|\bsite\b|plot\b|parcel|terrain|landscap|topograph|georeferen|latitude|"
        r"longitude|asemapiirros|asemakaava|tontti|tontin|lageplan|grundstück|gelände|"
        r"situationsplan|tomt|situatie|perceel|emplazamiento|parcela|plan de masse|"
        r"planimetria|asendiplaan|krunt",
    ),
)

# Weak words, in the order they win when no strong word is there.
_WEAK: tuple[tuple[Discipline, str], ...] = (
    (
        "plumbing",
        r"pipe|piping|valve|pump|putki|venttiil|pumppu|rohr|ventil|pumpe|rör|leiding|"
        r"tubería|tuyau|tubazion|toru",
    ),
    (
        "structural",
        r"beam|column|concrete|steel|palkki|pilari|betoni|teräs|träger|stütze|"
        r"beton|stahl|balk|pelare|stål|kolom|staal|viga|pilar|hormigón|acero|poutre|poteau|"
        r"béton|acier|trave|pilastr|calcestruzz|acciaio|tala|post|teras",
    ),
    (
        "architecture",
        r"room|bedroom|bathroom|kitchen|space|area|gfa|ufa|nfa|door|window|wall|stair|roof|"
        r"ceiling|floor|balcon|skirting|baseboard|exit|escape|insulation|thermal bridge|"
        r"air ?tightness|envelope|fa[cç]ade|jalkalist|sockelleist|fußleist|golvlist|plint|"
        r"zócalo|rodapié|plinthe|battiscopa|põrandaliist|"
        r"furniture|level|storey|stories|apartment|units?\b|corridor|elevator|lift|ramp|railing|"
        r"curtain|covering|finish|slab|huone|tila|ovi|ovet|ovia|ikkun|seinä|porra|portai|katto|"
        r"kerro|parvek|lattia|raum|räum|tür|fenster|wand|wänd|treppe|dach|decke|geschoss|"
        r"stockwerk|grundriss|wohnung|rum\b|rummet|dörr|fönster|vägg|trappa|tak\b|våning|"
        r"ruimte|deur|raam|muur|trap\b|dak\b|verdieping|plattegrond|habitaci|puerta|ventana|"
        r"muro|pared|escalera|planta|pièce|porte|fenêtre|escalier|étage|stanza|porta|finestr|"
        r"parete|scala|piano|ruum|uks|uste|aken|akna|sein|trepp|korrus|põrand",
    ),
)

# Sheet codes and discipline abbreviations as title blocks print them, case as printed:
# EN sheet numbers (A-101, S201, E-301), Finnish ARK/RAK/SÄH/IV/KVV, German TWP.
_CODES: tuple[tuple[Discipline, str], ...] = (
    ("architecture", r"\bARK\b|\bARCH\b|\bA[-_. ]?\d{3}\b"),
    ("structural", r"\bRAK\b|\bTWP\b|\bS[-_. ]?\d{3}\b"),
    ("plumbing", r"\bKVV\b|\bP[-_. ]?\d{3}\b"),
    ("ventilation", r"\bIV[-_]"),
    ("electrical", r"\bS[ÄA]H(?:K[ÖO])?\b|\bE[-_. ]?\d{3}\b"),
    ("fire", r"\bFP[-_. ]?\d{3}\b|\bFA[-_. ]?\d{3}\b"),
    ("site", r"\b[CL][-_. ]?\d{3}\b"),
)


def _compiled[T: str](
    table: tuple[tuple[T, str], ...], flags: int
) -> list[tuple[T, re.Pattern[str]]]:
    return [(name, re.compile(rf"\b(?:{words})", flags)) for name, words in table]


_SYSTEM_RES: list[tuple[System, re.Pattern[str]]] = _compiled(_SYSTEMS, re.I)
_STRONG_RES: list[tuple[Discipline, re.Pattern[str]]] = _compiled(_STRONG, re.I)
_WEAK_RES: list[tuple[Discipline, re.Pattern[str]]] = _compiled(_WEAK, re.I)
_CODE_RES: list[tuple[Discipline, re.Pattern[str]]] = [
    (name, re.compile(words)) for name, words in _CODES
]  # each code has its \b


def _systems_in(text: str) -> set[System]:
    return {name for name, pattern in _SYSTEM_RES if pattern.search(text)}


def system_from_question(text: str) -> System | None:
    """The one building-services system a question names (heating, hot water, supply air, ...);
    None when it names none or several ("supply and exhaust air")."""
    found = _systems_in(text)
    return found.pop() if len(found) == 1 else None


def _strong_in(text: str, codes: bool) -> set[Discipline]:
    strong: set[Discipline] = {SYSTEM_DISCIPLINE[s] for s in _systems_in(text)}
    strong |= {name for name, pattern in _STRONG_RES if pattern.search(text)}
    if codes:
        strong |= {name for name, pattern in _CODE_RES if pattern.search(text)}
    return strong


def _discipline(text: str, codes: bool) -> Discipline | None:
    strong = _strong_in(text, codes)
    if strong:
        return strong.pop() if len(strong) == 1 else None
    return next((name for name, pattern in _WEAK_RES if pattern.search(text)), None)


def discipline_from_question(text: str) -> Discipline | None:
    """The discipline whose model answers the question; None when it names several or none."""
    return _discipline(text, codes=False)


def discipline_named_in(text: str) -> Discipline | None:
    """The one discipline `text` names by a strong word ("Heizung", "cold water"), weak words
    ("valve", "Ventil") left out; None when it names several or none."""
    strong = _strong_in(text, codes=False)
    return strong.pop() if len(strong) == 1 else None


def discipline_from_title(text: str) -> Discipline | None:
    """A 2D sheet's discipline from its title-block text (title, sheet number, drawing list
    line); None when unsure. Also reads sheet codes (A-101, S-201, ARK, RAK, SÄH, IV-)."""
    return _discipline(text, codes=True)


# What the sheet-kind model's `sheet_kind` already says (app/adapters/triage/sheet_kind.py KINDS);
# a kind not here (detail, schedule, photo, ...) says nothing. mep_plan names no one discipline.
_KIND_DISCIPLINE: dict[str, Discipline] = {
    "architectural_floor_plan": "architecture",
    "multi_view_sheet": "architecture",
    "roof_or_ceiling_plan": "architecture",
    "elevation": "architecture",
    "section": "architecture",
    "structural_plan": "structural",
    "site_plan_or_map": "site",
}


def discipline_from_sheet(
    kind: str, title: str | None, sheet_number: str | None
) -> Discipline | None:
    """A 2D sheet's discipline from the sheet-kind reply's fields, with no new model call. A title
    or number that names a discipline other than architecture by a strong word or code wins (a
    heating plan the model called a floor plan); weak words ("POST OFFICE", "PUMP HOUSE") never
    pick a discipline, whatever the kind, nor does a service room ("ELECTRICAL ROOM"). A mep_plan
    only by a service its title or number names (strong words and codes; "PIPING PLAN" or "HVAC"
    names none), else None."""
    text = " ".join(part for part in (title, sheet_number) if part)
    if kind == "mep_plan":
        strong = _strong_in(text, codes=True)
        return strong.pop() if len(strong) == 1 else None
    strong = _strong_in(_SERVICE_ROOM.sub(" ", text), codes=True)
    named = strong.pop() if len(strong) == 1 else None
    if named not in (None, "architecture"):
        return named
    return _KIND_DISCIPLINE.get(kind) or named


def sheet_discipline(
    said: Discipline, title: str | None, sheet_number: str | None
) -> Discipline | None:
    """A 2D sheet's discipline: the one the sheet-kind model said from what is drawn, cross-checked
    against the title and number. When they name disciplines by a strong word or a code (as
    `discipline_from_sheet` reads them: "HEATING PLAN", "S-201", not "PIPING" or "ELECTRICAL ROOM")
    and the model's is not among them, the sheet's discipline is not known: None, which nothing
    routes."""
    text = " ".join(part for part in (title, sheet_number) if part)
    named = _strong_in(_SERVICE_ROOM.sub(" ", text), codes=True)
    return said if not named or said in named else None


# A service named only as a room ("ELECTRICAL ROOM", "Sähköhuone", "Heizraum") is a room on the
# plan, not a service drawing. Not "riser" or "shaft": a riser diagram is a service drawing.
# shortcut: EN room nouns and FI/DE/SV compounds only; add other languages' if titles need them.
_SERVICE_ROOM = re.compile(
    r"\b(?:[^\W\d_]+[ -]){1,2}(?:room|closet|cupboard)s?\b|\b[^\W\d_]+(?:huone\w*|raum|rum)\b",
    re.I,
)

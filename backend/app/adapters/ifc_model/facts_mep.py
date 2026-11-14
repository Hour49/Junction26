"""The MEP facts of an IFC model (plumbing, heating, ventilation, electrical, fire): what its
distribution elements are, where, in which system, and how long its pipes, ducts and conduits
run. Numbers only; app/core/ifc_facts.py says what a fact is.

What is read, and the definitions the dataset's answers follow (dev rows, ifc-mep report):

- Elements: every IfcDistributionElement (flow segments, fittings, terminals, controllers,
  equipment, control elements) and IfcBuildingElementProxy, IFC2X3 and IFC4. Its kind is its
  class in snake case (IfcPipeSegment -> "pipe_segment"); an IFC2X3 file writes the generic
  class (IfcFlowSegment) and the kind comes from its type (IfcPipeSegmentType). Its group is
  the generic class ("flow_segment"), which some answers count by.
- Its type name is the file's ObjectType ("Family:Type" in a Revit export), else its type's
  Name, else its own Name. Answers count by it.
- Its category is what a Revit export writes as `Category` (Pset_ProductRequirements):
  "Lighting Fixtures", "Conduits", ... Answers that count "by category" use it.
- Storey: the storey that contains it or the space it is in (objects.py). Space: the IfcSpace
  that contains it, by Name (the room number).
- Systems: the IfcSystems it is assigned to; a file without any (older Revit IFC2X3 exports)
  names the system in its own property set (`System Name`, `System Type`).
- Length of a segment: its Qto `Length`, else a property set's `Length` (`Länge`), else the
  depth of the extrusion its body is, times the file's length unit, in metres. The dataset's
  answers add these up per type name.
- Size: the `Size` (`Größe`) text a property set states ("25 mmø", "DN10 mm"), else
  NominalDiameter in mm.
- Ports: a port is connected when an IfcRelConnectsPorts links it to another.
- Derived numbers are facts too, so an answer only looks them up: totals per material, use
  (application), fitting type, valve function and duct shape, read from words of the type name
  (tables below). Fittings twice: `count_by_fitting_type` counts the English words only, as the
  dataset's answers do; `count_by_fitting_type_true` counts every language (a Dutch "bocht" is a
  bend there) and is the real number; per-storey averages (over the named storeys) and mean
  segment lengths.
"""

import re
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import ifcopenshell.util.element
import ifcopenshell.util.system

from app.adapters.ifc_model.objects import _storey, _unit_scales
from app.core.ifc_facts import Discipline, Fact

# A class that says only "a flow element": the kind is read from its type.
GENERIC = {
    "IfcDistributionElement",
    "IfcDistributionFlowElement",
    "IfcDistributionControlElement",
    "IfcFlowSegment",
    "IfcFlowFitting",
    "IfcFlowTerminal",
    "IfcFlowController",
    "IfcFlowMovingDevice",
    "IfcFlowStorageDevice",
    "IfcFlowTreatmentDevice",
    "IfcEnergyConversionDevice",
}
GROUPS = (  # the generic classes, IFC2X3 and IFC4, that an element's group is read from
    "IfcFlowSegment",
    "IfcFlowFitting",
    "IfcFlowTerminal",
    "IfcFlowController",
    "IfcFlowMovingDevice",
    "IfcFlowStorageDevice",
    "IfcFlowTreatmentDevice",
    "IfcEnergyConversionDevice",
    "IfcDistributionControlElement",
    "IfcDistributionChamberElement",
)
# First match wins, over the category, the system type and the kind. Order matters: a fire
# damper is fire, a hydronic pipe is heating, an air handling unit with heat recovery is air.
DISCIPLINE_WORDS: tuple[tuple[Discipline, tuple[str, ...]], ...] = (
    ("fire", ("fire", "sprinkler", "smoke", "alarm")),
    ("ventilation", ("duct", "air", "damper", "fan", "ventilat")),
    ("heating", ("heat", "boiler", "radiator", "hydronic")),
    (
        "electrical",
        (
            "electric", "cable", "conduit", "light", "lamp", "switch", "outlet", "junction",
            "protective", "motor", "transformer", "communication", "data", "telephone", "audio",
        ),
    ),
    ("plumbing", ("pipe", "sanitary", "waste", "valve", "pump", "tank", "water", "plumbing",
                  "drain", "meter", "interceptor")),
)  # fmt: skip
# What an exporter calls a property, in the languages the dataset's Revit exports write.
PROPERTY_NAMES: Mapping[str, tuple[str, ...]] = {
    "length": ("Length", "Länge"),
    "size": ("Size", "Overall Size", "Größe", "Gesamtmaß"),
    "category": ("Category", "Kategorie"),
    "system_name": ("System Name", "Systemname"),
    "system_type": ("System Type", "Systemtyp", "System Classification"),
    "material": ("Material", "Materiaal", "Werkstoff"),
}
# Words of a type name (or a stated material or system) that put an element in a class, first
# match wins. A word is a regex matched whole (between non-letters, so "_PE" and "C-staal"
# count). shortcut: English, Dutch and German words of the dataset's exports; extend a table
# when a model in another language comes in.
Table = tuple[tuple[str, tuple[str, ...]], ...]
MATERIALS: Table = (
    ("mlcp", ("mlcp",)),
    ("pvc", ("pvc",)),
    ("pe", ("pe", "pe80", "pe100", "hdpe")),
    ("pp", ("pp",)),
    ("copper", ("copper", "koper", "kupfer")),
    ("stainless steel", ("rvs", "stainless", "roestvast", "edelstahl")),
    ("galvanised steel", ("verzinkt", "galvani[sz]ed", "gegalvaniseerd")),
    ("steel", ("steel", "staal", "stahl", "emt")),
    ("cast iron", ("cast iron", "gietijzer", "guss")),
    ("plastic", ("plastic", "kunststof", "kunststoff")),
)
APPLICATIONS: Table = (
    ("water supply", ("cold water", "hot water", "domestic", "drinkwater", "tapwater",
                      "warm water", "koud water", "trinkwasser", "water supply")),
    ("drainage", ("waste", "sanitary", "riolering", "[a-z]*afvoer", "regenwater", "storm",
                  "hemelwater[a-z]*", "vuilwater[a-z]*", "drain[a-z]*", "abwasser", "regenwasser")),
    ("heating", ("hydronic", "heating", "verwarming", "cv", "heizung")),
    ("cooling", ("gekoeld", "chilled", "cooling", "k[aä]lte")),
    ("fire", ("brand[a-z]*", "fire", "sprinkler[a-z]*")),
    ("ventilation", ("air", "lucht[a-z]*", "exhaust", "uitblaas", "luft[a-z]*", "l[uü]ftung")),
)  # fmt: skip
# The dataset's answers count fittings by these English words (and "koppeling"); a Dutch
# "bocht" or "T-stuk" stays "other" there, so it does here.
FITTING_TYPES: Table = (
    ("bend", ("bend[a-z]*", "elbow[a-z]*")),
    ("tee", ("tee",)),
    ("reducer", ("reduc[a-z]*",)),
    ("coupling", ("coupling[a-z]*", "koppeling")),
)
# The true reading (`count_by_fitting_type_true`): the same classes, in every language the
# dataset's exports write. `count_by_fitting_type` is the answers' English-only convention.
FITTING_TYPES_TRUE: Table = (
    (
        "bend",
        ("bend[a-z]*", "elbow[a-z]*", "bocht[a-z]*", "[a-z]*bocht", "knie", "bogen", "winkel"),
    ),
    ("tee", ("tee", "t-stuk", "t-st[uü]ck", "abzweig[a-z]*", "verdeelstuk")),
    ("reducer", ("reduc[a-z]*", "verloop[a-z]*", "[a-z]*verloop[a-z]*", "reduzier[a-z]*")),
    ("coupling", ("coupling[a-z]*", "koppeling", "[a-z]*mof", "muffe", "sok")),
)
FUNCTIONS: Table = (  # of a flow controller: valve, damper, meter; else "control"
    ("fire safety", ("fire", "brand[a-z]*")),
    ("metering", ("meter",)),
    ("safety", ("terugstroom[a-z]*", "backflow", "safety", "relief", "veiligheid[a-z]*")),
    ("shutoff", ("kogelkraan", "ball", "isolating", "shut[a-z]*", "gate", "afsluiter")),
)
CLASSES = ("material", "application", "fitting_type", "fitting_type_true", "function", "shape")
SHAPES: Table = (  # of a duct
    ("rectangular", ("rectangular", "rechth[a-z]*")),
    ("oval", ("oval", "ovaal")),
    ("round", ("round", "rond", "circular")),
)
ALL = "all"  # the subject of a total over every type
# The subject of a total over the elements that have a type, sensors and alarms left out: what
# the dataset's answers call "total components" (untyped proxies and boards are not counted).
TYPED = "typed"
REVIT_NAME = re.compile(r"(.+:.+):\d+")  # "Family:Type:<element id>"


@dataclass(frozen=True)
class MepElement:
    guid: str
    kind: str  # "pipe_segment", "light_fixture", ...
    group: str  # the generic class: "flow_segment", "flow_fitting", ...
    predefined: str | None  # the PredefinedType, of the element or else its type
    type_name: str
    name: str | None
    category: str | None
    storey: str | None
    space: str | None
    systems: tuple[str, ...]
    system_type: str | None
    length_m: float | None  # segments only
    length_source: str | None
    size: str | None
    classes: Mapping[str, str]  # its class in each of CLASSES that names one: {"material": "pvc"}
    typed: bool  # has a type and is no sensor or alarm (control element)
    discipline: Discipline


def mep_facts(model: Any) -> list[Fact]:
    """The MEP facts of an opened ifcopenshell file."""
    elements = mep_elements(model)
    facts: list[Fact] = []
    storeys = sum(1 for storey in model.by_type("IfcBuildingStorey") if storey.Name)
    by = _grouper(elements, facts, storeys)
    for kind in (lambda e: e.kind, lambda e: e.group, lambda e: "element"):
        by("count", lambda e, k=kind: (k(e), ALL, None, None))
        by("count", lambda e, k=kind: (k(e), ALL, e.storey, None))
    by("count", lambda e: (e.kind, e.type_name, None, None))
    by("count", lambda e: (e.kind, e.type_name, e.storey, None))
    by("count", lambda e: (e.kind, ALL, None, e.systems) if e.systems else None)
    by("count_in_space", lambda e: (e.kind, e.space, None, None))
    by("count_by_predefined_type", lambda e: (e.kind, e.predefined, None, None))
    by("count", lambda e: ("category", e.category, None, None))
    by("count", lambda e: ("category", e.category, e.storey, None))
    by(
        "count",
        lambda e: ("category_group", e.category and _category_group(e.category), None, None),
    )
    by("count", lambda e: ("element", TYPED if e.typed else None, None, None))
    by("count", lambda e: ("element", TYPED if e.typed else None, e.storey, None))
    for kind in (lambda e: e.kind, lambda e: e.group):
        for name in CLASSES:
            by(f"count_by_{name}", lambda e, k=kind, n=name: (k(e), e.classes.get(n), None, None))
    run = _grouper([e for e in elements if e.length_m is not None], facts, storeys)
    for measure in ("length", "with_length"):
        for kind in (lambda e: e.kind, lambda e: e.group):
            run(measure, lambda e, k=kind: (k(e), ALL, None, None))
            run(measure, lambda e, k=kind: (k(e), ALL, e.storey, None))
        run(measure, lambda e: (e.kind, e.type_name, None, None))
        run(measure, lambda e: (e.kind, ALL, None, e.systems) if e.systems else None)
        run(measure, lambda e: ("category", e.category, None, None))
        run(measure, lambda e: ("category", e.category, e.storey, None))
    for measure in ("length_mean", "length_per_storey"):
        for kind in (lambda e: e.kind, lambda e: e.group):
            run(measure, lambda e, k=kind: (k(e), ALL, None, None))
        run(measure, lambda e: (e.kind, e.type_name, None, None))
        run(measure, lambda e: ("category", e.category, None, None))
    for kind in (lambda e: e.kind, lambda e: e.group):
        for name in ("material", "application"):
            for total in ("length", "with_length"):
                run(
                    f"{total}_by_{name}",
                    lambda e, k=kind, n=name: (k(e), e.classes.get(n), None, None),
                )
    sizes = _grouper([e for e in elements if e.length_m is not None and e.size], facts, storeys)
    sizes("size_count", lambda e: (e.kind, e.size, None, e.systems or None))
    sizes("size_length", lambda e: (e.kind, e.size, None, e.systems or None))
    facts += _system_facts(model)
    facts += _port_facts(model, elements)
    facts += [
        Fact(
            topic=f"{e.kind}.space",
            subject=e.name or e.type_name,
            value=e.space,
            unit=None,
            storey=e.storey,
            discipline=e.discipline,
            source="IfcRelContainedInSpatialStructure",
        )
        for e in elements
        if e.space
    ]
    return list(dict.fromkeys(facts))  # an element whose kind is its group is counted once


def mep_elements(model: Any) -> list[MepElement]:
    length_scale = _unit_scales(model)["LENGTHUNIT"]
    # A proxy is what an exporter writes for a family it has no class for: receptacles,
    # switches, toilets of a Revit model; answers count them by their type name.
    entities = [*model.by_type("IfcDistributionElement"), *model.by_type("IfcBuildingElementProxy")]
    return [_element(entity, length_scale) for entity in entities]


def _element(entity: Any, length_scale: float) -> MepElement:
    kind = _kind(entity)
    type_ = ifcopenshell.util.element.get_type(entity)
    psets = ifcopenshell.util.element.get_psets(entity)
    texts: dict[str, str] = {}
    for props in psets.values():
        for name, value in props.items():
            # a Revit export fills unset type properties with their own name ("Size": "Size")
            if isinstance(value, str) and value.strip() and value != name:
                texts.setdefault(name, value)
    systems = tuple(
        system.Name
        for system in ifcopenshell.util.system.get_element_systems(entity)
        if system.Name
    ) or tuple(_said(texts, "system_name")[:1])
    system_type = next(iter(_said(texts, "system_type")), None)
    category = next(iter(_said(texts, "category")), None)
    container = ifcopenshell.util.element.get_container(entity)
    storey = _storey(entity)
    length = _length(entity, psets, length_scale) if kind.endswith("_segment") else None
    words = " ".join(filter(None, (category, system_type, kind.replace("_", " "))))
    type_name = _type_name(entity, type_) or kind
    return MepElement(
        guid=entity.GlobalId,
        kind=kind,
        group=_kind_of(next((g for g in GROUPS if entity.is_a(g)), entity.is_a())),
        predefined=_predefined(entity, type_),
        type_name=type_name,
        name=entity.Name,
        category=category,
        storey=None if storey is None else storey.Name,
        space=container.Name if container is not None and container.is_a("IfcSpace") else None,
        systems=systems,
        system_type=system_type,
        length_m=None if length is None else length[0],
        length_source=None if length is None else length[1],
        size=next(iter(_said(texts, "size")), None) or _nominal(psets, length_scale),
        classes=_classes(entity, kind, type_name, texts, (system_type, *systems)),
        typed=type_ is not None and not entity.is_a("IfcDistributionControlElement"),
        discipline=_discipline_of(words),
    )


def _type_name(entity: Any, type_: Any) -> str | None:
    """The ObjectType; a Revit IFC2X3 export writes only the type there ("100W - 120V") and
    "Family:Type:...:<element id>" as the Name, so the Name without its id says more."""
    stated = entity.ObjectType or (type_ and type_.Name) or None
    revit = REVIT_NAME.fullmatch(entity.Name or "")
    if revit and (stated is None or (stated in revit[1] and stated != revit[1])):
        return revit[1]
    return stated or entity.Name


def _kind(entity: Any) -> str:
    class_ = entity.is_a()
    if class_ in GENERIC:
        type_ = ifcopenshell.util.element.get_type(entity)
        if type_ is not None and type_.is_a().endswith("Type"):
            class_ = type_.is_a().removesuffix("Type")
    return _kind_of(class_)


def _kind_of(class_: str) -> str:
    name = class_.removeprefix("Ifc")
    return "".join(f"_{c.lower()}" if c.isupper() else c for c in name).lstrip("_")


def _classes(
    entity: Any, kind: str, type_name: str, texts: Mapping[str, str], systems: Iterable[str | None]
) -> dict[str, str]:
    stated = next(iter(_said(texts, "material")), None)
    found = {
        "material": _first(MATERIALS, stated or "") or _first(MATERIALS, type_name),
        # the type name first: a waste pipe drawn in a heating system is drainage
        "application": next(
            filter(None, (_first(APPLICATIONS, t or "") for t in (type_name, *systems))), None
        ),
        "shape": _first(SHAPES, type_name) if kind.startswith("duct_") else None,
    }
    if entity.is_a("IfcFlowFitting"):
        found["fitting_type"] = _first(FITTING_TYPES, type_name) or "other"
        found["fitting_type_true"] = _first(FITTING_TYPES_TRUE, type_name) or "other"
    if entity.is_a("IfcFlowController"):
        found["function"] = _first(FUNCTIONS, type_name) or "control"
    return {name: value for name, value in found.items() if value}


def _first(table: Table, text: str) -> str | None:
    """The first class of `table` a word of `text` names."""
    low = text.lower()
    for name, words in table:
        if any(re.search(rf"(?<![a-z0-9]){word}(?![a-z0-9])", low) for word in words):
            return name
    return None


def _category_group(category: str) -> str:
    """ "Conduit Fittings" and "Conduits" are both "Conduit": the first word, singular."""
    word = category.split()[0]
    return word.removesuffix("s") if len(word) > 3 else word


def _predefined(entity: Any, type_: Any) -> str | None:
    for source in (entity, type_):
        value = getattr(source, "PredefinedType", None)
        if value and value not in ("NOTDEFINED", "USERDEFINED"):
            return value
    return None


def _said(texts: Mapping[str, str], what: str) -> list[str]:
    return [texts[name] for name in PROPERTY_NAMES[what] if name in texts]


def _length(entity: Any, psets: dict, scale: float) -> tuple[float, str] | None:
    """The stated length, else the depth of the extrusion the segment's body is."""
    quantities = ifcopenshell.util.element.get_psets(entity, qtos_only=True)
    for sets in (quantities, psets):
        for set_name, props in sets.items():
            for name in PROPERTY_NAMES["length"]:
                value = props.get(name)
                if isinstance(value, int | float) and not isinstance(value, bool):
                    return float(value) * scale, f"{set_name}.{name}"
    # shortcut: one extrusion only; a segment drawn as a mapped or bent solid has no length
    # here, read it with the geometry kernel when a model needs it.
    for shape in getattr(entity.Representation, "Representations", None) or ():
        items = shape.Items
        body = shape.RepresentationIdentifier == "Body" and len(items) == 1
        if body and items[0].is_a("IfcExtrudedAreaSolid"):
            return float(items[0].Depth) * scale, "geometry: extrusion depth"
    return None


def _nominal(psets: dict, scale: float) -> str | None:
    for props in psets.values():
        value = props.get("NominalDiameter")
        if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
            return f"DN{round(value * scale * 1000)}"
    return None


Key = tuple[str, str | None, str | None, tuple[str | None, ...] | str | None]


def _grouper(
    elements: list[MepElement], facts: list[Fact], storeys: int
) -> Callable[[str, Callable[[MepElement], Key | None]], None]:
    """Adds one fact per group: `key` gives (kind, subject, storey, system or systems) of an
    element, None to leave it out. The measure is a count of elements ("count", "with_length",
    "count_by_...", ...) unless it starts with "length"/"size_length": metres summed, or
    "length_mean" (per segment) and "length_per_storey" (over `storeys`) averaged."""

    def add(measure: str, key: Callable[[MepElement], Key | None]) -> None:
        groups: dict[tuple[str, str | None, str | None, str | None], list[MepElement]]
        groups = defaultdict(list)
        for element in elements:
            found = key(element)
            if found is None or found[1] is None:  # no subject: not in that class
                continue
            kind, subject, storey, systems = found
            for system in systems if isinstance(systems, tuple) else (systems,):
                groups[(kind, subject, storey, system)].append(element)
        for (kind, subject, storey, system), members in groups.items():
            length = measure.startswith(("length", "size_length"))
            total = sum(e.length_m or 0.0 for e in members)
            if measure == "length_mean":
                total /= len(members)
            elif measure == "length_per_storey":
                if not storeys:
                    continue
                total /= storeys
            value = round(total, 3) if length else len(members)
            facts.append(
                Fact(
                    topic=f"{kind}.{measure}",
                    subject=str(subject),
                    value=value,
                    unit="m" if length else "count",
                    storey=storey,
                    system=system,
                    discipline=_most(e.discipline for e in members),
                    source=_most(e.length_source or "" for e in members) if length else "count",
                )
            )

    return add


def _most[T](values: Iterable[T]) -> T:
    return Counter(values).most_common(1)[0][0]


def _system_facts(model: Any) -> list[Fact]:
    """How many systems, of which type: the system's ObjectType, else its PredefinedType."""
    systems = [s for s in model.by_type("IfcSystem") if not s.is_a("IfcZone")]
    facts: list[Fact] = []
    for system in systems:
        members = _members(system)
        facts.append(_system_fact("system.element_count", system.Name or "", len(members)))
    kinds = Counter(_system_type(s) for s in systems)
    facts += [_system_fact("system.count", kind, n) for kind, n in kinds.items()]
    if systems:
        facts.append(_system_fact("system.count", ALL, len(systems)))
    return facts


def _system_type(system: Any) -> str:
    return system.ObjectType or getattr(system, "PredefinedType", None) or system.is_a()


def _system_fact(topic: str, subject: str, value: int) -> Fact:
    return Fact(
        topic=topic,
        subject=subject,
        value=value,
        unit="count",
        system=subject if topic == "system.element_count" else None,
        discipline=_discipline_of(subject),
        source="IfcRelAssignsToGroup",
    )


def _discipline_of(text: str) -> Discipline:
    words = text.lower()
    for discipline, keys in DISCIPLINE_WORDS:
        if any(key in words for key in keys):
            return discipline
    return "other"


def _port_facts(model: Any, elements: list[MepElement]) -> list[Fact]:
    ports = model.by_type("IfcDistributionPort")
    if not ports:
        return []
    connected = sum(1 for p in ports if p.ConnectedTo or p.ConnectedFrom)
    discipline: Discipline = _most(e.discipline for e in elements) if elements else "other"
    typed = sum(1 for e in elements if e.typed)
    found: list[tuple[str, float, str]] = [("count", len(ports), "count")]
    found.append(("connected", connected, "count"))
    if typed:  # what the dataset's answers call "average ports per component"
        found.append(("per_element", round(len(ports) / typed, 3), "ratio"))
    return [
        Fact(
            topic=f"port.{measure}",
            subject=ALL,
            value=value,
            unit=unit,
            discipline=discipline,
            source="IfcRelConnectsPorts",
        )
        for measure, value, unit in found
    ]


def _members(system: Any) -> list[Any]:
    """A system's elements; an IFC4 export assigns the elements' ports to it as well."""
    return [
        member
        for member in ifcopenshell.util.system.get_system_elements(system)
        if not member.is_a("IfcDistributionPort")
    ]


@dataclass(frozen=True)
class SystemTrace:
    system: str
    start: str  # GlobalId of where the run starts: the system's equipment, else its feed point
    order: tuple[str, ...]  # GlobalIds, breadth first from `start` through connected ports
    terminals: tuple[str, ...]  # the flow terminals reached, in that order
    run_m_by_size: Mapping[str, float]  # metres of segment reached, per size ("" not stated)
    unreached: int  # members no connected port leads to from `start`


SOURCES = (  # groups that feed a system: boilers, pumps, tanks, distribution boards
    "energy_conversion_device",
    "flow_moving_device",
    "flow_storage_device",
    "flow_treatment_device",
)


def trace_system(model: Any, system_name: str) -> SystemTrace:
    """Follows the system named `system_name` from its source through IfcRelConnectsPorts to
    its terminals. The source is the system's equipment; a branch without any starts where
    it connects to an element outside it (its riser), else at a segment or fitting with one
    neighbour. KeyError: the model has no such system."""
    found = [s for s in model.by_type("IfcSystem") if s.Name == system_name]
    if not found:
        raise KeyError(system_name)
    members = {m.GlobalId: m for s in found for m in _members(s)}
    neighbours = {guid: _neighbours(member) for guid, member in members.items()}
    scale = _unit_scales(model)["LENGTHUNIT"]
    elements = {guid: _element(member, scale) for guid, member in members.items()}

    def inside(guid: str) -> list[str]:
        return [n for n in neighbours[guid] if n in members]

    start = (
        next(
            (
                g
                for g, e in elements.items()
                if e.group in SOURCES or e.kind.startswith("electric_d")
            ),
            None,
        )
        or next(
            (
                g
                for g, e in elements.items()
                if e.group != "flow_terminal" and any(n not in members for n in neighbours[g])
            ),
            None,
        )
        or next(
            (g for g, e in elements.items() if e.group != "flow_terminal" and len(inside(g)) == 1),
            next(iter(members)),
        )
    )
    order, queue, seen = [], deque([start]), {start}
    while queue:
        guid = queue.popleft()
        order.append(guid)
        for n in inside(guid):
            if n not in seen:
                seen.add(n)
                queue.append(n)
    runs: dict[str, float] = defaultdict(float)
    for guid in order:
        if elements[guid].length_m is not None:
            runs[elements[guid].size or ""] += elements[guid].length_m or 0.0
    return SystemTrace(
        system=system_name,
        start=start,
        order=tuple(order),
        terminals=tuple(g for g in order if elements[g].group == "flow_terminal"),
        run_m_by_size={size: round(m, 3) for size, m in runs.items()},
        unreached=len(members) - len(order),
    )


def _neighbours(element: Any) -> list[str]:
    """GlobalIds of the elements whose ports connect to this element's ports."""
    found = []
    for port in ifcopenshell.util.system.get_ports(element):
        other = ifcopenshell.util.system.get_connected_port(port)
        if other is not None:
            found.append(ifcopenshell.util.system.get_port_element(other).GlobalId)
    return found

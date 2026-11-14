"""What is derived from a stored services model, never stored (spec SV-9, SV-10, SV-12): the
services facts of the fact sheet and the element graph. A full re-derive runs after every edit.

`facts(model)` gives the same facts, in the same order, as `facts_mep.mep_facts` on the file the
model was built from (test: equal lists on a synthetic IFC4 and IFC2X3 file). Besides the
spec's element fields it reads, when the model has them, an element's `name`, `space` (the
IfcSpace it is in, by Name), `length_source`, `classes` ({"material": "pvc", ...}) and the
model's `systems` ([{name, type, element_count}]); without them those topics are left out.

The model is read as its JSON document (a dict); a pydantic model is dumped first.
"""

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from app.core.ifc_facts import Discipline, Fact
from app.core.services.ops import ServicesGraph

Doc = Mapping[str, Any]
Element = dict[str, Any]
KindOf = Callable[[Element], str]
Key = tuple[str, str | None, str | None, Iterable[str | None] | str | None]

ALL = "all"
TYPED = "typed"
# facts_mep's table (a test keeps them equal): first match over a system's name or type wins.
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
# The class tables facts_mep counts by (`count_by_<name>`), in its order.
CLASSES = ("material", "application", "fitting_type", "fitting_type_true", "function", "shape")


def document(model: Any) -> Doc:
    """The model as its JSON document."""
    if isinstance(model, Mapping):
        return model  # pyright: ignore[reportUnknownVariableType]
    return model.model_dump(mode="json", by_alias=True)


def graph(model: Any) -> ServicesGraph:
    """The element adjacency over the model's connections (SV-10)."""
    return ServicesGraph(document(model))


def facts(model: Any) -> list[Fact]:
    """The services facts of the model, as facts_mep.mep_facts gives them for its source."""
    doc = document(model)
    names = {s["id"]: s.get("name") for s in doc.get("storeys", ())}
    elements: list[Element] = [
        {**e, "storey": names.get(e.get("storey")), "systems": tuple(e.get("systems") or ())}
        for e in doc.get("elements", ())
    ]
    found: list[Fact] = []
    storeys = sum(1 for name in names.values() if name)
    by = _grouper(elements, found, storeys)
    every: tuple[KindOf, ...] = (lambda e: e["kind"], lambda e: e["group"], lambda e: "element")
    both: tuple[KindOf, ...] = every[:2]
    for kind in every:
        by("count", lambda e, k=kind: (k(e), ALL, None, None))
        by("count", lambda e, k=kind: (k(e), ALL, e["storey"], None))
    by("count", lambda e: (e["kind"], e["type"], None, None))
    by("count", lambda e: (e["kind"], e["type"], e["storey"], None))
    by("count", lambda e: (e["kind"], ALL, None, e["systems"]) if e["systems"] else None)
    by("count_in_space", lambda e: (e["kind"], e.get("space"), None, None))
    by("count_by_predefined_type", lambda e: (e["kind"], e.get("predefined"), None, None))
    by("count", lambda e: ("category", e.get("category"), None, None))
    by("count", lambda e: ("category", e.get("category"), e["storey"], None))
    by("count", lambda e: ("category_group", _category_group(e.get("category")), None, None))
    by("count", lambda e: ("element", TYPED if e.get("typed") else None, None, None))
    by("count", lambda e: ("element", TYPED if e.get("typed") else None, e["storey"], None))
    for kind in both:
        for name in CLASSES:
            by(f"count_by_{name}", lambda e, k=kind, n=name: (k(e), _class(e, n), None, None))
    runs = [e for e in elements if e.get("length_m") is not None]
    run = _grouper(runs, found, storeys)
    for measure in ("length", "with_length"):
        for kind in both:
            run(measure, lambda e, k=kind: (k(e), ALL, None, None))
            run(measure, lambda e, k=kind: (k(e), ALL, e["storey"], None))
        run(measure, lambda e: (e["kind"], e["type"], None, None))
        run(measure, lambda e: (e["kind"], ALL, None, e["systems"]) if e["systems"] else None)
        run(measure, lambda e: ("category", e.get("category"), None, None))
        run(measure, lambda e: ("category", e.get("category"), e["storey"], None))
    for measure in ("length_mean", "length_per_storey"):
        for kind in both:
            run(measure, lambda e, k=kind: (k(e), ALL, None, None))
        run(measure, lambda e: (e["kind"], e["type"], None, None))
        run(measure, lambda e: ("category", e.get("category"), None, None))
    for kind in both:
        for name in ("material", "application"):
            for total in ("length", "with_length"):
                run(
                    f"{total}_by_{name}", lambda e, k=kind, n=name: (k(e), _class(e, n), None, None)
                )
    sized = _grouper([e for e in runs if e.get("size")], found, storeys)
    sized("size_count", lambda e: (e["kind"], e["size"], None, e["systems"] or None))
    sized("size_length", lambda e: (e["kind"], e["size"], None, e["systems"] or None))
    found += _system_facts(doc)
    found += _port_facts(doc, elements)
    found += [
        Fact(
            topic=f"{e['kind']}.space",
            subject=e.get("name") or e["type"],
            value=e["space"],
            unit=None,
            storey=e["storey"],
            discipline=e["discipline"],
            source="IfcRelContainedInSpatialStructure",
        )
        for e in elements
        if e.get("space")
    ]
    return list(dict.fromkeys(found))  # an element whose kind is its group is counted once


def _class(element: Element, name: str) -> str | None:
    classes: dict[str, str] = element.get("classes") or {}
    return classes.get(name)


def _category_group(category: str | None) -> str | None:
    """ "Conduit Fittings" and "Conduits" are both "Conduit": the first word, singular."""
    if not category:
        return None
    word = category.split()[0]
    return word.removesuffix("s") if len(word) > 3 else word


def _grouper(
    elements: list[Element], found: list[Fact], storeys: int
) -> Callable[[str, Callable[[Element], Key | None]], None]:
    """One fact per group, as facts_mep._grouper: `key` gives (kind, subject, storey, system
    or systems) of an element, None to leave it out."""

    def add(measure: str, key: Callable[[Element], Key | None]) -> None:
        groups: dict[tuple[str, str | None, str | None, str | None], list[Element]]
        groups = defaultdict(list)
        for element in elements:
            got = key(element)
            if got is None or got[1] is None:
                continue
            kind, subject, storey, systems = got
            for system in systems if isinstance(systems, tuple) else (systems,):
                groups[(kind, subject, storey, system)].append(element)  # pyright: ignore[reportArgumentType]
        for (kind, subject, storey, system), members in groups.items():
            length = measure.startswith(("length", "size_length"))
            total = sum(e.get("length_m") or 0.0 for e in members)
            if measure == "length_mean":
                total /= len(members)
            elif measure == "length_per_storey":
                if not storeys:
                    continue
                total /= storeys
            sources = (e.get("length_source") or "" for e in members)
            found.append(
                Fact(
                    topic=f"{kind}.{measure}",
                    subject=str(subject),
                    value=round(total, 3) if length else len(members),
                    unit="m" if length else "count",
                    storey=storey,
                    system=system,
                    discipline=_most(e["discipline"] for e in members),
                    source=_most(sources) if length else "count",
                )
            )

    return add


def _most[T](values: Iterable[T]) -> T:
    return Counter(values).most_common(1)[0][0]


def _system_facts(doc: Doc) -> list[Fact]:
    systems = doc.get("systems") or ()
    found = [_system_fact("system.element_count", s["name"], s["element_count"]) for s in systems]
    kinds = Counter(s["type"] for s in systems)
    found += [_system_fact("system.count", kind, n) for kind, n in kinds.items()]
    if systems:
        found.append(_system_fact("system.count", ALL, len(systems)))
    return found


def _system_fact(topic: str, subject: str, value: int) -> Fact:
    return Fact(
        topic=topic,
        subject=subject,
        value=value,
        unit="count",
        system=subject if topic == "system.element_count" else None,
        discipline=discipline_of(subject),
        source="IfcRelAssignsToGroup",
    )


def discipline_of(text: str) -> Discipline:
    words = text.lower()
    for discipline, keys in DISCIPLINE_WORDS:
        if any(key in words for key in keys):
            return discipline
    return "other"


def _port_facts(doc: Doc, elements: list[Element]) -> list[Fact]:
    ports = [p["id"] for e in elements for p in e.get("ports") or ()]
    if not ports:
        return []
    linked = {end for c in doc.get("connections", ()) for end in (c["a"], c["b"])}
    discipline: Discipline = _most(e["discipline"] for e in elements) if elements else "other"
    typed = sum(1 for e in elements if e.get("typed"))
    measured: list[tuple[str, float, str]] = [("count", len(ports), "count")]
    measured.append(("connected", sum(1 for p in ports if p in linked), "count"))
    if typed:
        measured.append(("per_element", round(len(ports) / typed, 3), "ratio"))
    return [
        Fact(
            topic=f"port.{measure}",
            subject=ALL,
            value=value,
            unit=unit,
            discipline=discipline,
            source="IfcRelConnectsPorts",
        )
        for measure, value, unit in measured
    ]

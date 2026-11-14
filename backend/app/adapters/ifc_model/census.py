"""How many objects of each IFC class a model holds: the input of
app/core/discipline.discipline_from_census. Works on a file opened lazily (objects.py's
`read_model` opens it so): listing the classes and counting them parses no object, so the
largest model of the dataset is counted in seconds."""

from typing import Any


def entity_census(model: Any) -> dict[str, int]:
    """`{"IfcWall": 120, "IfcPipeSegmentType": 7, ...}` for an opened `ifcopenshell.file`, each
    class counted without its subclasses, so the counts add up to the file's objects."""
    counts = {name: len(model.by_type(name, include_subtypes=False)) for name in model.types()}
    return {name: count for name, count in counts.items() if count}

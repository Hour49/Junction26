"""Stage 9: the counting rules decide which items count for each quantity, and how.

The dataset's conventions are data here, not branches in the question parser or the takeoff:
`COMBINED` says which counts are made of other counts, `MEASURED` which element quantity a sum of
lengths, areas or volumes reads, and the room rules which rooms a total keeps. Each rule's `text`
is shown with the answer. Where a rule follows the dataset's answers against the question's own
wording, the text says so.
"""

from collections.abc import Mapping

from app.core.drawing.model import ElementClass, Mark, QuantityKey
from app.core.model import Frozen
from app.core.pipeline.model import Counted, CountingRule, Measure

EACH_ONCE = CountingRule(
    id="each-once", text="every element, room and plan the drawing lists counts once"
)
AS_GIVEN = CountingRule(
    id="as-given", text="the total the source states; the items behind it are not listed"
)
SAUNA_ROOM_ELSE_STOVE = CountingRule(
    id="sauna-room-else-stove",
    text="one per sauna room; a drawing without sauna rooms counts its sauna stoves "
    "(CubiCasa5K, review-1 section 7: 2648 of 2655 dev answers)",
)
SHOWERS_AND_BATHTUBS = CountingRule(
    id="showers-and-bathtubs", text="showers and bathtubs together, each counted once"
)
ROOM_AREA = CountingRule(id="room-area", text="the room's net floor area as the drawing gives it")
ROOMS_TOTAL = CountingRule(
    id="rooms-total",
    text="the sum of the rooms' net floor areas; unknown when one of them has no area",
)
INDOOR_TOTAL = CountingRule(
    id="indoor-rooms-total",
    text="every room that is not outdoor; shafts, lifts and stairwells stay in, as the "
    "dataset's answers do although the question says shafts are left out (review-4)",
)
APARTMENT_AREA = CountingRule(
    id="apartment-area",
    text="the apartment's stated net area, else the sum of its rooms that are neither outdoor "
    "nor shafts",
)
ELEMENT_QUANTITY = CountingRule(
    id="element-quantities",
    text="the sum of the elements' own quantities (the model's Qto values); unknown when one "
    "of them has none",
)
SHEET_DWELLING = CountingRule(
    id="sheet-dwelling",
    text="a sheet that draws no apartment is one dwelling: the sum of its rooms that are neither "
    "outdoor nor shafts",
)
LARGEST_ROOM = CountingRule(
    id="largest-room",
    text="the largest net floor area among the rooms; unknown when one of them has no area",
)
MODEL_COUNT = CountingRule(
    id="model-objects",
    text="every object of the building model counts once, whether this sheet draws it or not",
)
MODEL_QUANTITY = CountingRule(
    id="model-quantities",
    text="the sum of the model's own quantities (its Qto values) over every object of the "
    "storey, drawn on this sheet or not; unknown when one of them has none",
)
MODEL_SPACES = CountingRule(
    id="model-spaces",
    text="the net floor area the model states for each of the storey's spaces, drawn on this "
    "sheet or not, else the area of the room the sheet draws it as; unknown when a space has "
    "neither",
)
ROOM_SIDE = CountingRule(
    id="room-longer-side",
    text="the longer side of a rectangular room's outline at the sheet's scale; other shapes "
    "have no sides to compare",
)


class Combined(Frozen):
    """A count made of other counts. `first_listed`: the first part that lists anything (a
    fallback); otherwise every part is added."""

    key: str
    rule: CountingRule
    parts: tuple[str, ...]
    first_listed: bool


COMBINED: tuple[Combined, ...] = (
    Combined(
        key="sauna",
        rule=SAUNA_ROOM_ELSE_STOVE,
        parts=("room:sauna", "sauna_stove"),
        first_listed=True,
    ),
    Combined(
        key="shower+bathtub",
        rule=SHOWERS_AND_BATHTUBS,
        parts=("shower", "bathtub"),
        first_listed=False,
    ),
)

# Sums over elements: (class, measure) -> the attr of each element that holds its quantity.
MEASURED: Mapping[tuple[ElementClass, Measure], str] = {
    ("wall", "length"): "length_m",
    ("wall", "area"): "net_side_area_m2",  # the net side area of the walls
    ("wall", "volume"): "net_volume_m3",
    ("slab", "volume"): "net_volume_m3",
}

# The same sums over a building model's objects: (class, measure) -> the object's quantity key.
MODEL_MEASURED: Mapping[tuple[ElementClass, Measure], QuantityKey] = {
    ("wall", "length"): "length_m",
    ("wall", "area"): "side_area_m2",
    ("wall", "volume"): "volume_m3",
    ("slab", "volume"): "volume_m3",
}

# A room is known by its label and by these attrs, alone or as "<name> (<number>)" (IFC spaces:
# review-6 section 8). `number` and `name` are what a sheet prints in the room (the vector
# extractor); `ifc_name` and `ifc_long_name` are the IFC space's Name and LongName (the gold).
ROOM_NUMBERS: tuple[str, ...] = ("number", "ifc_name")
ROOM_NAMES: tuple[str, ...] = ("name", "ifc_long_name", "ifc_name")


def apply_rules(listed: Mapping[str, tuple[Mark, ...]]) -> dict[str, Counted]:
    """`listed` is Drawing.marks_by_quantity() (or the same for the items of one storey): per
    count key, every item the drawing lists. Gives each key counted once per item, plus the
    `COMBINED` counts."""
    counted = {key: Counted(rule=EACH_ONCE, marks=marks) for key, marks in listed.items()}
    for combined in COMBINED:
        parts = [listed.get(part, ()) for part in combined.parts]
        excluded: tuple[tuple[Mark, str], ...] = ()
        if combined.first_listed:
            chosen = next((i for i, found in enumerate(parts) if found), None)
            marks = () if chosen is None else parts[chosen]
            if chosen is not None:
                why = f"{combined.parts[chosen]} counted instead ({combined.rule.id})"
                excluded = tuple((mark, why) for found in parts[chosen + 1 :] for mark in found)
        else:
            marks = tuple(mark for found in parts for mark in found)
        counted[combined.key] = Counted(rule=combined.rule, marks=marks, excluded=excluded)
    return counted


def combine_totals(counts: Mapping[str, int]) -> dict[str, int]:
    """The `COMBINED` counts of a drawing that only states totals. A combined count whose parts
    are not all stated is unknown, except a fallback whose first part is stated and above zero."""
    combined: dict[str, int] = {}
    for rule in COMBINED:
        values = [counts.get(part) for part in rule.parts]
        if rule.first_listed:
            first = values[0]
            if first is not None and first > 0:
                combined[rule.key] = first
            elif first is not None and all(value is not None for value in values):
                combined[rule.key] = next((v for v in values if v), 0)
        elif all(value is not None for value in values):
            combined[rule.key] = sum(value for value in values if value is not None)
    return combined

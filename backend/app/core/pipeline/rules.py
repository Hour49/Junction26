"""Stage 9: the counting rules decide which items count for each quantity, and how.

The dataset's conventions are data here, not branches in the question parser or the takeoff:
`COMBINED` says which counts are made of other counts, `MEASURED` which element quantity a sum of
lengths, areas or volumes reads, and the room rules which rooms a total keeps. Each rule's `text`
is shown with the answer. Where a rule follows the dataset's answers against the question's own
wording, the text says so.
"""

from collections.abc import Mapping

from app.core.drawing.model import ElementClass, Mark
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

# A room is known by its label and by these attrs, alone or as "<long name> (<name>)",
# "<name> (<number>)" and "<long name> (<number>)" (IFC spaces: review-6 section 8).
ROOM_NUMBER, ROOM_NAME, ROOM_LONG_NAME = "number", "ifc_name", "ifc_long_name"


def apply_rules(listed: Mapping[str, tuple[Mark, ...]]) -> dict[str, Counted]:
    """`listed` is Drawing.marks_by_quantity() (or the same for the items of one storey): per
    count key, every item the drawing lists. Gives each key counted once per item, plus the
    `COMBINED` counts."""
    counted = {key: Counted(rule=EACH_ONCE, marks=marks) for key, marks in listed.items()}
    for combined in COMBINED:
        parts = [listed.get(part, ()) for part in combined.parts]
        if combined.first_listed:
            marks = next((found for found in parts if found), ())
        else:
            marks = tuple(mark for found in parts for mark in found)
        counted[combined.key] = Counted(rule=combined.rule, marks=marks)
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

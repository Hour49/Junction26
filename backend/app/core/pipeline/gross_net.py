"""A floor area the sheet prints against the rooms found summed (GROSS_NET_CHECK).

US sheets print area tables whose totals are gross: BOMA Z65.3 and ASTM E1836 measure a floor to
the outside face of its exterior walls, with no deductions (docs/research/pdf-accuracy/scanned.md
#4). The rooms a reading finds are net: each outline inside its walls. So the two never agree, but
their ratio is known (related.md #2): net/gross is 0.60-0.82 for offices (study guides, secondary
sources) and 0.71 for a K-8 school (NJ DOE grossing factor 1.40). Our net is every room outline,
corridors included, so it sits above an assignable ratio; the top of NET_TO_GROSS is 1.0 plus the
2% a rounded printed total may be off (second_count.TOLERANCE).

- Outside NET_TO_GROSS the rooms found miss part of the floor (or the scale is off, or the total
  is another floor's or the building's): the sheet's floor area gets two stage-8 values, the rooms
  summed (`summed_rooms`) and the printed gross (`printed_total`), the note saying which is which.
  No rule decides between them, so the indoor area answer keeps the net number and is held for a
  person (takeoff._conflict_keys); it never becomes the gross number.
- Inside it the printed gross is only context: a note on the reading.

The gross is a printed fact with an area unit whose subject is floor_area or whose text says TOTAL
or GROSS, the largest of them (a floor total is never smaller than its wing subtotals). The net is
the indoor rooms as the takeoff sums them (`takeoff._area_sum`): a room whose box area was refused
is left out, any other room without an area leaves the net unknown, and then nothing is checked.
"""

import re
from collections.abc import Sequence

from app.core.drawing.model import MeasuredValue, Room, Subject
from app.core.pipeline.model import Extracted, Measurement
from app.core.pipeline.printed import PrintedFact
from app.core.pipeline.raster_scale import AREA_REFUSED

FT2_M2 = 0.09290304  # one international square foot
AREA_UNITS = {"m2": 1.0, "ft2": FT2_M2}  # the Carbon reader's area units, in m²
NET_TO_GROSS = (0.60, 1.02)  # the plausible net/gross band: the module docstring
_TOTAL = re.compile(r"\b(?:total|gross)\b", re.IGNORECASE)


def printed_gross(facts: Sequence[PrintedFact]) -> tuple[float, PrintedFact] | None:
    """The sheet's printed gross floor area in m², with the fact it was read from; None when it
    prints no area total."""
    totals = [
        (fact.value * AREA_UNITS[fact.unit], fact)
        for fact in facts
        if fact.unit in AREA_UNITS
        and fact.value > 0
        and (fact.subject == "floor_area" or _TOTAL.search(fact.text))
    ]
    return max(totals, key=lambda total: total[0], default=None)


def net_area(rooms: Sequence[Room]) -> float | None:
    """The indoor rooms' areas summed; None when there are none or one has no area that was not
    refused."""
    indoor = [
        r for r in rooms if not r.outdoor and not (r.area_m2 is None and AREA_REFUSED in r.attrs)
    ]
    areas = [room.area_m2 for room in indoor]
    if not areas or any(area is None for area in areas):
        return None
    return sum(area for area in areas if area is not None)


def gross_net_checked(found: Extracted, facts: Sequence[PrintedFact]) -> Extracted:
    """`found` with its rooms' net area checked against the gross area the sheet prints: a note,
    and outside NET_TO_GROSS the two as a `floor_area` conflict of the sheet."""
    gross, net = printed_gross(facts), net_area(found.rooms)
    if gross is None or net is None:
        return found
    m2, fact = gross
    ratio = net / m2
    low, high = NET_TO_GROSS
    said = (
        f'the sheet prints a gross area of {m2:,.0f} m² ("{fact.text}", to the outside walls); '
        f"the rooms found sum to {net:,.0f} m² (inside walls), {ratio:.0%} of it"
    )
    if low <= ratio <= high:
        return found.model_copy(
            update={"notes": (*found.notes, f"{said}: as expected of a net area")}
        )
    said += f": outside the {low:.0%}-{high:.0%} expected of a net area, left for a person"
    sheet = Subject(kind="sheet", ref=None)
    printed = MeasuredValue(
        value=m2,
        unit="m2",
        method="printed_total",
        page=fact.page if fact.box is not None else None,
        box=fact.box,
    )
    pair = (
        Measurement(
            quantity="floor_area",
            subject=sheet,
            value=MeasuredValue(value=net, unit="m2", method="summed_rooms"),
        ),
        Measurement(quantity="floor_area", subject=sheet, value=printed, note=said),
    )
    return found.model_copy(
        update={"printed": (*found.printed, *pair), "notes": (*found.notes, said)}
    )

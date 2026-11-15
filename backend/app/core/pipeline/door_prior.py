"""Which door width a door estimate takes: by the kind of door box, then by the unit system.

DOOR_PRIOR_BOXES=on: a door box is either the detector's leaf box (raster_scale.DOOR_M, 0.794 m,
fitted on it) or the Carbon reader's box with the door's swing in (CARBON_DOOR_M, 1.069 m, fitted
on it). Where the composite reads the doors with Carbon (no detector weights, `carbon:` door
components), `PriorScale` divided Carbon's boxes by DOOR_M: the scale came out 0.66-0.78 of a hand
reference on T1 (UK school, metric), T2 (US dorm) and T3 (US piping), 1.01 / 1.05 / 0.89 at
CARBON_DOOR_M (.agents/research/accuracy/t2-scale.md). `read_only_by`: every door the prior counts
(`door_sides`) was read by that reader; the estimate then takes `carbon_door_scale`. With detector
weights the composite's doors are the detector's and nothing changes.

DOOR_PRIOR_UNITS=on: the door estimate on a sheet whose printed text is imperial takes a US door.

raster_scale.DOOR_M (0.794 m) is fitted on CubiCasa val: Finnish homes, 800 mm leaves. A US
commercial or dorm door is a 3'-0" leaf: IMPERIAL_DOOR_M = 0.914 m, from the standard, not a fit
(ADA 2010 404.2.3 asks 32" clear, which a 36" leaf gives; 3'-0" is the stock commercial leaf).
The estimate is proportional to the width, so on a US sheet the fitted width gives a scale
0.794 / 0.914 = 0.87 of a 3'-0" door's (lengths 13% short, areas 25% low).

Why here and not in the estimate: the door estimate (`PriorScale`) is made before the sheet's
printed text is read, and only the printed reader (`PrintedScale`, outside it) has that text. So
the estimate is corrected afterwards, as `with_printed` corrects it with a printed scale: the
scale is multiplied by IMPERIAL_DOOR_M / DOOR_M, its source says so, and every room the estimate
measured (or refused) is measured again. The relative band (`door_band`) is unchanged: it rests
on how many doors there are and how far their widths disagree, not on the width.

`is_imperial`: an imperial printed scale (`printed.imperial_scales`), a feet-inch dimension
(12'-6"), or a number in square feet or feet (1,200 SF, 40 FEET) anywhere in the printed scale,
the scale bars' labels, the printed facts' texts or the room labels. A count ("48 DORMS"), a lone
prime (6') or a bare number says nothing and is not imperial.

Only the detector's estimate (DOOR_M in its source) is changed. Carbon's door estimate
(CARBON_DOOR_M, fitted on Swiss scans and USCG fp21 with the boxes' swing in) is left as it is:
too few US scans to split it (.agents/research/accuracy/door-prior.md). A printed scale still
replaces the corrected estimate in `with_printed`, which then keeps the corrected one as the
conflict's other value. shortcut: 0.914 is the standard, not measured on the detector's boxes on
US scans (fewer than 5 with a reference); refit when there are.
"""

import re
from collections.abc import Iterable, Sequence

from app.core.drawing.model import Element, Page, Room
from app.core.pipeline.model import Extracted
from app.core.pipeline.printed import PrintedSheet, imperial_scales
from app.core.pipeline.raster_scale import (
    AREA_REFUSED,
    CARBON_DOORS,
    DOOR_M,
    REFUSED_NOTE,
    door_sides,
    rooms_with_areas,
)

IMPERIAL_DOOR_M = 0.914  # m, a 3'-0" leaf (ADA 404.2.3: 32" clear), the standard, not a fit
ESTIMATE_NOTE = "scale estimate: "  # how PriorScale's note on its estimate starts
_DETECTOR = f"a door is about {DOOR_M} m wide; "  # how the detector estimate's source starts
_FEET_INCHES = re.compile(r"\d\s*['\u2019\u2032]\s*-?\s*\d+(?:\s+\d+/\d+)?\s*[\"\u201d\u2033]")
_IMPERIAL_UNIT = re.compile(
    r"\d\s*(?:s\.?\s?f\.?|sq\.?\s*f(?:ee)?t\.?|ft2|ft²|square\s+f(?:ee|oo)t|f(?:ee|oo)t|ft)"
    r"(?![^\W\d_])",
    re.IGNORECASE,
)


def read_only_by(reader: str, elements: Sequence[Element], pages: Sequence[Page]) -> bool:
    """Whether every door the door prior counts (`door_sides`: sure, located, on a page) was read
    by `reader` (`attrs.reader`); False when it counts none. An unlocated placeholder door is not
    counted, so it does not decide either way."""
    counted = door_sides(elements, pages)
    mine = door_sides([e for e in elements if e.attrs.get("reader") == reader], pages)
    return bool(counted) and len(mine) == len(counted)


def is_imperial(texts: Iterable[str | None]) -> bool:
    """Whether any of `texts` is printed in feet and inches: an imperial scale, a feet-inch
    dimension, or a number in (square) feet."""
    return any(
        imperial_scales(text) or _FEET_INCHES.search(text) or _IMPERIAL_UNIT.search(text)
        for text in texts
        if text
    )


def sheet_texts(printed: PrintedSheet, rooms: Sequence[Room]) -> list[str | None]:
    """What the sheet prints that can say its units: its scale, its bars' labels, its printed
    facts and its room labels."""
    return [
        printed.printed_scale,
        *(bar.text for bar in printed.bars),
        *(fact.text for fact in printed.printed_facts),
        *(room.label for room in rooms),
    ]


def imperial_doors(found: Extracted, printed: PrintedSheet, pages: Sequence[Page]) -> Extracted:
    """`found` with its detector door estimate at IMPERIAL_DOOR_M when the sheet is imperial, and
    every room that estimate measured or refused measured again; `found` itself otherwise."""
    scale = found.scale
    source = scale.source or ""
    if (
        scale.status != "estimated"
        or scale.m_per_unit is None
        or not source.startswith(_DETECTOR)
        or CARBON_DOORS in source
        or not is_imperial(sheet_texts(printed, found.rooms))
    ):
        return found
    us = scale.model_copy(
        update={
            "m_per_unit": scale.m_per_unit * IMPERIAL_DOOR_M / DOOR_M,
            "source": f"a door is about {IMPERIAL_DOOR_M} m wide (a 3'-0\" leaf: the sheet is "
            f"imperial); {source.removeprefix(_DETECTOR)}",
        }
    )
    cleared = {"area_m2": None, "area_status": None, "area_source": None, "area_uncertainty": None}
    rooms = [
        room.model_copy(
            update={**cleared, "attrs": {k: v for k, v in room.attrs.items() if k != AREA_REFUSED}}
        )
        if room.area_source == "geometry_x_estimate" or AREA_REFUSED in room.attrs
        else room
        for room in found.rooms
    ]
    measured, refused = rooms_with_areas(rooms, us, pages)
    kept = (n for n in found.notes if not n.startswith((ESTIMATE_NOTE, REFUSED_NOTE)))
    return found.model_copy(
        update={
            "scale": us,
            "rooms": tuple(measured),
            "notes": (*kept, f"{ESTIMATE_NOTE}{us.source}", *refused),
        }
    )

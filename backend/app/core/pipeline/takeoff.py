"""Stage 10: the takeoff, every quantity the drawing model can answer, with its marks and rule.

Hello world: counts only (the keys of COUNT_KEYS). Areas, lengths and volumes are added here, and
the question parser then maps questions to their keys.
"""

from collections.abc import Mapping

from app.core.drawing.model import Drawing
from app.core.pipeline.model import Counted, Quantity
from app.core.pipeline.rules import AS_GIVEN, apply_rules


def take_off(drawing: Drawing, counted: Mapping[str, Counted]) -> dict[str, Quantity]:
    """A drawing that only states totals (`counts`) gives those, without marks; a quantity it
    does not state is unknown. Otherwise each quantity is the number of marks its rule kept."""
    if drawing.counts is not None:
        return {
            key: Quantity(key=key, value=value, unit="count", marks=(), rule=AS_GIVEN.id)
            for key, value in drawing.counts.items()
        }
    return {
        key: Quantity(
            key=key, value=len(found.marks), unit="count", marks=found.marks, rule=found.rule.id
        )
        for key, found in counted.items()
    }


def known_quantities(drawing: Drawing) -> dict[str, Quantity]:
    """Stages 9 and 10 on a stored drawing model: what answering looks a query up in."""
    return take_off(drawing, apply_rules(drawing.marks_by_quantity()))

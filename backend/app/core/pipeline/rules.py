"""Stage 9: the counting rules decide which marks count for each quantity.

Hello world: one rule, every listed item counts once. A dataset convention (one window per drawn
cell; a sauna room, else its stove) becomes a `CountingRule` here plus the selection it makes in
`apply_rules`.
"""

from collections.abc import Mapping

from app.core.drawing.model import Mark
from app.core.pipeline.model import Counted, CountingRule

EACH_ONCE = CountingRule(
    id="each-once", text="every element, room and plan the drawing lists counts once"
)
AS_GIVEN = CountingRule(
    id="as-given", text="the total the source states; the items behind it are not listed"
)


def apply_rules(listed: Mapping[str, tuple[Mark, ...]]) -> dict[str, Counted]:
    """`listed` is Drawing.marks_by_quantity(): per quantity, every item the drawing lists."""
    return {key: Counted(rule=EACH_ONCE, marks=marks) for key, marks in listed.items()}

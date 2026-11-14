"""Which of the plan boxes on a page are floor plans, by the rooms read in them.

The image route's plan boxes come from a detector trained on sheets where every drawing is a floor
plan, so it also boxes an elevation or a section drawn beside the plans: on a sheet with two plans
and four elevations it gave six boxes, and the answer was "6 floor plans". An elevation has no
room names, and few or no rooms. So on a page where a plan box holds a labelled room, a box that
holds no room at all is not a floor plan; a box with rooms whose labels were not read stays (a
second plan beside a labelled one: review-377). A page where no box holds a labelled room keeps
every box: the sheet may not label its rooms at all. On CubiCasa val (376 pages, 68 of them with
two or three plan boxes) no page loses a box.
"""

from collections.abc import Sequence

from app.core.drawing.model import Box, Plan, Room


def floor_plans(plans: Sequence[Plan], rooms: Sequence[Room]) -> tuple[Plan, ...]:
    """`plans` without the boxes that hold no room at all on a page where another box holds a
    labelled one; the order is kept. A box holds a room when the centre of the room's box is
    inside it."""
    labelled = [room for room in rooms if (room.label or "").strip()]
    with_labels = [_holds_any(plan, labelled) for plan in plans]
    pages = {plan.page for plan, has in zip(plans, with_labels, strict=True) if has}
    return tuple(plan for plan in plans if plan.page not in pages or _holds_any(plan, rooms))


def _holds_any(plan: Plan, rooms: Sequence[Room]) -> bool:
    return any(room.page == plan.page and _holds(plan.box, room.box) for room in rooms)


def _holds(plan: Box, room: Box) -> bool:
    x, y = (room[0] + room[2]) / 2, (room[1] + room[3]) / 2
    return plan[0] <= x <= plan[2] and plan[1] <= y <= plan[3]

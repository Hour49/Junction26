"""A plan edit as the chat returns it (decision 0013, `edit` and `Selection`; spec AC-20)."""

from typing import Literal

from pydantic import Field

from app.core.drawing.model import Box
from app.core.model import Frozen
from app.core.plan_edit.law_check import LawCheck
from app.core.services.edit import ServicesChange
from app.core.services.model import ServicesFollow

# A polygon in page fractions (0..1, top left), as get_plan_geometry returns rooms.
Ring = tuple[tuple[float, float], ...]
ProposalState = Literal["proposed", "accepted", "rejected"]


class Selection(Frozen):
    """What the user pointed at on a plan: a room (`ref` its id) or a dragged rectangle (`box`)."""

    id: str = Field(pattern=r"^sel_\d+$")
    kind: Literal["room", "region"]
    drawing_id: str = Field(min_length=1, max_length=64)
    page: int = Field(ge=1)
    ref: str | None = Field(default=None, max_length=32)
    box: Box | None = None


class Item(Frozen):
    """A removed or added piece of geometry (a wall strip, a door, a new partition)."""

    id: str
    polygon: Ring
    label: str


class RoomChange(Frozen):
    id: str  # "R1+R2" for a merge, "new" ids for a placed room
    label: str
    polygon: Ring
    area_before_m2: float
    area_after_m2: float
    was: tuple[str, ...] = ()


class Flag(Frozen):
    code: str
    text: str


class Proposal(Frozen):
    proposal_id: str  # p1, p2... per chat
    drawing_id: str
    page: int = Field(ge=1)
    state: ProposalState = "proposed"
    removed: tuple[Item, ...] = ()
    added: tuple[Item, ...] = ()
    rooms: tuple[RoomChange, ...] = ()
    unknowns: tuple[str, ...] = ()
    flags: tuple[Flag, ...] = ()
    law: LawCheck | None = None  # the rule pack before vs after (LC-7); None: no pack chosen
    # The edit followed through the project's service models (decision 0016); None: not asked
    # for (SERVICES_FOLLOW=off)
    services: ServicesFollow | None = None
    # A change of a services model itself (decision 0017, SV-28): set on a services proposal only,
    # whose removed, added and rooms are then empty; None on a plan edit. law_check does not read it
    services_change: ServicesChange | None = None

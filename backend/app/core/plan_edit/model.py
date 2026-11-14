"""A plan edit as the chat returns it (decision 0013, `edit` and `Selection`; spec AC-20)."""

from typing import Literal

from pydantic import Field

from app.core.drawing.model import Box
from app.core.model import Frozen

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

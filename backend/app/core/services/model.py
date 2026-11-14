"""A plan edit followed through the building's services (docs/specs/services-follow.md): what a
service model holds as plain data, and the follow-up as the chat returns it on a proposal.

A service element is a pipe or duct piece, a fitting, a valve, a fixture: anything of a model
that carries plumbing, ventilation, heating or electrical. Its place is a point and the points
of its connection ports; a run's centre line is the line between its two ports. Which elements
connect is the model's own port graph, and which system each belongs to is the model's own
grouping. Nothing here is drawn or guessed: a project without a service model has none.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from app.core.ifc_facts import Discipline
from app.core.model import Frozen

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
Path = tuple[Point2, ...]

# The lanes a follow-up always lists, checked or not: silence would read as "nothing to do".
LANES: tuple[Discipline, ...] = ("plumbing", "ventilation", "heating", "electrical")
MAX_RESIDUAL_M = 0.05  # a room's centre this far off after the fit: the sheet is not the model
SCALE_SLACK = 0.02  # the sheet's metres and the model's metres must agree this closely
TERMINAL_KINDS = {"space_heater", "electric_heater"}  # terminals an IFC2x3 file groups elsewhere


@dataclass(frozen=True)
class ServiceElement:
    guid: str
    lane: Discipline
    kind: str  # as the model classes it: "pipe_segment", "sanitary_terminal", "damper"
    group: str  # the generic class: "flow_segment", "flow_fitting", "flow_terminal", ...
    predefined: str | None  # "TOILETPAN", "FIREDAMPER"
    type_name: str
    size: str | None
    systems: tuple[str, ...]
    storey: str | None  # the storey the model files it under, by name
    at: Point3  # x, y: metres in the frame it was last placed in; z: the model's height
    ports: tuple[Point3, ...]
    neighbours: tuple[str, ...]  # GlobalIds of the elements its ports connect to

    @property
    def is_run(self) -> bool:
        return self.group == "flow_segment" and len(self.ports) == 2

    @property
    def is_terminal(self) -> bool:
        return self.group == "flow_terminal" or self.kind in TERMINAL_KINDS

    @property
    def heights(self) -> tuple[float, float]:
        zs = [p[2] for p in self.ports] or [self.at[2]]
        return min(zs), max(zs)


@dataclass(frozen=True)
class Frame:
    """Model metres to a plan page's metres (x right, y down from the page's top left): the
    least-squares fit over the rooms the sheet draws. `residual_m`: the worst room's miss."""

    a: tuple[tuple[float, float], tuple[float, float]]
    b: Point2
    residual_m: float
    rooms: int

    def at(self, x: float, y: float) -> Point2:
        (axx, axy), (ayx, ayy) = self.a
        return axx * x + axy * y + self.b[0], ayx * x + ayy * y + self.b[1]

    def placed(self, element: ServiceElement) -> ServiceElement:
        def moved(point: Point3) -> Point3:
            return (*self.at(point[0], point[1]), point[2])

        return replace(element, at=moved(element.at), ports=tuple(map(moved, element.ports)))


def fit_frame(pairs: Sequence[tuple[Point2, Point2]]) -> Frame | str:
    """The frame that takes each pair's first point (model) onto its second (page), or why
    there is none: fewer than three rooms, rooms in one line, a miss over 5 cm, or metres that
    disagree (the sheet's scale is not the model's)."""
    if len(pairs) < 3:
        return f"only {len(pairs)} rooms of the model are drawn on this sheet (3 are needed)"
    n = len(pairs)
    mx = sum(m[0] for m, _ in pairs) / n
    my = sum(m[1] for m, _ in pairs) / n
    sxx = sum((m[0] - mx) ** 2 for m, _ in pairs)
    sxy = sum((m[0] - mx) * (m[1] - my) for m, _ in pairs)
    syy = sum((m[1] - my) ** 2 for m, _ in pairs)
    det = sxx * syy - sxy * sxy
    if det <= 1e-9 * max(sxx, syy, 1.0) ** 2:
        return "the rooms drawn on this sheet lie in one line, so the model cannot be placed"
    rows: list[tuple[float, float]] = []
    offsets: list[float] = []
    for axis in (0, 1):
        mean = sum(p[axis] for _, p in pairs) / n
        cx = sum((m[0] - mx) * (p[axis] - mean) for m, p in pairs)
        cy = sum((m[1] - my) * (p[axis] - mean) for m, p in pairs)
        ax, ay = (cx * syy - cy * sxy) / det, (cy * sxx - cx * sxy) / det
        rows.append((ax, ay))
        offsets.append(mean - ax * mx - ay * my)
    frame = Frame((rows[0], rows[1]), (offsets[0], offsets[1]), 0.0, n)
    scale = abs(rows[0][0] * rows[1][1] - rows[0][1] * rows[1][0]) ** 0.5
    if abs(scale - 1) > SCALE_SLACK:
        return f"the sheet's scale and the model disagree (1 m of the model is {scale:.2f} m here)"
    worst = max(
        ((frame.at(*m)[0] - p[0]) ** 2 + (frame.at(*m)[1] - p[1]) ** 2) ** 0.5 for m, p in pairs
    )
    if worst > MAX_RESIDUAL_M:
        return f"the model's rooms miss the sheet's rooms by up to {worst:.2f} m"
    return replace(frame, residual_m=round(worst, 4))


@dataclass(frozen=True)
class Lane:
    """One discipline of a project for one plan page: its elements placed in the page's metres,
    or why it could not be followed."""

    discipline: Discipline
    status: Literal["checked", "no_model", "not_aligned"]
    source: str | None = None  # the model's plain name in the project
    reason: str | None = None
    elements: tuple[ServiceElement, ...] = ()


# --- the follow-up as the API gives it (additive on the proposal, decision 0016) ---------------

Status = Literal["follows", "stays", "needs_decision", "cut_off"]
Code = Literal[
    "reseat", "in_wall", "cut_off", "through", "riser", "fire_damper", "tally", "opening", "under",
    "missing",
]  # fmt: skip


class ServiceMark(Frozen):
    """One service element near the edit, for the overlay: a run as its line, anything else as
    its point. Page fractions."""

    ref: str  # P12, V3, H7, E1: the lane's letter and a number, stable within one follow-up
    global_id: str  # the element's IFC GlobalId in the lane's model (`source`), for a 3D view
    kind: str  # plain: "pipe", "duct", "radiator", "toilet"
    label: str
    line: Path = ()
    at: Point2 | None = None


class ServiceAction(Frozen):
    """One consequence of the edit in one discipline. `label` is the whole of it in plain words,
    numbers included; the rest is for drawing it."""

    id: str  # a1, a2... within the lane
    status: Status
    code: Code
    label: str
    refs: tuple[str, ...] = ()  # the marks it is about
    system: str | None = None
    moved_to: Point2 | None = None  # a re-seated terminal's new place
    paths: tuple[Path, ...] = ()  # proposed new connections, drawn dashed


class Summary(Frozen):
    follows: int = 0
    stays: int = 0
    needs_decision: int = 0
    cut_off: int = 0  # terminals that lose a system
    new_run_m: float = 0.0  # estimated new pipe or duct, right-angle routes


class DisciplineFollow(Frozen):
    discipline: Discipline
    status: Literal["checked", "no_model", "not_aligned"]
    source: str | None = None
    reason: str | None = None  # why not checked
    elements: int = 0  # of the model on this storey's height
    line: str  # the lane in one sentence, server-written
    summary: Summary = Summary()
    marks: tuple[ServiceMark, ...] = ()
    actions: tuple[ServiceAction, ...] = ()


class ServicesFollow(Frozen):
    storey: str | None
    disciplines: tuple[DisciplineFollow, ...]  # always the four lanes, in LANES order
    unknowns: tuple[str, ...] = ()
    credits: tuple[str, ...] = ()  # the service models' licence credits

"""Response models shared by several routes (docs/API.md). Every route returns a pydantic model,
so /openapi.json describes every response; unknown fields are refused so a fixture that drifts
from the code fails its test (tests/api/test_api_fixtures.py)."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.composition import second_counter_of
from app.core.drawing.model import Drawing, ScaleStatus
from app.core.ingest.model import (
    DRAWING_KINDS,
    ContentKind,
    DrawingInfo,
    FileState,
    FileTrace,
    Normalised,
    ProjectStatus,
)
from app.core.pipeline.model import Route

# The kinds a drawing is read from: a sheet (stage 7 places the drawing model on its page) or a
# model; DXF and SVG are other renderings only (pipeline/ingest.py NO_SHEET)
GIVES_A_DRAWING: frozenset[ContentKind] = frozenset(
    {"pdf_vector", "pdf_scan", "png_plan", "jpeg_plan", "photo_plan", "ifc"}
)


class View(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(View):
    """Every error: one sentence, a code, and FastAPI's list for a request that fails validation."""

    detail: str
    code: str
    errors: list[dict[str, object]] | None = None


class ScaleView(View):
    """The sheet's scale as read. `ratio`: N of a printed "1:N", None when the text is no ratio."""

    status: ScaleStatus
    text: str | None
    ratio: float | None
    source: str | None


class PageView(View):
    page: int
    width: float
    height: float
    unit: Literal["px", "pt"]
    url: str
    normalised: Normalised | None  # how an image sheet was made upright; None for a PDF page
    scale: ScaleView  # the drawing's scale, the same on each of its pages
    scale_text: str | None  # the printed scale, "1:100"; None: none printed or found
    storey: str | None  # the storey of the plan on this page; None: no plan, or several storeys


RATIO = re.compile(r"\s*1\s*[:/]\s*(\d+(?:\.\d+)?)\s*")


def scale_view(drawing: Drawing) -> ScaleView:
    scale = drawing.scale
    found = None if scale.text is None else RATIO.fullmatch(scale.text)
    return ScaleView(
        status=scale.status,
        text=scale.text,
        ratio=None if found is None else float(found.group(1)),
        source=scale.source,
    )


def page_views(drawing_id: str, drawing: Drawing, normalised: Normalised | None) -> list[PageView]:
    scale = scale_view(drawing)
    views: list[PageView] = []
    for page in drawing.pages:
        storeys = {
            str(plan.storey)
            for plan in drawing.plans
            if plan.page == page.page and plan.storey is not None
        }
        views.append(
            PageView(
                page=page.page,
                width=page.width,
                height=page.height,
                unit=page.unit,
                url=f"/api/drawings/{drawing_id}/pages/{page.page}.png",
                normalised=normalised,
                scale=scale,
                scale_text=scale.text,
                storey=next(iter(storeys)) if len(storeys) == 1 else None,
            )
        )
    return views


class Reader(View):
    """How a drawing was read: its route, the file it was read from and that route's reader."""

    route: Route | None
    source: str | None
    extractor: str | None
    second_counter: str
    question_parser: str


# The ifc extractor on a sheet of its model: what it gives is what the sheet draws (plan_drawing),
# the model only names each element; the model's own count is the second count (R3-qa-5-1)
IFC_SHEET = "ifc_sheet"


def reader_of(info: DrawingInfo, twice: bool, names: dict[str, str]) -> Reader:
    """`names`: composition.readers(settings), the adapter of each route and port. `twice`: the
    second counter measured what is shown (a drawing: anything on it, stage 8 wrote its
    conflicts; an answer: the answered quantity); else it is named "none". A sheet read with
    its IFC model is named as read from the sheet, by `IFC_SHEET`."""
    sheet = info.route == "bim" and info.kind != "ifc" and names["bim"] == "ifc"
    extractor = None if info.route is None else names[info.route]
    return Reader(
        route=info.route,
        source=info.path if sheet else info.source,
        extractor=IFC_SHEET if sheet else extractor,
        second_counter=second_counter_of(names, info.route) if twice else "none",
        question_parser=names["question_parser"],
    )


class Rendering(View):
    drawing_id: str
    file: str


class DrawingEntry(View):
    """One drawing of a project: one per group of renderings of the same plan."""

    drawing_id: str
    group: str
    file: str
    kind: str | None
    route: Route | None
    source: str | None
    state: FileState
    other_renderings: list[Rendering]


class Skipped(View):
    """A file ingest set aside, with the reason."""

    path: str
    reason: str


class ProjectView(ProjectStatus):
    """Ingest's project status, plus the project's drawings, one per plan."""

    drawings: tuple[DrawingEntry, ...]
    skipped: tuple[Skipped, ...]  # the files set aside, in upload order
    # The drawings the upload holds, one per group of renderings that has a sheet or a model.
    # None until it is known (queued, or files not grouped yet); then final: it never drops.
    expected_drawings: int | None


def skipped_of(status: ProjectStatus) -> tuple[Skipped, ...]:
    return tuple(
        Skipped(path=file.path, reason=file.reason)
        for file in status.files
        if file.state == "set_aside"
    )


def expected_drawings_of(status: ProjectStatus) -> int | None:
    """The groups that give a drawing, where groups holding the same content (a copy under
    another name) are one drawing, as `drawings_of` lists them. A group gives a drawing when it
    holds a sheet or a model (`GIVES_A_DRAWING`); a group of only DXF or SVG files has no page
    to place one on. None while the count is not known: the project is queued, or a file of the
    running project is not grouped yet (each file would count as its own drawing). A file set
    aside after it was grouped (its reading failed) still counts, so the number never drops."""
    if status.state == "queued":
        return None
    if status.state == "running" and any(
        file.group is None and file.state in ("queued", "running") for file in status.files
    ):
        return None
    groups: dict[str, set[str]] = {}
    gives: set[str] = set()
    for file in status.files:
        if file.group is None or file.kind not in DRAWING_KINDS:
            continue  # set aside or text before grouping
        groups.setdefault(file.group, set()).add(file.sha256 or file.path)
        if file.kind in GIVES_A_DRAWING:
            gives.add(file.group)
    drawings: list[set[str]] = []
    for key, contents in groups.items():
        if key not in gives:
            continue
        same = [found for found in drawings if found & contents]
        for found in same:
            drawings.remove(found)
            contents = contents | found
        drawings.append(contents)
    return len(drawings)


class ProjectTrace(View):
    project_id: str
    files: list[FileTrace]

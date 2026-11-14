"""What project ingest reports: the state of every file of an upload, and its trace per stage.

The interface the API reads (`.agents/ingest.md` has it in words): `ProjectStatus` lists the
files with their state and reason, `FileTrace` adds one `StageTrace` per stage the file went
through.
"""

from typing import Literal, cast

from pydantic import ConfigDict, Field, model_validator

from app.core.model import Frozen
from app.core.pipeline.model import Route

FileState = Literal["queued", "running", "ready", "flagged", "text_only", "set_aside"]
FINISHED: frozenset[FileState] = frozenset({"ready", "flagged", "text_only", "set_aside"})
ProjectState = Literal["queued", "running", "done", "failed"]

# What a file is, from its content (stage 3). The first eight go into the pipeline.
ContentKind = Literal[
    "pdf_vector",  # a drawn PDF: paths and text objects
    "pdf_scan",  # a PDF whose page is one big image (a scan)
    "png_plan",  # a drawing as an image: mostly white paper with dark lines
    "jpeg_plan",
    "photo_plan",  # a camera photo of a drawing: perspective, background around the paper
    "ifc",
    "dxf",
    "svg",
    "pdf_text",  # a PDF with text and next to no drawing: a specification, a letter
    "text",  # plain text (txt, csv, md, json)
    "photo",  # a camera photo that is not of a drawing
    "pdf_encrypted",  # no empty password opens it
    "dwg",  # needs converting to DXF first (requirement I13, not built)
    "office",  # a Word, Excel or PowerPoint file
    "archive",  # a zip that was not unpacked (nested deeper than one level)
    "unknown",
]
DRAWING_KINDS: frozenset[ContentKind] = frozenset(
    {"pdf_vector", "pdf_scan", "png_plan", "jpeg_plan", "photo_plan", "ifc", "dxf", "svg"}
)
TEXT_KINDS: frozenset[ContentKind] = frozenset({"pdf_text", "text"})

# The stages a file's trace can name, in pipeline order.
Stage = Literal[
    "unpack",
    "hash",
    "identify",
    "group",
    "route",
    "cache",
    "normalise",
    "extract",
    "second_count",
    "takeoff",  # the counting rules (stage 9) and the takeoff (stage 10), timed together
    "write",
]


class Entry(Frozen):
    """One file of an upload, as the unpacker gives it: its bytes, or why it was refused."""

    path: str  # inside the archive, "/"-separated; the upload's name for a single file
    size: int = Field(ge=0)  # uncompressed, as the archive declares it
    data: bytes | None = None
    refused: str | None = None  # set: the file is set aside before it is read


class LaterPage(Frozen):
    """A page after page 1 of a PDF that holds a drawing, as a PDF of its own: ingest reads it as
    a file `<name>#p<number>.pdf` (a set's page 1 is read with the file itself)."""

    number: int = Field(ge=2)
    data: bytes = Field(repr=False)


class Probed(Frozen):
    """Stage 3: the content kind, and how it was decided, in words."""

    kind: ContentKind
    did: str
    pages: tuple[LaterPage, ...] = ()  # a multi-page PDF's later drawn pages, in page order


# File triage (decision 0010): is an uploaded image a floor plan, and if not, what is it and does
# it belong to the project. Unsure means floor_plan: a plan set aside would never be read.
TriageClass = Literal["floor_plan", "other_drawing", "not_drawing"]
Verdict = Literal["related", "unrelated", "unsure"]
# The probe kinds triage looks at: images and scans (vector PDFs, models and CAD are not triaged).
TRIAGED_KINDS: frozenset[ContentKind] = frozenset(
    {"png_plan", "jpeg_plan", "photo_plan", "pdf_scan", "photo"}
)


class _Classed(Frozen):
    """`class` is a Python keyword, so the field is `class_` under the JSON name `class`."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        serialize_by_alias=True,
        validate_by_name=True,
        validate_by_alias=True,
    )


class Classified(_Classed):
    """Step 1: what the classifier made of one image."""

    class_: TriageClass = Field(alias="class")
    p_plan: float = Field(ge=0, le=1)  # P(a floor plan anywhere on the page)
    method: str  # in plain words, e.g. "local classifier v1 (EfficientNet-B0, CPU)"
    cost_usd: float = Field(default=0.0, ge=0)


class Description(Frozen):
    """Step 2, for a file that is not a floor plan: what the picture shows, in words."""

    text: str  # 1-3 plain sentences
    subject: str  # a short label: "south elevation of a two-storey house"
    text_seen: tuple[str, ...] = Field(default=(), max_length=20)  # words printed on it
    language: str | None = None  # of text_seen, ISO 639-1; None: none read
    model: str  # which describer
    cost_usd: float = Field(default=0.0, ge=0)


class Relevance(Frozen):
    """Step 3, once the project's plans are read: does the described file belong to it."""

    verdict: Verdict
    why: str  # one sentence naming what matched or what is missing
    matched_on: tuple[str, ...] = ()
    plans: tuple[str, ...] = ()  # drawing ids of the project's plans it relates to
    judge: str  # which judge, in plain words


class Overrule(Frozen):
    """A person's call on a file's relevance; the judge's own verdict stays as it was."""

    verdict: Literal["related", "unrelated"]
    by: str
    at: str  # ISO 8601, UTC


class Triage(_Classed):
    """FileStatus.triage: what triage made of an image file (decision 0010). Build a changed one
    with `model_validate`, not `model_copy`, so `verdict` follows `overruled` and `relevance`."""

    class_: TriageClass = Field(alias="class")
    p_plan: float = Field(ge=0, le=1)
    method: str
    description: Description | None = None  # only for a file that is not a floor plan
    relevance: Relevance | None = None  # set when the project's ingest finishes
    overruled: Overrule | None = None
    # What counts now: the person's call, else the judge's; None while not judged
    verdict: Verdict | None = None
    # Why `description` or `relevance` is null, in a plain sentence; None when both are set
    note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _verdict(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        fields = cast(dict[str, object], data)
        said = [_verdict_of(fields.get("overruled")), _verdict_of(fields.get("relevance"))]
        return {**fields, "verdict": next((found for found in said if found), None)}


def _verdict_of(found: object) -> str | None:
    """The verdict of an overrule or relevance, given as a model or as its fields."""
    if isinstance(found, dict):
        verdict = cast(dict[str, object], found).get("verdict")
    else:
        verdict = getattr(found, "verdict", None)
    return verdict if isinstance(verdict, str) else None


class Unavailable(Frozen):
    """A triage port's declared degraded mode: it could not answer, and says why."""

    note: str


class ProjectContext(Frozen):
    """What a described file is judged against: the project's own data, once its plans are read."""

    plans: tuple[str, ...]  # drawing ids of the project's floor plans
    plan_text: tuple[str, ...]  # text read on them: room and flat labels, storeys, table titles
    file_names: tuple[str, ...]  # every file's path in the upload
    descriptions: tuple[str, ...]  # the other described files' subjects


class StageTrace(Frozen):
    stage: Stage
    did: str  # what the stage did, one readable line
    ms: float = Field(ge=0)
    output: str = ""  # what it produced, in short
    failure: str | None = None  # set when the stage failed; the file is then set aside
    cost_usd: float = Field(default=0.0, ge=0)  # model calls paid for (app/core/cost.py)


Point = tuple[float, float]
Quad = tuple[Point, Point, Point, Point]


class Normalised(Frozen):
    """How an image was brought into the frame every page size, box and served page is in:
    EXIF orientation applied, then any turn, deskew or perspective correction. The pipeline
    reads the normalised image, never the upload's bytes."""

    exif: int | None = None  # the EXIF orientation tag (1-8) of the upload; None: none given
    rotated: int = 0  # degrees clockwise turned after the EXIF turn: 0, 90, 180, 270
    deskew_deg: float = 0.0
    rectified: bool = False  # perspective corrected by the `Rectifier` (RECTIFIER setting)
    # The paper's corners in the upload (after the EXIF turn, as a browser shows it) as fractions
    # of its size: top left, top right, bottom right, bottom left; None: not rectified.
    quad: Quad | None = None
    width: int = Field(ge=1)  # the normalised image, in pixels
    height: int = Field(ge=1)
    rectifier: str | None = None  # how it was rectified, e.g. "R1 contour quad"


class Rectified(Frozen):
    """A rectifier's result: the paper seen straight on, and where it was in the image."""

    data: bytes = Field(exclude=True, repr=False)  # the rectified image, PNG or JPEG
    quad: Quad  # the paper's corners in the image it was given, as fractions of it
    width: int = Field(ge=1)  # of the rectified image, in pixels
    height: int = Field(ge=1)
    method: str  # how it was found, shown in the trace and the status


class FileStatus(Frozen):
    id: str  # f1, f2... in the order the upload lists the files
    path: str
    size: int = Field(ge=0)
    sha256: str | None = None  # None: refused before it was read
    kind: ContentKind | None = None  # None: not identified (refused, or still queued)
    state: FileState = "queued"
    reason: str = ""
    group: str | None = None
    route: Route | None = None
    source: str | None = None  # the file of its group the drawing was read from
    drawing_id: str | None = None
    reused: bool = False  # True: the same content was ingested before with the same readers
    takeoff: dict[str, int | float] = Field(default_factory=dict[str, int | float])
    ms: float = Field(default=0, ge=0)
    stage: Stage | None = (
        None  # the stage it is in while running, else the last one it went through
    )
    cost_usd: float = Field(default=0.0, ge=0)
    normalised: Normalised | None = None  # an image sheet: how its frame was made
    # Set for an image file when triage is on (decision 0010); left out of the JSON otherwise
    triage: Triage | None = Field(default=None, exclude_if=lambda value: value is None)


class ProjectStatus(Frozen):
    id: str
    name: str
    state: ProjectState
    created_at: str  # ISO 8601, UTC
    started_at: str | None = (
        None  # ISO 8601, UTC: when the run began (after the queue); None: not yet
    )
    finished_at: str | None = None  # ISO 8601, UTC: when it ended, done or failed; None: not yet
    files: tuple[FileStatus, ...] = ()
    counts: dict[FileState, int] = Field(default_factory=dict[FileState, int])
    readers: dict[str, str] = Field(default_factory=dict[str, str])  # route -> adapter name
    error: str | None = None
    ms: float = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)


class SecondCount(Frozen):
    """What the second method did on a drawing: quantities it measured and where it disagreed."""

    measured: int = Field(ge=0)
    conflicts: int = Field(ge=0)


class FileTrace(Frozen):
    project_id: str
    file: FileStatus
    stages: tuple[StageTrace, ...]
    # Set by the API from the file's drawing (None: no drawing yet, or nothing measured twice)
    second_count: SecondCount | None = None


SheetKind = Literal["pdf", "png", "jpeg", "ifc"]  # a file a drawing model is written for


class DrawingInfo(Frozen):
    """Where a drawing model came from: its file (a sheet, or an IFC model with no page), the
    route that read it and the file it was read from."""

    drawing_id: str
    project_id: str  # where it was first ingested
    path: str
    kind: SheetKind
    route: Route | None = None
    source: str | None = None  # path of the file it was read from, in that project
    normalised: Normalised | None = None
    flags: tuple[str, ...] = ()  # how the page was read: a phone photo, a scan (Outcome.flags)


class SheetFile(Frozen):
    """The file a drawing model is placed on, for rendering its pages."""

    drawing_id: str
    path: str
    kind: Literal["pdf", "png", "jpeg"]
    route: Route | None = None
    source: str | None = None
    data: bytes = Field(exclude=True, repr=False)  # normalised: the frame the boxes are in
    normalised: Normalised | None = None


class Outcome(Frozen):
    """What ingest made of one file of a group, kept by content so the same file in the same
    group is not ingested again. Paths of the group are named by their sha256, so a copy under
    another name reuses it."""

    key: str  # the drawing id when `has_drawing`
    project_id: str  # where it was first ingested
    path: str
    sheet_kind: SheetKind | None = None
    state: FileState
    reason: str
    route: Route | None = None
    source_sha256: str | None = None
    source: str | None = None  # its path in `project_id`
    has_drawing: bool = False
    takeoff: dict[str, int | float] = Field(default_factory=dict[str, int | float])
    stages: tuple[StageTrace, ...] = ()
    normalised: Normalised | None = None
    flags: tuple[str, ...] = ()  # how the page was read, for every answer (judge.reading_flags)

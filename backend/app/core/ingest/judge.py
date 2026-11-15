"""A file's end state from its drawing model, and the pipeline's trace lines as stages."""

from collections.abc import Mapping, Sequence

from app.core.drawing.model import Conflict, Drawing
from app.core.ingest.model import (
    CARBON_FLAG,
    CARBON_PART_FLAG,
    CarbonRead,
    ContentKind,
    FileState,
    Normalised,
    Stage,
    StageTrace,
)
from app.core.pipeline.ingest import nothing_read
from app.core.pipeline.model import Route
from app.core.wording import CONFLICT_WORDS, ROUTE_WORDS, SCALE_WORDS, count, route_words

# The pipeline's trace line prefixes (app/core/pipeline/ingest.py) after stage 5, by stage.
# The counting rules and the takeoff run together, so they are one timed stage.
STAGE_OF_LINE: dict[str, Stage] = {
    "normalise": "normalise",
    "extract": "extract",
    "second count": "second_count",
    "rules": "takeoff",
    "takeoff": "takeoff",
}


def judge(
    drawing: Drawing,
    kind: ContentKind,
    route: Route,
    reader: str | None,
    frame: Normalised | None = None,
    carbon: CarbonRead | None = None,
    unruled: bool = False,
) -> tuple[FileState, str]:
    """`ready` when the route's reader read the drawing and nothing needs a look; `flagged`
    with every reason a person should look at it. `reader`: the route's adapter name; `frame`:
    how an image was normalised; `carbon`: what Gemini Carbon read of it (reading_flags);
    `unruled`: a drawn PDF read as an image (VECTOR_FALLBACK)."""
    if drawing.model_objects is not None and not drawing.pages:
        found = (
            count(len(drawing.model_objects), "model object")
            if drawing.model_objects
            else "no wall, door, window or room in the model"  # a services model (QA B4)
        )
    else:
        tables = len(drawing.tables or ())
        schedules = f"{count(tables, 'schedule')}, " if tables else ""
        found = (
            f"{count(len(drawing.elements), 'element')}, {count(len(drawing.rooms), 'room')}, "
            f"{schedules}{SCALE_WORDS[drawing.scale.status]}"
        )
    flags: list[str] = []
    disputed = [entry for entry in drawing.conflicts or () if entry.status == "conflict"]
    conflicts = [entry for entry in disputed if entry.quantity != "scale"]
    if conflicts:
        what = ", ".join(sorted({CONFLICT_WORDS[entry.quantity] for entry in conflicts}))
        flags.append(f"{count(len(conflicts), 'conflict')} between the two methods ({what})")
    flags += [scale_flag(entry) for entry in disputed if entry.quantity == "scale"]
    empty = read_nothing(drawing, route, reader)
    if empty is not None:
        flags.append(empty)
    flags += reading_flags(kind, frame, carbon, unruled)
    if flags:
        return "flagged", f"{'; '.join(flags)} ({found})"
    return "ready", f"read on the {route_words(route)}: {found}"


UNRULED_FLAG = "a drawn PDF without reading rules, read as an image"


def scale_flag(entry: Conflict) -> str:
    """A `scale` conflict in words. It is not a conflict a person settles in the Conflicts list
    (no takeoff quantity is the scale, takeoff._conflict_keys): a rule picks one of the two, or
    none does and the estimate stays the sheet's scale (printed.py); either way the file is
    flagged so a person checks the scale its areas and lengths rest on (QA R3-A1)."""
    if entry.resolution is None:
        return "the scale read two ways disagrees and no rule decides between them"
    return f"the scale read two ways disagrees: a rule keeps {entry.resolution.rule}"


def read_nothing(drawing: Drawing, route: Route, reader: str | None) -> str | None:
    """Why the route's reader read nothing from the drawing, or None when it read something
    (a schedule sheet reads tables). `reader` "hello" is the do-nothing stand-in."""
    if not nothing_read(drawing):
        return None
    if reader == "hello":
        return f"not read: this setup has no reader for the {route_words(route)}"
    why = drawing.notes[0] if drawing.notes else "nothing it knows was found"
    return f"the {ROUTE_WORDS[route]} reader read nothing: {why}"


def reading_flags(
    kind: ContentKind,
    frame: Normalised | None,
    carbon: CarbonRead | None = None,
    unruled: bool = False,
) -> tuple[str, ...]:
    """The flags about how the page itself was read (a phone photo, a scan, a drawn PDF with no
    reading rules read as an image, by Gemini Carbon alone): every answer on the drawing carries
    them, none of its answers is certified, and a group the reader found nothing of is not a
    count of 0 (review/ask.py). A conflict or an empty read is said where it shows (its row,
    no-reader). They are part of the stored reading; the sheet-kind step's flag is the
    project's (triage.sheet_flag, with_sheet_flag)."""
    flags: tuple[str, ...] = ()
    if kind == "pdf_scan":
        flags = ("a scanned PDF, read as an image",)
    elif unruled:  # VECTOR_FALLBACK: its readers were made for scans and photos, not this sheet
        flags = (UNRULED_FLAG,)
    elif kind == "photo_plan" and frame is not None and frame.rectified:
        flags = (f"a phone photo, rectified by {frame.rectifier}: check the paper's corners",)
    elif kind == "photo_plan":
        flags = ("a phone photo, read without perspective correction",)
    if carbon == "elements":
        flags += (CARBON_FLAG,)
    elif carbon == "part":
        flags += (CARBON_PART_FLAG,)
    return flags


def with_sheet_flag(state: FileState, reason: str, flag: str | None) -> tuple[FileState, str]:
    """A read file's state and reason in its project: the stored reading's, flagged when the
    project's triage doubts the sheet is a floor plan (triage.sheet_flag). The flag is not in the
    stored reading, which is shared by content across projects and triage settings."""
    if flag is None:
        return state, reason
    return "flagged", f"{flag}; {reason}"


def pipeline_stages(
    lines: Sequence[str], ms: Mapping[Stage, float], usd: Mapping[Stage, float]
) -> list[StageTrace]:
    """The pipeline's lines from stage 6 on, one `StageTrace` per stage with its time and the
    model calls it paid for."""
    merged: dict[Stage, list[str]] = {}
    for line in lines:
        prefix, _, said = line.partition(": ")
        stage = STAGE_OF_LINE.get(prefix)
        if stage is not None:
            merged.setdefault(stage, []).append(said if stage != "takeoff" else line)
    return [
        StageTrace(
            stage=stage,
            did="; ".join(said),
            ms=ms.get(stage, 0.0),
            output=said[-1],
            cost_usd=usd.get(stage, 0.0),
        )
        for stage, said in merged.items()
    ]

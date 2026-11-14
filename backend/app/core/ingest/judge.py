"""A file's end state from its drawing model, and the pipeline's trace lines as stages."""

from collections.abc import Mapping, Sequence

from app.core.drawing.model import Drawing
from app.core.ingest.model import ContentKind, FileState, Normalised, Stage, StageTrace
from app.core.pipeline.model import Route
from app.core.wording import SCALE_WORDS, count

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
) -> tuple[FileState, str]:
    """`ready` when the route's reader read the drawing and nothing needs a look; `flagged`
    with every reason a person should look at it. `reader`: the route's adapter name; `frame`:
    how an image was normalised."""
    if drawing.model_objects is not None and not drawing.pages:
        found = count(len(drawing.model_objects), "model object")
    else:
        tables = len(drawing.tables or ())
        schedules = f"{count(tables, 'schedule')}, " if tables else ""
        found = (
            f"{count(len(drawing.elements), 'element')}, {count(len(drawing.rooms), 'room')}, "
            f"{schedules}{SCALE_WORDS[drawing.scale.status]}"
        )
    flags: list[str] = []
    conflicts = [entry for entry in drawing.conflicts or () if entry.status == "conflict"]
    if conflicts:
        what = ", ".join(sorted({entry.quantity for entry in conflicts}))
        flags.append(f"{count(len(conflicts), 'conflict')} between the two methods ({what})")
    empty = read_nothing(drawing, route, reader)
    if empty is not None:
        flags.append(empty)
    flags += reading_flags(kind, frame)
    if flags:
        return "flagged", f"{'; '.join(flags)} ({found})"
    return "ready", f"read on the {route} route: {found}"


def read_nothing(drawing: Drawing, route: Route, reader: str | None) -> str | None:
    """Why the route's reader read nothing from the drawing, or None when it read something
    (a schedule sheet reads tables). `reader` "hello" is the do-nothing stand-in."""
    if drawing.read != () or drawing.tables:
        return None
    if reader == "hello":
        return f"no reader for the {route} route yet: nothing was read"
    why = drawing.notes[0] if drawing.notes else "nothing it knows was found"
    return f"the {route} reader read nothing: {why}"


def reading_flags(kind: ContentKind, frame: Normalised | None) -> tuple[str, ...]:
    """The flags about how the page itself was read (a phone photo, a scan): every answer on
    the drawing carries them, and a group the reader found nothing of is not a count of 0
    (review/ask.py). A conflict or an empty read is said where it shows (its row, no-reader)."""
    if kind == "pdf_scan":
        return ("a scanned PDF, read as an image",)
    if kind == "photo_plan" and frame is not None and frame.rectified:
        return (f"a phone photo, rectified by {frame.rectifier}: check the paper's corners",)
    if kind == "photo_plan":
        return ("a phone photo, read without perspective correction",)
    return ()


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

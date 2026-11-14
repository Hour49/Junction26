"""A file's end state from its drawing model, and the pipeline's trace lines as stages."""

from collections.abc import Mapping, Sequence

from app.core.drawing.model import Drawing
from app.core.ingest.model import ContentKind, FileState, Normalised, Stage, StageTrace
from app.core.pipeline.model import Route

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
        found = f"{len(drawing.model_objects)} model objects"
    else:
        tables = len(drawing.tables or ())
        schedules = f"{tables} schedule{'s' if tables > 1 else ''}, " if tables else ""
        found = (
            f"{len(drawing.elements)} elements, {len(drawing.rooms)} rooms, {schedules}"
            f"scale {drawing.scale.status}"
        )
    flags: list[str] = []
    conflicts = [entry for entry in drawing.conflicts or () if entry.status == "conflict"]
    if conflicts:
        what = ", ".join(sorted({entry.quantity for entry in conflicts}))
        flags.append(f"{len(conflicts)} conflict(s) between the two methods ({what})")
    read_nothing = drawing.read == () and not drawing.tables  # a schedule sheet reads tables
    if read_nothing and reader == "hello":
        flags.append(f"no reader for the {route} route yet: nothing was read")
    elif read_nothing:
        why = drawing.notes[0] if drawing.notes else "nothing it knows was found"
        flags.append(f"the {route} reader read nothing: {why}")
    if kind == "pdf_scan":
        flags.append("a scanned PDF, read as an image")
    if kind == "photo_plan" and frame is not None and frame.rectified:
        flags.append(f"a phone photo, rectified by {frame.rectifier}: check the paper's corners")
    elif kind == "photo_plan":
        flags.append("a phone photo, read without perspective correction")
    if flags:
        return "flagged", f"{'; '.join(flags)} ({found})"
    return "ready", f"read on the {route} route: {found}"


def pipeline_stages(lines: Sequence[str], ms: Mapping[Stage, float]) -> list[StageTrace]:
    """The pipeline's lines from stage 6 on, one `StageTrace` per stage with its time."""
    merged: dict[Stage, list[str]] = {}
    for line in lines:
        prefix, _, said = line.partition(": ")
        stage = STAGE_OF_LINE.get(prefix)
        if stage is not None:
            merged.setdefault(stage, []).append(said if stage != "takeoff" else line)
    return [
        StageTrace(stage=stage, did="; ".join(said), ms=ms.get(stage, 0.0), output=said[-1])
        for stage, said in merged.items()
    ]

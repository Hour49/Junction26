"""File triage (decision 0010): every uploaded image is asked "is this a floor plan?" before any
reader sees it. A floor plan goes on as today. Anything else is kept and set aside with its
reason, described in words, and once the project's plans are read, judged against the project:
related, unrelated or unsure. The judge's verdict is a suggestion a person can overrule.

Pure functions over the ports in ports.py; the service calls them (service.py)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.core.drawing.model import Drawing
from app.core.ingest.model import (
    TRIAGED_KINDS,
    ContentKind,
    Description,
    FileStatus,
    Overrule,
    Probed,
    ProjectContext,
    Relevance,
    Triage,
    TriageClass,
    Unavailable,
)
from app.core.ingest.ports import Classifier, Describer, RelevanceJudge
from app.core.pipeline.model import FileKind

CLASS_WORDS: dict[TriageClass, str] = {
    "floor_plan": "a floor plan",
    "other_drawing": "another kind of drawing (an elevation, section, site plan, detail or cover)",
    "not_drawing": "not a drawing",
}
NO_PLAN = "no floor plan in the project to compare with"
# Triage.note: why `description` or `relevance` is null, in plain words (decision 0010)
NOTE_PLAN = "a floor plan: it is read, so it is not described or judged"
NOTE_NO_DESCRIBER = "not described: no description model is set up, so it is not judged"
NOTE_RUNNING = "not judged yet: the project is still being read"
NOTE_NO_JUDGE = "not judged: no relevance judge is set up"
NOTE_FAILED = "not judged: the project's ingest failed"
NOTE_JUDGE_FAILED = "not judged: the judge failed"
MAX_PLAN_TEXT = 200  # labels kept for the judge, so a huge model can't make a huge prompt


@dataclass(frozen=True)
class TriageSteps:
    """The triage ports as composition built them; the describer and judge may be off."""

    classifier: Classifier
    describer: Describer | None
    judge: RelevanceJudge | None
    name: str  # the adapters, in words, e.g. "classifier=rules, describer=rules, judge=rules"


@dataclass(frozen=True)
class Triaged:
    """Steps 1 and 2 for one file: the triage (None: not triaged, or the classifier could not
    answer) and what to add to the identify stage's line."""

    triage: Triage | None
    said: str


def triaged(
    steps: TriageSteps, data: bytes, probed: Probed, file_format: FileKind | None
) -> Triaged:
    """Classifies an image file and describes it when it is not a floor plan."""
    if not _is_image(probed.kind, file_format):
        return Triaged(None, "")
    classified = steps.classifier.classify(data, probed)
    if isinstance(classified, Unavailable):
        return Triaged(None, f"triage not available: {classified.note}; read as today")
    said = f"triage: {_how(classified.class_, classified.p_plan, classified.method)}"
    description: Description | None = None
    if classified.class_ == "floor_plan":
        note = NOTE_PLAN
    elif steps.describer is None:
        note = NOTE_NO_DESCRIBER
    else:
        found = steps.describer.describe(data, classified)
        if isinstance(found, Unavailable):
            note = f"not described: {found.note}"
        else:
            description, note = found, NOTE_RUNNING
            said += f"; described as {found.subject} ({found.model})"
    if description is None and note != NOTE_PLAN:
        said += f"; {note}"
    triage = Triage.model_validate(
        {
            "class": classified.class_,
            "p_plan": classified.p_plan,
            "method": classified.method,
            "description": description,
            "note": note,
        }
    )
    return Triaged(triage, said)


def judged(triage: Triage, found: Relevance | None, note: str | None) -> Triage:
    """The triage with step 3's outcome: a verdict, or why there is none."""
    return Triage.model_validate({**triage.model_dump(), "relevance": found, "note": note})


def overruled(triage: Triage, overrule: Overrule | None) -> Triage:
    return Triage.model_validate({**triage.model_dump(), "overruled": overrule})


def kind_after(probed: Probed, triage: Triage | None, file_format: FileKind | None) -> Probed:
    """The probe's kind once triage has spoken. With triage on, the classifier alone decides
    plan or not: an image it calls a floor plan is read as one even where the probe (or the kind
    signal's not-a-drawing rule) said otherwise."""
    if triage is None or triage.class_ != "floor_plan":
        return probed
    said = f"{probed.did}; triage calls it a floor plan, so it is read as one"
    if probed.kind == "photo":
        return Probed(kind="photo_plan", did=said)
    if probed.kind == "unknown" and file_format == "png":
        return Probed(kind="png_plan", did=said)
    if probed.kind == "unknown" and file_format == "jpeg":
        return Probed(kind="jpeg_plan", did=said)
    return probed


def set_aside_reason(triage: Triage) -> str:
    """The file's reason; after "not a floor plan: " plain words, shown as they are."""
    return f"not a floor plan: {_how(triage.class_, triage.p_plan, triage.method)}"


def _how(found: TriageClass, p_plan: float, method: str) -> str:
    return f"{CLASS_WORDS[found]} (P(plan) {p_plan:.2f}, {method})"


def is_not_plan(file: FileStatus) -> bool:
    return file.triage is not None and file.triage.class_ != "floor_plan"


def context_of(files: Iterable[FileStatus], drawings: Mapping[str, Drawing]) -> ProjectContext:
    """The project as the judge sees it: its plans' text, its file names and its descriptions.
    `drawings`: the project's drawing models by id."""
    files = tuple(files)
    text: list[str] = []
    for drawing in drawings.values():
        text += [room.label for room in drawing.rooms if room.label]
        text += [flat.label for flat in drawing.apartments if flat.label]
        text += [str(plan.storey) for plan in drawing.plans if plan.storey is not None]
        text += [table.title for table in drawing.tables or () if table.title]
        text += [found.storey for found in drawing.model_objects or () if found.storey]
        text += [found.name for found in drawing.model_objects or () if found.name]
    return ProjectContext(
        plans=tuple(drawings),
        plan_text=tuple(dict.fromkeys(" ".join(said.split()) for said in text))[:MAX_PLAN_TEXT],
        file_names=tuple(file.path for file in files),
        descriptions=tuple(
            file.triage.description.subject
            for file in files
            if file.triage is not None and file.triage.description is not None
        ),
    )


def relevance_of(
    judge: RelevanceJudge, description: Description, context: ProjectContext
) -> Relevance | Unavailable:
    """Step 3 for one described file. With no plan in the project there is nothing to compare
    with, so the verdict is unsure without asking the judge."""
    if not context.plans:
        return Relevance(verdict="unsure", why=f"Unsure: {NO_PLAN}.", judge="no judge asked")
    mine = tuple(said for said in context.descriptions if said != description.subject)
    found = judge.judge(description, context.model_copy(update={"descriptions": mine}))
    if isinstance(found, Unavailable):
        return found
    # only this project's plans, so a screen can name them from the project's drawings
    plans = tuple(plan for plan in found.plans if plan in context.plans)
    return found.model_copy(update={"plans": plans})


def _is_image(kind: ContentKind, file_format: FileKind | None) -> bool:
    """Images and scans; also an image the probe or the kind signal called unknown, since with
    triage on the classifier makes that call."""
    return kind in TRIAGED_KINDS or (kind == "unknown" and file_format in ("png", "jpeg"))

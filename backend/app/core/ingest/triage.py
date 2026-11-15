"""File triage (decision 0010): every uploaded image is asked "is this a floor plan?" before any
reader sees it. A floor plan goes on as today. Anything else is kept and set aside with its
reason, described in words, and once the project's plans are read, judged against the project:
related, unrelated or unsure. The judge's verdict is a suggestion a person can overrule.

Pure functions over the ports in ports.py; the service calls them (service.py)."""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.core.drawing.model import Drawing
from app.core.ingest.model import (
    SHEET_PLAN_KINDS,
    TRIAGED_KINDS,
    ContentKind,
    Description,
    FileStatus,
    Overrule,
    Probed,
    ProjectContext,
    ReadAsPlan,
    Relevance,
    Sheet,
    Triage,
    TriageClass,
    Unavailable,
)
from app.core.ingest.ports import Classifier, Describer, RelevanceJudge
from app.core.pipeline.model import FileKind
from app.core.wording import kind_words

# The triaged kinds the probe calls a drawing (it calls a `photo` not one)
DRAWN_KINDS: frozenset[ContentKind] = TRIAGED_KINDS - {"photo"}
CLASS_WORDS: dict[TriageClass, str] = {
    "floor_plan": "a floor plan",
    "other_drawing": "another kind of drawing (an elevation, section, site plan, detail or cover)",
    "not_drawing": "not a drawing",
}
NO_PLAN = "no floor plan in the project to compare with"
# Triage.note: why `description` or `relevance` is null, in plain words (decision 0010)
# Triage's own step only: the evidence index may still describe the file, by its own sheet-kind
# call (EVIDENCE_SCOPE, app/core/evidence), so the note never says it is not described (detail's
# audit: site.jpg read anyway, then described for the index under "it is not described")
NOTE_PLAN = "read as a floor plan, so triage does not describe or judge it"
NOTE_NO_DESCRIBER = "not described: no description model is set up, so it is not judged"
# the same file once a judge that reads no description judged it
NOTE_NO_DESCRIBER_JUDGED = "not described: no description model is set up"
NOTE_RUNNING = "not judged yet: the project is still being read"
NOTE_NO_JUDGE = "not judged: no relevance judge is set up"
NOTE_FAILED = "not judged: the project's ingest failed"
NOTE_JUDGE_FAILED = "not judged: the judge failed"
MAX_PLAN_TEXT = 200  # labels kept for the judge, so a huge model can't make a huge prompt

# Relevance by rule (decision 0010 section 8): the words of a description matched against the
# project's facts. Words of 4 letters or more; these never count, since every sheet has them.
RULE = "rule on the words printed on it and whether it shows a building, no model"
MIN_LETTERS = 4
MAX_MATCHED = 5
STOP_WORDS = frozenset(
    {
        # drawing words, en / fi / sv / de / fr, casefolded with accents folded
        "plan",
        "plans",
        "floor",
        "floors",
        "scale",
        "section",
        "sections",
        "elevation",
        "elevations",
        "drawing",
        "drawings",
        "sheet",
        "detail",
        "details",
        "site",
        "view",
        "views",
        "level",
        "storey",
        "ground",
        "first",
        "second",
        "third",
        "north",
        "south",
        "east",
        "west",
        "pohja",
        "pohjapiirros",
        "leikkaus",
        "julkisivu",
        "mittakaava",
        "kerros",
        "asemapiirros",
        "piirustus",
        "ritning",
        "planritning",
        "sektion",
        "fasad",
        "skala",
        "vaning",
        "grundriss",
        "schnitt",
        "ansicht",
        "massstab",
        "geschoss",
        "zeichnung",
        "blatt",
        "coupe",
        "facade",
        "echelle",
        "etage",
        "dessin",
        "niveau",
        # file and picture words
        "jpeg",
        "tiff",
        "heic",
        "webp",
        "image",
        "photo",
        "scan",
        "page",
        "copy",
        "file",
        # small words
        "with",
        "from",
        "that",
        "this",
    }
)
LETTERS = re.compile(r"[^\W\d_]+")


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
    how = _how(classified.class_, classified.p_plan, classified.method, classified.sheet)
    said = f"triage: {how}"
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
            said += f"; described as {found.subject}"  # the model id is `description.model`
    if description is None and note != NOTE_PLAN:
        said += f"; {note}"
    triage = Triage.model_validate(
        {
            "class": classified.class_,
            "p_plan": classified.p_plan,
            "method": classified.method,
            "register": classified.register_,
            "description": description,
            "note": note,
            "sheet": classified.sheet,
        }
    )
    return Triaged(triage, said)


def judged(triage: Triage, found: Relevance | None, note: str | None) -> Triage:
    """The triage with step 3's outcome: a verdict, or why there is none."""
    return Triage.model_validate({**triage.model_dump(), "relevance": found, "note": note})


def overruled(triage: Triage, overrule: Overrule | None) -> Triage:
    return Triage.model_validate({**triage.model_dump(), "overruled": overrule})


def read_as_plan(triage: Triage, call: ReadAsPlan | None) -> Triage:
    return Triage.model_validate({**triage.model_dump(), "read_as_plan": call})


def plan_kind(kind: ContentKind | None, file_format: FileKind | None) -> ContentKind | None:
    """The kind a file a person had read as a floor plan is read as: a photo is a photo of a
    plan, an image the probe called unknown is a drawing image; None: it can't be read as one."""
    if kind == "photo":
        return "photo_plan"
    if kind == "unknown" and file_format == "png":
        return "png_plan"
    if kind == "unknown" and file_format == "jpeg":
        return "jpeg_plan"
    return kind if kind in TRIAGED_KINDS else None


def kind_after(probed: Probed, triage: Triage | None, file_format: FileKind | None) -> Probed:
    """The probe's kind once triage has spoken. With triage on, the classifier alone decides
    plan or not: an image it calls a floor plan is read as one even where the probe (or the kind
    signal's not-a-drawing rule) said otherwise. Where the two disagree, `did` says the probe's
    line was its guess and what triage made of it, so the identify stage's line ends on the
    outcome (QA R4-A10: "a photo, not of a drawing", then output "photo of a drawing")."""
    if triage is None:
        return probed
    if triage.class_ == "not_drawing" and probed.kind in DRAWN_KINDS:
        said = f"the probe guessed {probed.did}; triage calls it not a drawing, so it is not read"
        return probed.model_copy(update={"did": said})
    if triage.class_ != "floor_plan":
        return probed
    if probed.kind == "photo":
        kind: ContentKind = "photo_plan"
    elif probed.kind == "unknown" and file_format == "png":
        kind = "png_plan"
    elif probed.kind == "unknown" and file_format == "jpeg":
        kind = "jpeg_plan"
    else:
        return probed
    said = f"the probe guessed {probed.did}; triage calls it a floor plan, so it is read as a "
    return Probed(kind=kind, did=said + kind_words(kind))


def set_aside_reason(triage: Triage) -> str:
    """The file's reason, in plain words shown as they are; P(plan) and the method are in the
    triage itself and in the identify stage's line. A sheet the sheet-kind step set aside is named
    by its kind, with its printed title and sheet number when there are any."""
    return f"not a floor plan: {not_plan_words(triage)}"


def not_plan_words(triage: Triage) -> str:
    """What triage called a file that is not a floor plan, in plain words: the sheet-kind
    step's kind with the printed title and sheet number when that step set it aside, else the
    class's words."""
    sheet = triage.sheet
    if sheet is None or sheet.decision != "set_aside":
        return CLASS_WORDS[triage.class_]
    printed = ", ".join(said for said in (sheet.title, sheet.sheet_number) if said)
    return sheet.kind_words + (f" ({printed})" if printed else "")


def sheet_doubt(triage: Triage | None) -> str | None:
    """The line every answer read off this file carries when the sheet-kind step doubted it is a
    floor plan but called it a plan kind; None otherwise, and once a person had it read as a
    floor plan. A doubted non-plan kind is flagged instead (sheet_flag), and the flag's note on
    each answer says what it looks like."""
    if triage is None or triage.sheet is None or triage.read_as_plan is not None:
        return None
    if triage.sheet.decision != "doubt" or triage.sheet.kind not in SHEET_PLAN_KINDS:
        return None
    return "This sheet may not be a floor plan."


def sheet_flag(triage: Triage | None) -> str | None:
    """The reading flag for a sheet the sheet-kind step doubted and called a non-plan kind (a
    warn-only set-aside, SHEET_KIND_SET_ASIDE=false): the drawing is flagged at upload like a
    Carbon-alone read, so none of its answers is certified and each is Low (orchestrator,
    2026-11-14). None otherwise, and once a person had it read as a floor plan."""
    if triage is None or triage.read_as_plan is not None or not doubted_not_plan(triage):
        return None
    assert triage.sheet is not None  # doubted_not_plan
    return f"the sheet may not be a floor plan: it looks like {triage.sheet.kind_words}"


def not_a_drawing(triage: Triage | None) -> bool:
    """The sheet-kind step called the sheet not a drawing at all (a screenshot, a photo of a
    room) and it was read only because the step warns instead of setting aside
    (SHEET_KIND_SET_ASIDE=false, sheet_flag): its drawing is kept, flagged, but is no drawing a
    screen counts as ready (QA R4-A9). False once a person had it read as a floor plan."""
    if sheet_flag(triage) is None or triage is None or triage.sheet is None:
        return False
    return triage.sheet.kind == "not_a_drawing"


# Over this the step is sure enough that a services sheet's symbols are not doors or fixtures
# (review-596: 0 of 327 real plans in 892 labelled cached replies; T3 is 0.98)
SURE_SERVICES = 0.9


def symbols_refused(triage: Triage | None) -> str | None:
    """sheet_flag's flag when the step called the doubted sheet a services (MEP) plan at a
    confidence over SURE_SERVICES: its door, window and fixture counts are refused (R3-C3: T3, a
    piping plan, answered "6 toilets" from 1 WC and 5 tanks). None otherwise: every other doubted
    kind stays warn-only, answered Low with the flag (orchestrator, 2026-11-15 04:39)."""
    flag = sheet_flag(triage)
    if flag is None or triage is None or triage.sheet is None:
        return None
    sure = triage.sheet.kind == "mep_plan" and triage.sheet.confidence > SURE_SERVICES
    return flag if sure else None


def doubted_not_plan(triage: Triage) -> bool:
    """The sheet-kind step doubted the sheet is a floor plan and called it a non-plan kind (read,
    and flagged until a person has it read as a floor plan)."""
    sheet = triage.sheet
    return sheet is not None and sheet.decision == "doubt" and sheet.kind not in SHEET_PLAN_KINDS


def _how(found: TriageClass, p_plan: float, method: str, sheet: Sheet | None = None) -> str:
    """Triage's call in words. A sheet the sheet kind doubts is read as a plan and flagged, so it
    is not headlined "a floor plan": the line says what decided it (detail's audit: site.jpg,
    "a floor plan (P(plan) 0.00, ...)" for a sheet the model called not a drawing)."""
    words = CLASS_WORDS[found]
    if found == "floor_plan" and sheet is not None and sheet.decision == "doubt":
        why = (
            "the sheet kind is unsure"
            if sheet.kind == "architectural_floor_plan"
            else f"the sheet kind calls it {sheet.kind_words}"
        )
        words = f"read as a floor plan, but flagged: {why}"
    return f"{words} (P(plan) {p_plan:.2f}, {method})"


def called_not_plan(file: FileStatus) -> bool:
    """Triage's classifier called the file not a floor plan (a person may have had it read)."""
    return file.triage is not None and file.triage.class_ != "floor_plan"


def is_not_plan(file: FileStatus) -> bool:
    """Not a floor plan now: called so by triage, and no person had it read as one."""
    return called_not_plan(file) and file.triage is not None and file.triage.read_as_plan is None


def context_of(
    name: str, files: Iterable[FileStatus], drawings: Mapping[str, Drawing]
) -> ProjectContext:
    """The project as the judge sees it: its name, its plans' text, its file names and its
    descriptions. `drawings`: the project's drawing models by id."""
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
        project_name=name,
        plan_text=tuple(dict.fromkeys(" ".join(said.split()) for said in text))[:MAX_PLAN_TEXT],
        file_names=tuple(file.path for file in files),
        descriptions=tuple(
            file.triage.description.subject
            for file in files
            if file.triage is not None and file.triage.description is not None
        ),
    )


def to_judge(files: Iterable[FileStatus], judge: RelevanceJudge) -> list[FileStatus]:
    """The files step 3 judges: each non-plan described and waiting for its verdict, and, for a
    judge that reads no description, each non-plan nothing described as well."""
    return [
        file
        for file in files
        if file.triage is not None
        and file.triage.class_ != "floor_plan"
        and file.triage.relevance is None
        and (
            file.triage.note == NOTE_RUNNING
            or (file.triage.description is None and not judge.reads_description)
        )
    ]


def judged_note(triage: Triage, not_judged: str | None) -> str | None:
    """The note once step 3 ran: why the description is null (a described file: None), and
    why there is no verdict when there is none (`not_judged`)."""
    if triage.description is not None:
        return not_judged
    said = NOTE_NO_DESCRIBER_JUDGED if triage.note == NOTE_NO_DESCRIBER else triage.note
    return said if not_judged is None else f"{said}; {not_judged}"


def relevance_of(
    judge: RelevanceJudge,
    kind: TriageClass,
    description: Description | None,
    context: ProjectContext,
    path: str,
) -> Relevance | Unavailable:
    """Step 3 for the file at `path`. With no plan in the project there is nothing to compare
    with, so the verdict is unsure without asking the judge. The judge sees the project without
    the file itself: neither its own subject nor its own name."""
    if not context.plans:
        return Relevance(verdict="unsure", why=f"Unsure: {NO_PLAN}.", judge="no judge asked")
    own = description.subject if description is not None else None
    others = {
        "descriptions": tuple(said for said in context.descriptions if said != own),
        "file_names": tuple(name for name in context.file_names if name != path),
    }
    found = judge.judge(kind, description, context.model_copy(update=others))
    if isinstance(found, Unavailable):
        return found
    # only this project's plans, so a screen can name them from the project's drawings
    plans = tuple(plan for plan in found.plans if plan in context.plans)
    return found.model_copy(update={"plans": plans})


def relevance_by_rule(description: Description, context: ProjectContext) -> Relevance:
    """Decision 0010 section 8 (with Tudor's fleet's review, #152): related only when a word
    printed on the picture is among the project's facts (its name, its other files' and folders'
    names, its plans' text); a picture that shows a building but matches nothing is unsure, for a
    person; one with no building and no match is unrelated. The `why` names what matched, or that
    nothing did."""
    printed = words_of((description.visible_text, *description.text_seen))
    facts = {
        "name": words_of((context.project_name,)),
        "file and folder names": words_of(context.file_names),
        "plan text": words_of(context.plan_text),
    }
    shared = sorted(word for word in printed if any(word in found for found in facts.values()))
    shared = shared[:MAX_MATCHED]
    building = "it shows a building" if description.shows_building else "it shows no building"
    if shared:
        places = [place for place, found in facts.items() if any(word in found for word in shared)]
        matched = tuple(
            f"'{word}' ({', '.join(place for place, found in facts.items() if word in found)})"
            for word in shared
        )
        said = ", ".join(f"'{word}'" for word in shared)
        why = (
            f"Related: {said}, printed on it, {'is' if len(shared) == 1 else 'are'} in the "
            f"project's {' and '.join(places)}; {building}."
        )
        return Relevance(verdict="related", why=why, matched_on=matched, judge=RULE)
    seen = (
        "none of its printed words is in the project's name, file and folder names or plan text"
        if printed
        else "it has no printed text"
    )
    if description.shows_building:
        why = f"Unsure: {building}, but {seen}."
        return Relevance(verdict="unsure", why=why, judge=RULE)
    return Relevance(verdict="unrelated", why=f"Unrelated: {building}, and {seen}.", judge=RULE)


def words_of(texts: Iterable[str]) -> frozenset[str]:
    """The words the rule matches: casefolded, accents folded, runs of letters only (so a
    number is never one), 4 letters or more, not a stop word."""
    found: set[str] = set()
    for text in texts:
        plain = unicodedata.normalize("NFKD", text.casefold())
        plain = "".join(char for char in plain if not unicodedata.combining(char))
        found.update(LETTERS.findall(plain))
    return frozenset(word for word in found if len(word) >= MIN_LETTERS and word not in STOP_WORDS)


def _is_image(kind: ContentKind, file_format: FileKind | None) -> bool:
    """Images and scans; also an image the probe or the kind signal called unknown, since with
    triage on the classifier makes that call."""
    return kind in TRIAGED_KINDS or (kind == "unknown" and file_format in ("png", "jpeg"))

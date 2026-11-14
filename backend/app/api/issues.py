"""GET /api/projects/{project_id}/issues (and issues.csv): every finding in a project as one
located issue, the list Stoa's floor view takes in (decision 0008, story #140). Built from what
the API already holds: the takeoff's disagreements, the question log, ingest's file states and,
with `?pack=`, the failed building-code checks (decision 0009); no model call."""

import csv
import hashlib
import io
import re
import zipfile
from collections.abc import Iterator, Mapping
from pathlib import PurePosixPath
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.adapters.evidence_render import render as render_evidence
from app.adapters.page_render import render_png
from app.api.checks import RulePacksDep, find_pack
from app.api.deps import Credits, CreditsDep, Ingest, IngestDep, ProjectId, ReviewsDep, SettingsDep
from app.api.drawings import credit_of
from app.api.project_ask import LACKS
from app.api.questions import AskedQuestion, asked
from app.api.takeoff import Takeoff, takeoff_rows
from app.api.takeoff import _cell as csv_cell  # pyright: ignore[reportPrivateUsage]
from app.api.views import View, drawings_of
from app.composition import readers
from app.core.checks.check import check_drawing
from app.core.checks.model import CheckResult, RuleCheck, RulePack
from app.core.drawing.model import Box, Drawing, Polygon
from app.core.ingest.judge import read_nothing
from app.core.ingest.model import FileStatus, ProjectStatus
from app.core.ingest.triage import CLASS_WORDS, called_not_plan, is_not_plan
from app.core.review.model import MarkView, Row
from app.core.review.ports import ReviewStore
from app.core.review.proof import NO_PROOF, PALETTE, ClassKey, check
from app.core.review.review import NotAllowedError, disputes
from app.core.wording import count as count_of
from app.settings import Settings

router = APIRouter(prefix="/api/projects")

# Every kind planned, so a screen's exhaustive switch never meets a new one (decision 0008). Not
# produced yet: double_check (#129: an uncertified answer, one issue per disputed place).
# code_check_failed only with ?pack= (decision 0009).
IssueKind = Literal[
    "conflict",
    "refused_answer",
    "set_aside",
    "reading_flag",
    "code_check_failed",
    "double_check",
    "unrelated_file",
]
Severity = Literal["fails_rule", "needs_person", "note"]
IssueState = Literal["open", "settled", "signed_off"]
SEVERITIES: tuple[Severity, ...] = ("fails_rule", "needs_person", "note")  # the list's order
# A refusal about our parser, not the building: not an issue (decision 0008)
NOT_ABOUT_THE_DRAWING = "unsupported-question"
CSV_COLUMNS = (
    "id", "kind", "severity", "state", "file", "file_id", "drawing_id", "floor", "page",
    "x0", "y0", "x1", "y1", "mark_id", "why", "quantity", "question", "reason", "check",
)  # fmt: skip
SEVERITY_WORDS: dict[Severity, str] = {
    "fails_rule": "fails a rule", "needs_person": "needs a person", "note": "note",
}  # fmt: skip
SEVERITY_COLOURS: dict[Severity, str] = {  # from the marks' palette: red, orange, blue
    "fails_rule": PALETTE[0], "needs_person": PALETTE[4], "note": PALETTE[1],
}  # fmt: skip
PAGE_WIDTH = 1600  # px: a marked page in the zip, as the viewer shows a page
PACK = Query(
    description="a building-code rule pack (decision 0009): its failed checks join the list"
)


class IssueLinks(View):
    """API paths to open the issue; None where there is nothing to open."""

    drawing: str | None
    takeoff: str | None
    trace: str | None
    checks: str | None  # the drawing's checks for the pack (code_check_failed only)


class Issue(View):
    id: str  # unique in the project, stable across calls: kind, drawing (or file), source ref
    kind: IssueKind
    severity: Severity
    state: IssueState
    drawing_id: str | None  # None: a file with no drawing (most set-aside files)
    file: str  # as the project uploaded it
    file_id: str | None
    floor: str | None  # only where a source states it (an IFC storey); never guessed
    page: int | None
    box: Box | None  # page fractions, as MarkView.box
    polygon: Polygon | None  # the outline, when the place is a room's mark (MarkView.polygon)
    mark_id: str | None  # the takeoff's MarkView.id when the place is a takeoff mark
    why: str  # one plain sentence
    quantity: str | None  # the takeoff key
    question: str | None  # the question as asked
    reason: str | None  # ingest's reason
    check: str | None  # `<pack>:<CheckResult.id>` (code_check_failed)
    links: IssueLinks


class ProjectIssues(View):
    project_id: str
    pack: str | None  # the rule pack asked for; None: no code checks in the list
    # By severity (fails_rule, needs_person, note), then drawing in the project's order (files
    # with no drawing after, in upload order), page, box top, then the source ref
    issues: list[Issue]


@router.get("/{project_id}/issues")
def project_issues(
    project_id: ProjectId,
    ingest: IngestDep,
    reviews: ReviewsDep,
    settings: SettingsDep,
    packs: RulePacksDep,
    pack: Annotated[str | None, PACK] = None,
) -> ProjectIssues:
    """Every finding of the project as a located issue (decision 0008)."""
    return issues_of(project_id, pack, ingest, reviews, settings, packs)


@router.get(
    "/{project_id}/issues.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "the issues as CSV"}},
)
def project_issues_csv(
    project_id: ProjectId,
    ingest: IngestDep,
    reviews: ReviewsDep,
    settings: SettingsDep,
    packs: RulePacksDep,
    pack: Annotated[str | None, PACK] = None,
) -> Response:
    """The same issues as GET …/issues, one CSV row each."""
    found = issues_of(project_id, pack, ingest, reviews, settings, packs)
    name = _download(ingest.status(project_id).name, pack, "csv")
    return _attachment(_csv(found.issues, numbered=False), "text/csv; charset=utf-8", name)


@router.get(
    "/{project_id}/issues.zip",
    response_class=Response,
    responses={
        200: {"content": {"application/zip": {}}, "description": "issues.csv and marked pages"}
    },
)
def project_issues_zip(
    project_id: ProjectId,
    ingest: IngestDep,
    reviews: ReviewsDep,
    settings: SettingsDep,
    credits: CreditsDep,
    packs: RulePacksDep,
    pack: Annotated[str | None, PACK] = None,
) -> Response:
    """issues.csv with each issue's number `n` first, and one PNG per drawing page that has
    issues with a box: the page with each box drawn and labelled with its `n`."""
    found = issues_of(project_id, pack, ingest, reviews, settings, packs).issues
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("issues.csv", _csv(found, numbered=True))
        names: set[str] = {"issues.csv"}
        for (drawing_id, page), placed in _by_page(found).items():
            name = _unique(f"{_stem(placed[0][1].file)}-p{page}.png", names)
            archive.writestr(name, _marked_page(drawing_id, page, placed, ingest, credits))
    name = _download(ingest.status(project_id).name, pack, "zip")
    return _attachment(out.getvalue(), "application/zip", name)


def _csv(found: list[Issue], numbered: bool) -> str:
    """The issues as CSV; `numbered`: with each one's number in the list first (`n`)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow((("n",) if numbered else ()) + CSV_COLUMNS)
    for n, issue in enumerate(found, start=1):
        x0, y0, x1, y1 = issue.box if issue.box is not None else ("", "", "", "")
        cells = (
            issue.id, issue.kind, issue.severity, issue.state, issue.file, issue.file_id,
            issue.drawing_id, issue.floor, issue.page, x0, y0, x1, y1, issue.mark_id, issue.why,
            issue.quantity, issue.question, issue.reason, issue.check,
        )  # fmt: skip
        row = ["" if cell is None else csv_cell(cell) for cell in cells]
        writer.writerow(([n] if numbered else []) + row)
    return out.getvalue()


def _by_page(found: list[Issue]) -> dict[tuple[str, int], list[tuple[int, Issue]]]:
    """The issues with a place on a page (a drawing, a page and a box), numbered as listed,
    grouped by drawing page in the order they first appear."""
    pages: dict[tuple[str, int], list[tuple[int, Issue]]] = {}
    for n, issue in enumerate(found, start=1):
        if issue.drawing_id is not None and issue.page is not None and issue.box is not None:
            pages.setdefault((issue.drawing_id, issue.page), []).append((n, issue))
    return pages


def _marked_page(
    drawing_id: str, page: int, placed: list[tuple[int, Issue]], ingest: Ingest, credits: Credits
) -> bytes:
    """The page with each issue's box drawn by evidence.png's renderer, numbered with its `n`,
    coloured by severity; the issues' sentences, one per line, and the licence credit under it."""
    marks = [
        MarkView(
            id=issue.id, n=n, page=page, box=issue.box or (0.0, 0.0, 1.0, 1.0),
            polygon=issue.polygon,
            state="counted", value=None, label=SEVERITY_WORDS[issue.severity], ref=None,
            reason=None,
        )
        for n, issue in placed
    ]  # fmt: skip
    keys = tuple(
        ClassKey(label=SEVERITY_WORDS[severity], colour=SEVERITY_COLOURS[severity], count=count)
        for severity in SEVERITIES
        if (count := sum(issue.severity == severity for _, issue in placed))
    )
    said = "\n".join(f"{n}. {issue.why}" for n, issue in placed)  # one line per issue
    proof = NO_PROOF.model_copy(update={"kind": "count", "legend": keys, "arithmetic": said})
    file = placed[0][1].file
    shown = f"{file}, page {page}: {count_of(len(placed), 'issue')}"
    sheet = render_png(ingest.sheet(drawing_id), page, PAGE_WIDTH)
    credit = credit_of(ingest.drawing_info(drawing_id), ingest, credits)
    return render_evidence(sheet, page, marks, proof, shown, credit, PAGE_WIDTH)


def _unique(name: str, taken: set[str]) -> str:
    stem, dot, suffix = name.rpartition(".")
    found, at = name, 2
    while found in taken:
        found, at = f"{stem}-{at}{dot}{suffix}", at + 1
    taken.add(found)
    return found


def _download(project: str, pack: str | None, suffix: str) -> str:
    """`<project name>-issues[-<pack>].<suffix>`, safe in a Content-Disposition header."""
    return f"{_stem(project)}-issues{'' if pack is None else '-' + _stem(pack)}.{suffix}"


def _stem(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", PurePosixPath(path).stem) or "project"


def _attachment(content: str | bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def issues_of(
    project_id: str,
    pack: str | None,
    ingest: Ingest,
    reviews: ReviewStore,
    settings: Settings,
    packs: tuple[RulePack, ...] = (),
) -> ProjectIssues:
    """The project's issues as the routes give them, with `pack`'s failed checks when one is
    named (among `packs`): 404 for an unknown project or pack, 409 until the project is done."""
    status = ingest.status(project_id)  # 404 for a project that doesn't exist
    chosen = None if pack is None else find_pack(packs, pack)  # 404 unknown-pack
    if status.state != "done":
        raise NotAllowedError(f"project {project_id} is {status.state}; list its issues when done")
    found = listed_issues(status, ingest, reviews, settings, pack=chosen)
    return ProjectIssues(project_id=project_id, pack=pack, issues=found)


def listed_issues(
    status: ProjectStatus,
    ingest: Ingest,
    reviews: ReviewStore,
    settings: Settings,
    takeoffs: Mapping[str, Takeoff] | None = None,
    pack: RulePack | None = None,
) -> list[Issue]:
    """The issues of a done project, in the list's order. `takeoffs`: each drawing's takeoff
    in this project, when the caller has them already (the project list's summary). `pack`:
    its failed checks join the list."""
    where = _Files(status)
    found = [
        *([] if pack is None else _code_checks(status, where, ingest, pack)),
        *_conflicts(status, where, ingest, reviews, takeoffs or {}),
        *_reading_flags(status, where, ingest, settings),
        *_set_aside(status, where),
        *_unrelated_files(status),
        *_refusals(status, where, settings),
    ]
    drawings = {entry.drawing_id: at for at, entry in enumerate(drawings_of(status))}
    files = {file.path: at for at, file in enumerate(status.files)}
    last = len(drawings) + len(files)

    def order(issue: Issue) -> tuple[int, int, int, float, str, str]:
        # a file's unrelated_file issue keeps the file's place, also once it has a drawing
        placed = issue.drawing_id if issue.kind != "unrelated_file" else None
        drawing = drawings.get(placed or "")
        at = drawing if drawing is not None else len(drawings) + files.get(issue.file, last)
        top = issue.box[1] if issue.box is not None else 2.0  # no box: after the boxed ones
        ref = issue.check or issue.quantity or issue.question or issue.reason or ""
        return (SEVERITIES.index(issue.severity), at, issue.page or 1_000_000, top, ref, issue.id)

    return sorted(found, key=order)


def open_count(
    status: ProjectStatus,
    ingest: Ingest,
    reviews: ReviewStore,
    settings: Settings,
    takeoffs: Mapping[str, Takeoff],
) -> int:
    """How many issues of the done project are open (no pack: code checks are a screen's
    choice), for ProjectSummary.issues_open."""
    return sum(
        issue.state == "open"
        for issue in listed_issues(status, ingest, reviews, settings, takeoffs)
    )


class _Files:
    """The project's files: the one a drawing is named by, as the project lists the drawing."""

    def __init__(self, status: ProjectStatus) -> None:
        self.project_id = status.id
        self._by_path = {file.path: file for file in status.files}
        self._named = {entry.drawing_id: entry.file for entry in drawings_of(status)}
        for file in status.files:  # another rendering: named by its own file
            if file.drawing_id is not None:
                self._named.setdefault(file.drawing_id, file.path)

    def of(self, drawing_id: str) -> FileStatus | None:
        path = self._named.get(drawing_id)
        return None if path is None else self._by_path[path]


def _issue(
    kind: IssueKind,
    project_id: str,
    file: FileStatus,
    drawing_id: str | None,
    ref: str,
    checks: str | None = None,
    by_file: bool = False,
    **fields: object,
) -> Issue:
    """An issue of the file, its id hashed from what names it (`by_file`: the file, even once it
    has a drawing), its links filled in (`checks`: the drawing's checks for the pack, for a failed
    code check)."""
    named = drawing_id if drawing_id is not None and not by_file else file.id
    digest = hashlib.sha256("\0".join((kind, named, ref)).encode()).hexdigest()  # per project
    at = f"?project={project_id}"
    links = IssueLinks(
        drawing=None if drawing_id is None else f"/api/drawings/{drawing_id}{at}",
        takeoff=None if drawing_id is None else f"/api/drawings/{drawing_id}/takeoff{at}",
        trace=f"/api/projects/{project_id}/files/{file.id}/trace",
        checks=checks,
    )
    defaults: dict[str, object] = {
        "state": "open", "floor": None, "page": None, "box": None, "polygon": None, "mark_id": None,
        "quantity": None, "question": None, "reason": None, "check": None,
    }  # fmt: skip
    return Issue.model_validate(
        {
            **defaults,
            **fields,
            "id": f"{kind}-{digest[:12]}",
            "kind": kind,
            "drawing_id": drawing_id,
            "file": file.path,
            "file_id": file.id,
            "links": links,
        }
    )


def _code_checks(
    status: ProjectStatus, where: _Files, ingest: Ingest, pack: RulePack
) -> Iterator[Issue]:
    """One issue per failed check of the pack (decision 0009), placed on its room or door: the
    result's first subject mark, on a page the drawing has. Cannot tell is not an issue."""
    for entry in drawings_of(status):
        file = where.of(entry.drawing_id)
        assert file is not None  # a listed drawing has its file
        drawing = ingest.drawing(entry.drawing_id)
        sheets = {page.page for page in drawing.pages}
        route = ingest.drawing_info(entry.drawing_id).route  # raster: read off a picture
        checks = f"/api/drawings/{entry.drawing_id}/checks?pack={pack.id}&project={status.id}"
        for rule in check_drawing(drawing, pack, route):
            for result in rule.results:
                if result.status != "fail":
                    continue
                mark = next((m for m in result.marks if m.role == "subject"), None)
                placed = mark if mark is not None and mark.page in sheets else None
                page = None if placed is None else placed.page
                yield _issue(
                    "code_check_failed",
                    status.id,
                    file,
                    entry.drawing_id,
                    f"{pack.id}:{result.id}",
                    severity="fails_rule",
                    floor=_floor(drawing, page),
                    page=page,
                    box=None if placed is None else placed.box,
                    polygon=None if placed is None else placed.polygon,
                    mark_id=None if placed is None else placed.mark_id,
                    why=_check_why(result, rule),
                    quantity=result.quantity,
                    check=f"{pack.id}:{result.id}",
                    checks=checks,
                )


def _check_why(result: CheckResult, rule: RuleCheck) -> str:
    """The result's sentences, then the clause it quotes (decision 0009)."""
    return f"{result.why} ({rule.clause.ref})"


def _conflicts(
    status: ProjectStatus,
    where: _Files,
    ingest: Ingest,
    reviews: ReviewStore,
    takeoffs: Mapping[str, Takeoff],
) -> Iterator[Issue]:
    """One issue per disagreement between two methods (`disputes`: a room keyed under several
    names is one), placed where it was measured."""
    for entry in drawings_of(status):
        file = where.of(entry.drawing_id)
        assert file is not None  # a listed drawing has its file
        drawing = ingest.drawing(entry.drawing_id)
        rows = takeoffs.get(entry.drawing_id) or takeoff_rows(
            entry.drawing_id, ingest, reviews, zeros=False, project=status.id
        )
        for row in disputes(rows.quantities):
            page, box, polygon, mark_id = _place(row, drawing)
            yield _issue(
                "conflict",
                status.id,
                file,
                entry.drawing_id,
                row.key,
                severity="needs_person" if row.needs_person else "note",
                state=_state(row),
                floor=_floor(drawing, page) or row.scope.storey,
                page=page,
                box=box,
                polygon=polygon,
                mark_id=mark_id,
                why=_conflict_why(row),
                quantity=row.key,
            )


def _state(row: Row) -> IssueState:
    if row.signed is not None:
        return "signed_off"
    if row.settled is not None or (row.conflict is not None and row.conflict.resolution):
        return "settled"
    return "open"


def _conflict_why(row: Row) -> str:
    said = check(row) or "two methods disagree"
    why = f"{row.label[:1].upper()}{row.label[1:]}: {said[:1].lower()}{said[1:]}"
    if row.signed is not None:
        why += f"; signed off by {row.signed.by}"
    return f"{why}."


def _place(row: Row, drawing: Drawing) -> tuple[int | None, Box | None, Polygon | None, str | None]:
    """Where to open the drawing (decision 0008), as (page, box, polygon, mark id): the row's
    one mark (a room, with its outline), else the box a method read the value from, else the
    plan when it is the only one on the page; else nowhere. Only a page the drawing has: a
    building model has none."""
    sheets = {page.page for page in drawing.pages}
    if len(row.marks) == 1 and row.marks[0].page in sheets:
        mark = row.marks[0]
        return mark.page, mark.box, mark.polygon, mark.id
    if row.conflict is not None:
        for value in row.conflict.values:
            if value.page in sheets and value.box is not None:
                return value.page, value.box, None, None
    pages = {mark.page for mark in row.marks} or sheets
    if len(pages) == 1 and pages <= sheets:
        (page,) = pages
        plans = [plan for plan in drawing.plans if plan.page == page]
        if len(plans) == 1:
            return page, plans[0].box, None, None
    return None, None, None, None


def _floor(drawing: Drawing, page: int | None) -> str | None:
    """The storey of the plans on the page, when they name one (today only an IFC sheet's)."""
    storeys = {plan.storey for plan in drawing.plans if plan.page == page}
    if len(storeys) != 1:
        return None
    (storey,) = storeys
    return None if storey is None else str(storey)


def _reading_flags(
    status: ProjectStatus, where: _Files, ingest: Ingest, settings: Settings
) -> Iterator[Issue]:
    """How a drawing's page was read (a phone photo, a scan), and a reader that read nothing."""
    names = readers(settings)
    for entry in drawings_of(status):
        file = where.of(entry.drawing_id)
        assert file is not None  # a listed drawing has its file
        info = ingest.drawing_info(entry.drawing_id)
        said = list(info.flags)
        if info.route is not None:
            empty = read_nothing(ingest.drawing(entry.drawing_id), info.route, names[info.route])
            said += [] if empty is None else [empty]
        if said:
            why = "; ".join(said)
            pages = ingest.drawing(entry.drawing_id).pages
            yield _issue(
                "reading_flag",
                status.id,
                file,
                entry.drawing_id,
                "reading",  # one per drawing: its id stays when the wording changes
                severity="note",
                page=pages[0].page if len(pages) == 1 else None,  # the whole sheet: no box
                why=f"{why[:1].upper()}{why[1:]}.",
                reason=why,
            )


def _set_aside(status: ProjectStatus, where: _Files) -> Iterator[Issue]:
    """Files set aside at ingest, but not those triage called not a floor plan: those are
    `unrelated_file` issues (decision 0010)."""
    for file in status.files:
        if file.state == "set_aside" and not is_not_plan(file):
            yield _issue(
                "set_aside",
                status.id,
                file,
                file.drawing_id,
                file.path,
                severity="note",
                why=f"Set aside at ingest: {file.reason}.",
                reason=file.reason,
            )


def _unrelated_files(status: ProjectStatus) -> Iterator[Issue]:
    """One issue per file triage called not a floor plan whose verdict is not `related`
    (unjudged and undescribed ones too), and per such file a person made a call on (decision
    0010, board #152), or a person had read as a floor plan. The severity is the judge's
    (`unsure` needs a person), so a person's call settles the issue in place: same id, same place
    in the list, also once the file is read and has a drawing."""
    for file in status.files:
        triage = file.triage
        if triage is None or not called_not_plan(file):
            continue
        called = triage.overruled is not None or triage.read_as_plan is not None
        if triage.verdict == "related" and not called:
            continue
        judged = triage.relevance.verdict if triage.relevance is not None else None
        what = CLASS_WORDS[triage.class_]
        if triage.description is not None:
            what = f"{what}: {triage.description.subject}"
        why = f"Not a floor plan ({what})."
        if triage.relevance is not None:
            why += f" {triage.relevance.why}"
        elif triage.note is not None:
            why += f" {triage.note[0].upper()}{triage.note[1:]}."
        if triage.overruled is not None:
            why += f" {triage.overruled.by} says it is {triage.overruled.verdict}."
        if triage.read_as_plan is not None:
            why += f" {triage.read_as_plan.by} had it read as a floor plan."
        yield _issue(
            "unrelated_file",
            status.id,
            file,
            file.drawing_id,  # once read as a floor plan, a link to open it (R6-a-4)
            file.path,
            by_file=True,  # the same id before and after it is read
            severity="needs_person" if judged == "unsure" else "note",
            state="settled" if called else "open",
            why=why,
            reason=triage.verdict,
        )


def _refusals(status: ProjectStatus, where: _Files, settings: Settings) -> Iterator[Issue]:
    """The questions in the log whose last ask on a drawing got no number, for a reason about
    the drawing (decision 0008); a line without its refusal code (older) says too little."""
    last: dict[tuple[str, str], AskedQuestion] = {}
    for line in asked(settings.projects_dir, status.id):
        last[(line.drawing_id, " ".join(line.question.split()).lower())] = line
    for (drawing_id, _), line in last.items():
        code = line.refusal
        file = where.of(drawing_id)
        if not line.refused or code is None or code == NOT_ABOUT_THE_DRAWING or file is None:
            continue
        yield _issue(
            "refused_answer",
            status.id,
            file,
            drawing_id,
            " ".join(line.question.split()).lower(),
            severity="note",
            why=f'No answer to "{line.question}": the drawing {LACKS[code][0]}.',
            question=line.question,
        )

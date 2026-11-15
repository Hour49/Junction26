"""The evidence step for one file (decision 0012 sources v2, EVIDENCE_SCOPE=all_non_plan): what the
file is in the project's evidence index (report 7.1-7.4).

- a picture (pictures.py): the kind call, then the describer; a drawn or scanned PDF's own text
  pages are added to it as `text` passages, or are its whole source when the picture is not one;
- a text document (`pdf_text`, `text`): its own text (`text`), no model;
- a file nothing reads (DWG, office, archive, encrypted PDF, IFC, an unknown non-image, a refused
  entry): listed by name (`listed`), its passage says why its content is not read;
- DXF and SVG: not a source (no render for a kind call; most are copies of a sheet that has one);
- a second file at a path the upload already used: not a source (set aside at a free name).

Text and listed files carry a `Description` made by rule, so the tools' JSON keeps its shape.
The text itself is not kept: the index reads it again from the stored file."""

from collections.abc import Callable

from app.core.evidence.chunks import KIND_WORDS
from app.core.evidence.file_sources import TextSource, listed_piece, name_words
from app.core.evidence.pictures import EvidenceSteps, is_picture, picture_evidence
from app.core.ingest.model import (
    SECOND_PATH,
    TEXT_KINDS,
    ContentKind,
    Description,
    FileEvidence,
    FileStatus,
)

PDF_PICTURES: frozenset[ContentKind] = frozenset({"pdf_vector", "pdf_scan"})
LISTED: frozenset[ContentKind] = frozenset(
    {"dwg", "office", "archive", "pdf_encrypted", "ifc", "unknown"}
)
IFC_REASON = "a building model, read by the takeoff"
CAD = "a CAD drawing: the evidence index does not read DXF or SVG files"
TEXT_MODEL = "no model: the file's own text"
LISTED_MODEL = "no model: file name and type only"


def file_evidence(
    file: FileStatus, read: Callable[[], bytes], steps: EvidenceSteps
) -> FileEvidence | None:
    """The file's record, or None when the step does not look at it (a file triage set aside
    keeps today's path: its triage description is the source). `read` gives the upload's bytes,
    read only when needed."""
    if file.triage is not None and file.triage.class_ != "floor_plan":
        return None
    if file.state in ("queued", "running"):  # not a finished record
        return None
    if file.state == "set_aside" and file.reason == SECOND_PATH:  # at a name the user never gave
        return None
    kind = file.kind
    if kind in ("dxf", "svg"):
        return FileEvidence(indexed=False, why=CAD)
    if kind is None or (kind in LISTED and not is_picture(file, read)):
        return listed(file)
    if kind in TEXT_KINDS:
        return _text_only(file, steps.texts.text(file.path, kind, read()), kind)
    if not is_picture(file, read):
        return None
    data = read()
    picture = picture_evidence(data, steps.kinds, steps.describer)
    if kind not in PDF_PICTURES:
        return picture
    found = steps.texts.text(file.path, kind, data)
    if found is None:
        return picture
    if picture.indexed:  # its text pages become `text` passages of the described source
        return picture.model_copy(update={"text_pages": found.pages, "text_chars": found.chars})
    text = _text_only(file, found, kind)
    assert text is not None
    why = f"{text.why}; its drawing is not a source ({picture.why})"
    return text.model_copy(
        update={"why": why, "sheet": picture.sheet, "cost_usd": picture.cost_usd}
    )


def listed(file: FileStatus) -> FileEvidence:
    """A file whose content nothing in this path reads, listed by name with why."""
    kind = file.kind or "not_read"  # a refused entry, or one identify could not read
    reason = IFC_REASON if kind == "ifc" else file.reason or "nothing reads this kind of file"
    passage = listed_piece(file.path, KIND_WORDS[kind], reason)
    described = _rule_made(file.path, passage.text, "other", LISTED_MODEL)
    why = f"listed by name only: {reason.strip().rstrip('.')}"
    return FileEvidence(indexed=True, how="listed", kind=kind, why=why, description=described)


def _text_only(
    file: FileStatus, found: TextSource | None, kind: ContentKind
) -> FileEvidence | None:
    if found is None:
        return FileEvidence(indexed=False, why="no text to index: no page holds text")
    text_kind = {"text": "text_file", "pdf_text": "text_document"}.get(kind, "text_pages")
    summary = found.pieces[0].text
    first = summary.removeprefix(f"{KIND_WORDS[text_kind]}. {name_words(file.path)}. ")
    pages = "page" if found.pages == 1 else "pages"
    why = f"searched by its own text: {found.pages} {pages}, {found.chars} characters"
    if found.cut:
        why += ", cut at 200,000 characters"
    return FileEvidence(
        indexed=True,
        how="text",
        kind=text_kind,
        why=why,
        description=_rule_made(file.path, first, "text_page", TEXT_MODEL),
        text_pages=found.pages,
        text_chars=found.chars,
    )


def _rule_made(path: str, text: str, what_it_is: str, model: str) -> Description:
    return Description.model_validate(
        {
            "subject": name_words(path),
            "text": text,
            "detail": "",
            "visible_text": "",
            "text_seen": [],
            "language": None,
            "what_it_is": what_it_is,
            "shows_building": False,
            "model": model,
            "cost_usd": 0.0,
        }
    )

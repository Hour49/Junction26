"""EVIDENCE_SCOPE=all_non_plan for files that are not pictures (decision 0012 sources v2, report
7.1, 7.4 and 7.7): a text document is searched by its own text, page by page; a drawn PDF's text
pages are searched too; a file nothing reads is listed by name; a DXF is not a source. The text is
read again from the stored file when the index is built, so the index is a function of the status
and the stored files."""

import zipfile
from pathlib import Path

import pytest
from conftest import MakeService
from evidence_fakes import FakeKinds, picture_kind
from pdf_sheets import SheetPdf
from test_ingest_multipage import pdf_of
from test_ingest_triage import file_of, zipped
from test_vector_pdf import swiss_sheet
from triage_fakes import FakeDescriber

from app.adapters.archive import DiskProjectStore
from app.adapters.evidence.project import ProjectEvidence
from app.adapters.evidence.store import SqliteEvidenceIndex
from app.adapters.evidence.texts import FileTextReader, StoredTexts
from app.core.evidence.chunks import passages
from app.core.evidence.file_sources import TEXT_CHARS
from app.core.evidence.model import sources
from app.core.evidence.pictures import EvidenceSteps
from app.core.evidence.step import CAD
from app.core.ingest.model import ProjectStatus

PLAN = swiss_sheet().pdf()


def text_page(*lines: str) -> bytes:
    sheet = SheetPdf(595, 842)
    for at, line in enumerate(lines):
        sheet.text(line, 50, 60 + 14 * at, size=9)
    return sheet.pdf()


def page_of(word: str) -> bytes:
    """A specification page whose every line names `word` (well over 200 characters)."""
    return text_page(
        *[f"Clause {n}: the {word} shall be fitted as the schedule says." for n in range(12)]
    )


SPEC = pdf_of(page_of("doors"), page_of("windows"), page_of("insulation"))  # 3 text pages
DRAWN_WITH_NOTES = pdf_of(PLAN, page_of("handrails"))  # a drawn plan, then a notes page
NOTES = b"Site notes.\nCall the architect on +358 40 123 4567 or mail anna@example.com.\n"
DWG = b"AC1027" + bytes(200)
DXF = b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"
KINDS = {
    PLAN: picture_kind("architectural_floor_plan", True),
    DRAWN_WITH_NOTES: picture_kind("architectural_floor_plan", True),
}


def steps(kinds: FakeKinds | None = None) -> EvidenceSteps:
    return EvidenceSteps(
        kinds=kinds or FakeKinds(KINDS),
        describer=FakeDescriber({}),
        texts=FileTextReader(),
    )


def ingest(make_service: MakeService, root: Path, files: dict[str, bytes]) -> ProjectStatus:
    service = make_service(root=root, evidence_steps=steps())
    return service.wait(service.start("site.zip", zipped(files)))


def index(root: Path, projects: Path) -> SqliteEvidenceIndex:
    texts = StoredTexts(DiskProjectStore(projects), FileTextReader())
    return SqliteEvidenceIndex(root, passages, None, texts)


def evidence_of(root: Path, projects: Path, status: ProjectStatus) -> ProjectEvidence:
    return ProjectEvidence(index(root, projects), status, lambda size, sha256: None)


def test_a_text_pdf_is_searched_by_its_own_text_with_each_passages_page(
    make_service: MakeService, tmp_path: Path
) -> None:
    projects = tmp_path / "projects"
    status = ingest(make_service, projects, {"docs/specification.pdf": SPEC})
    spec = file_of(status, "docs/specification.pdf")
    assert spec.kind == "pdf_text" and spec.evidence is not None
    found = spec.evidence
    assert (found.indexed, found.how, found.kind, found.text_pages) == (
        True,
        "text",
        "text_document",
        3,
    )
    assert found.description is not None and found.description.subject == "specification"
    assert found.description.text.startswith("Clause 0: the doors")
    evidence = evidence_of(tmp_path / "index", projects, status)
    for word, page in (("windows", 2), ("insulation", 3)):
        (hit,) = evidence.search(word, k=1).hits
        assert (hit.how, hit.part, hit.page) == ("text", "text", page)
        detail = evidence.get(hit.id)
        assert detail is not None
        assert (detail.how, detail.part, detail.page) == ("text", "text", page)
        assert word in detail.text and detail.description.model.startswith("no model")


def test_a_drawn_pdfs_text_page_is_a_source_though_its_drawing_is_a_plan(
    make_service: MakeService, tmp_path: Path
) -> None:
    projects = tmp_path / "projects"
    status = ingest(make_service, projects, {"A101.pdf": DRAWN_WITH_NOTES})
    plan = file_of(status, "A101.pdf")
    assert plan.kind == "pdf_vector" and plan.drawing_id is not None  # still read as a plan
    found = plan.evidence
    assert found is not None and (found.how, found.text_pages) == ("text", 1)
    assert found.why.startswith("searched by its own text: 1 page")
    assert "its drawing is not a source (a floor plan" in found.why
    (hit,) = evidence_of(tmp_path / "index", projects, status).search("handrails").hits
    assert (hit.part, hit.page) == ("text", 2)


def test_a_described_drawn_pdf_also_gets_its_text_pages(
    make_service: MakeService, tmp_path: Path
) -> None:
    projects = tmp_path / "projects"
    kinds = FakeKinds({DRAWN_WITH_NOTES: picture_kind("elevation", False)})
    describer = FakeDescriber({DRAWN_WITH_NOTES: ("the south elevation", ())})
    service = make_service(
        root=projects,
        evidence_steps=EvidenceSteps(kinds=kinds, describer=describer, texts=FileTextReader()),
    )
    status = service.wait(service.start("site.zip", zipped({"A200.pdf": DRAWN_WITH_NOTES})))
    found = file_of(status, "A200.pdf").evidence
    assert found is not None and (found.how, found.text_pages) == ("described", 1)
    evidence = evidence_of(tmp_path / "index", projects, status)
    (hit,) = evidence.search("handrails").hits
    assert (hit.how, hit.part, hit.page) == ("described", "text", 2)
    (hit,) = evidence.search("south elevation").hits
    assert hit.part == "summary"  # one summary: the description's


def test_contact_data_is_in_no_passage_and_a_long_text_is_cut(
    make_service: MakeService, tmp_path: Path
) -> None:
    projects = tmp_path / "projects"
    long = "\n".join(f"line {n} of the building description" for n in range(8000)).encode()
    assert len(long) > TEXT_CHARS
    status = ingest(make_service, projects, {"docs/notes.txt": NOTES, "docs/long.txt": long})
    notes = file_of(status, "docs/notes.txt").evidence
    assert notes is not None and (notes.how, notes.kind) == ("text", "text_file")
    cut = file_of(status, "docs/long.txt").evidence
    assert cut is not None and cut.text_chars is not None and cut.text_chars <= TEXT_CHARS
    assert cut.why.endswith("cut at 200,000 characters")
    store = index(tmp_path / "index", projects)
    store.update(status)
    with store.reader(status.id) as reader:
        assert reader.bm25("architect", frozenset({None}))  # the notes are searchable
        texts = [reader.passage(found) for _, found in reader.bm25("architect", frozenset({None}))]
    words = " ".join(found[0].text for found in texts if found is not None)
    assert "architect" in words
    assert "4567" not in words and "anna@example.com" not in words
    assert notes.description is not None and "4567" not in notes.description.text


def test_a_dwg_is_listed_by_name_and_a_dxf_is_not_a_source(
    make_service: MakeService, tmp_path: Path
) -> None:
    projects = tmp_path / "projects"
    files = {"cad/A-801 Door Schedules.dwg": DWG, "cad/detail.dxf": DXF, "plan.pdf": PLAN}
    status = ingest(make_service, projects, files)
    dwg = file_of(status, "cad/A-801 Door Schedules.dwg").evidence
    assert dwg is not None and (dwg.indexed, dwg.how, dwg.kind) == (True, "listed", "dwg")
    assert dwg.why.startswith("listed by name only: a DWG drawing")
    dxf = file_of(status, "cad/detail.dxf").evidence
    assert dxf is not None and (dxf.indexed, dxf.why) == (False, CAD)
    assert [source.path for source in sources(status)] == ["cad/A-801 Door Schedules.dwg"]
    evidence = evidence_of(tmp_path / "index", projects, status)
    (hit,) = evidence.search("door schedules").hits
    assert (hit.how, hit.kind, hit.part) == ("listed", "dwg", "summary")
    detail = evidence.get(hit.id)
    assert detail is not None
    assert detail.text == (
        "DWG drawing, not converted. A 801 Door Schedules. Its content is not read: "
        "a DWG drawing: converting it to DXF is not built yet."
    )
    prompt = evidence.prompt()
    assert "(1 listed by name; 1 dwg)" in prompt
    assert "A file listed by name was not read: say only that it exists." in prompt
    assert "A text document is quoted" not in prompt


def test_a_refused_entry_is_listed_with_its_refusal(
    make_service: MakeService, tmp_path: Path
) -> None:
    buffer = tmp_path / "site.zip"
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("plan.pdf", PLAN)
        archive.writestr("../escape.txt", b"outside")
    service = make_service(root=tmp_path / "projects", evidence_steps=steps())
    status = service.wait(service.start("site.zip", buffer.read_bytes()))
    refused = [file for file in status.files if file.sha256 is None]
    assert refused, "the zip has an entry ingest refuses"
    found = refused[0].evidence
    assert found is not None and (found.how, found.kind) == ("listed", "unknown")
    assert found.why == f"listed by name only: {refused[0].reason.rstrip('.')}"


def test_the_index_rebuilt_from_status_and_stored_files_equals_the_first(
    make_service: MakeService, tmp_path: Path
) -> None:
    projects = tmp_path / "projects"
    files = {"docs/specification.pdf": SPEC, "A101.pdf": DRAWN_WITH_NOTES, "x.dwg": DWG}
    status = ingest(make_service, projects, files)
    first, again = index(tmp_path / "a", projects), index(tmp_path / "b", projects)
    first.update(status)
    again.update(status)

    def dump(store: SqliteEvidenceIndex) -> list[tuple[object, ...]]:
        with store.reader(status.id) as reader:
            db = reader._connection()  # pyright: ignore[reportPrivateUsage]
            assert db is not None
            return db.execute("select id, part, n, page, text from passages order by id").fetchall()

    assert dump(first) == dump(again) and len(dump(first)) > 5
    assert {row[3] for row in dump(first) if row[1] == "text"} == {1, 2, 3}


@pytest.mark.parametrize("scope_off", [True])
def test_scope_off_still_writes_no_evidence_for_text_or_listed_files(
    make_service: MakeService, tmp_path: Path, scope_off: bool
) -> None:
    service = make_service(root=tmp_path / "projects")
    status = service.wait(service.start("site.zip", zipped({"a.pdf": SPEC, "b.dwg": DWG})))
    assert all(file.evidence is None for file in status.files)


def test_a_text_pdfs_drawn_page_is_its_own_file_and_not_in_the_texts_passages(
    make_service: MakeService, tmp_path: Path
) -> None:
    projects = tmp_path / "projects"
    status = ingest(make_service, projects, {"set.pdf": pdf_of(page_of("doors"), PLAN)})
    text = file_of(status, "set.pdf")
    assert text.kind == "pdf_text" and text.evidence is not None
    assert (text.evidence.how, text.evidence.text_pages) == ("text", 1)
    assert any(file.path.startswith("set#p2") for file in status.files)  # the drawn page
    evidence = evidence_of(tmp_path / "index", projects, status)
    assert [hit.file for hit in evidence.search("Küche Balkon").hits] == []

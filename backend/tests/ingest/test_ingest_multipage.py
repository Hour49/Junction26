"""A multi-page PDF (a permit or drawing set): every page after page 1 that holds a drawing is read
as a file of its own, `<name>#p<n>.pdf`, through the normal route; page 1 is read as before, so a
one-page PDF ingests exactly as it did (orchestrator brief, 2026-11-14: a notes cover hid a set)."""

import io

import pypdfium2
from conftest import MakeService
from test_ingest_probe import ink_sketch_pdf
from test_vector_pdf import swiss_sheet

from app.adapters.archive import FileProbe
from app.adapters.archive.probe import MAX_PAGES
from app.core.ingest.model import page_path, split_from
from scripts.make_sample_archive import text_pdf


def pdf_of(*pages: bytes) -> bytes:
    """One PDF made of the first page of each of `pages`, in order."""
    document = pypdfium2.PdfDocument.new()
    for page in pages:
        document.import_pages(pypdfium2.PdfDocument(page))
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def permit_set() -> bytes:
    """A notes cover, then two drawn plans."""
    return pdf_of(text_pdf(), swiss_sheet().pdf(), swiss_sheet().pdf())


def test_the_probe_gives_each_later_drawn_page_as_a_pdf_of_its_own() -> None:
    found = FileProbe().probe(pdf_of(text_pdf(), swiss_sheet().pdf(), text_pdf(), ink_sketch_pdf()))
    assert found.kind == "pdf_text"
    assert found.did.endswith("; pages 2 and 4 hold drawings, each read as a file of its own")
    assert [page.number for page in found.pages] == [2, 4]
    kinds = [FileProbe().probe(page.data) for page in found.pages]
    assert [(probed.kind, "page 1 of 1:" in probed.did) for probed in kinds] == [
        ("pdf_vector", True),
        ("pdf_scan", True),
    ]
    assert FileProbe().probe(pdf_of(text_pdf(), swiss_sheet().pdf())).pages[0].data == (
        FileProbe().probe(pdf_of(text_pdf(), swiss_sheet().pdf())).pages[0].data
    )  # the same bytes every time: the hash cache and the same-content check rely on it


def test_a_set_with_a_notes_cover_reads_each_drawn_page(make_service: MakeService) -> None:
    ingest = make_service()
    project = ingest.wait(ingest.start("set.pdf", permit_set()))
    by_path = {file.path: file for file in project.files}
    assert list(by_path) == ["set.pdf", "set#p2.pdf", "set#p3.pdf"]
    assert by_path["set.pdf"].state == "text_only"
    cover = by_path["set.pdf"].reason
    assert cover.endswith("; pages 2 and 3 hold drawings, each read as a file of its own")
    for path in ("set#p2.pdf", "set#p3.pdf"):
        page = by_path[path]
        assert (page.kind, page.route, page.state) == ("pdf_vector", "vector", "ready"), page
        assert page.drawing_id is not None
    trace = ingest.trace(project.id, by_path["set#p3.pdf"].id)
    assert trace.stages[0].did == "page 3 of set.pdf, as a PDF of its own"


def test_a_one_page_pdf_is_one_file_as_before(make_service: MakeService) -> None:
    ingest = make_service()
    project = ingest.wait(ingest.start("plan.pdf", swiss_sheet().pdf()))
    assert [(file.path, file.kind, file.route) for file in project.files] == [
        ("plan.pdf", "pdf_vector", "vector")
    ]


def test_pages_past_the_cap_are_named_not_read() -> None:
    plan = swiss_sheet().pdf()
    found = FileProbe().probe(pdf_of(text_pdf(), *[plan] * (MAX_PAGES + 2)))
    assert len(found.pages) == MAX_PAGES
    last, count = MAX_PAGES + 1, MAX_PAGES + 3
    assert found.did.endswith(f"; pages after {last} of {count} were not looked at")


def test_a_page_file_names_the_pdf_it_was_split_from() -> None:
    paths = ["sets/Permit .PDF", "sets/Permit #p3.pdf", "plan.pdf", "notes#p2.pdf"]
    assert page_path("sets/Permit .PDF", 3) == "sets/Permit #p3.pdf"
    assert split_from("sets/Permit #p3.pdf", paths) == "sets/Permit .PDF"
    assert split_from("plan.pdf", paths) is None  # not a page file
    assert split_from("notes#p2.pdf", paths) is None  # named like one, but no notes.pdf

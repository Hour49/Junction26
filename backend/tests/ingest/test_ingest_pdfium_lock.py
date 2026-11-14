"""pdfium is not thread-safe: every place ingest calls it holds `PDFIUM` (app/adapters/
pdfium_lock.py), so the API's page renders on request threads never run beside it."""

import threading
from typing import Any

import pypdfium2
import pytest
from test_vector_pdf import swiss_sheet

from app.adapters.archive import FileProbe
from app.adapters.page_sizes import PageSizes
from app.adapters.pdfium_lock import PDFIUM
from app.adapters.vector_pdf.objects import read_page
from app.core.pipeline.model import DrawingFile

PDF = swiss_sheet().pdf()


def free_elsewhere() -> bool:
    """Whether another thread could take the lock now."""
    taken: list[bool] = []

    def attempt() -> None:
        taken.append(PDFIUM.acquire(blocking=False))
        if taken[0]:
            PDFIUM.release()

    worker = threading.Thread(target=attempt)
    worker.start()
    worker.join()
    return taken[0]


@pytest.fixture
def opened_unlocked(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """One entry per pdfium document opened: True when it was opened without the lock."""
    seen: list[bool] = []
    real = pypdfium2.PdfDocument

    def spy(*args: Any, **kwargs: Any) -> Any:
        seen.append(free_elsewhere())
        return real(*args, **kwargs)

    monkeypatch.setattr(pypdfium2, "PdfDocument", spy)
    return seen


class Files:
    def read(self, path: str) -> bytes:
        return PDF


def test_the_probe_page_sizes_and_the_vector_reader_hold_the_lock(
    opened_unlocked: list[bool],
) -> None:
    FileProbe().probe(PDF)
    PageSizes(Files()).pages(DrawingFile(path="a.pdf", size=len(PDF), sha256="0", kind="pdf"))
    read_page(PDF)
    assert opened_unlocked == [False, False, False]

"""One PDF set as the schedule rules read it (schedule_check.py): each page's plain text, its text
objects and the tables of the pages that hold a schedule. Reading the pages of a 33-page set takes
seconds, so every rule shares one reading. Only text is kept; a page's paths are read only where a
rule asks for its tables.
"""

from dataclasses import dataclass

import pypdfium2

from app.adapters.pdf_tables.lattice import read_tables
from app.adapters.pdf_tables.page import read_table_page
from app.adapters.pdfium_lock import PDFIUM
from app.adapters.vector_pdf.objects import PdfText, read_page
from app.core.drawing.model import Table


@dataclass(frozen=True)
class PageTexts:
    width: float  # points, as rendered
    height: float
    texts: tuple[PdfText, ...]


class PdfSet:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.text = _page_texts(data)  # each page's plain text, in page order
        self._objects: dict[int, PageTexts] = {}
        self._tables: dict[int, list[Table]] = {}

    @property
    def pages(self) -> int:
        return len(self.text)

    def objects(self, index: int) -> PageTexts:
        """The text objects of page `index` (0-based)."""
        if index not in self._objects:
            page = read_page(self.data, index)
            self._objects[index] = PageTexts(page.width, page.height, page.texts)
        return self._objects[index]

    def tables(self, index: int) -> list[Table]:
        """The ruled schedules of page `index` (0-based)."""
        if index not in self._tables:
            self._tables[index] = read_tables(read_table_page(self.data, index))
        return self._tables[index]


def _page_texts(data: bytes) -> list[str]:
    with PDFIUM:  # pdfium is not thread-safe (app/adapters/pdfium_lock.py)
        document = pypdfium2.PdfDocument(data)
        try:
            return [
                document[index].get_textpage().get_text_range() for index in range(len(document))
            ]
        finally:
            document.close()

"""`TABLES=pdf`: the schedules printed on a drawn PDF sheet (door, window, finish, room schedules),
added to what the route's own extractor read.

`PdfTables` wraps an `Extractor`. When the source is a PDF and the sheet is its page 1 (the PDF
itself or its render), it reads page 1's ruling lines and characters (page.py), rebuilds each
ruled schedule's grid and reads title, header and rows from it (lattice.py), and hands them back
as `tables` in page fractions. A page without a schedule keeps `tables` None, so the inner
extractor's result is unchanged.

A PDF that holds a schedule and plans that tag what it lists (doors, window types, rooms) also
gets a note per schedule saying which marks the two disagree on (schedule_check.py, whose
`ScheduleTagCounter` brings the two counts to stage 8).

Only ruled schedules are read (Revit and AutoCAD schedules draw every cell), and only those with
a title row: title blocks, revision lists and drawings made of boxes have none.
"""

from app.adapters.pdf_tables.lattice import read_tables
from app.adapters.pdf_tables.page import read_table_page
from app.adapters.pdf_tables.schedule_check import checks_of, reads_itself
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles, Extractor

SAME_SHAPE = 0.01  # relative difference of width / height between the PDF page and the sheet


class PdfTables:
    def __init__(self, inner: Extractor, files: DrawingFiles) -> None:
        self._inner = inner
        self._files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        if source.kind != "pdf" or not sheet.pages:
            return found
        if reads_itself(source, sheet) and (checked := checks_of(self._files, source)):
            notes = tuple(rule.note() for rule in checked)
            found = found.model_copy(update={"notes": (*found.notes, *notes)})
        page = read_table_page(self._files.read(source.path))
        target = sheet.pages[0]
        if abs((page.width / page.height) / (target.width / target.height) - 1) > SAME_SHAPE:
            return found
        tables = read_tables(page)
        if not tables:
            return found
        names = ", ".join(table.title or table.id for table in tables)
        return found.model_copy(
            update={
                "tables": tuple(tables),
                "notes": (*found.notes, f"pdf tables: {len(tables)} schedules read ({names})"),
            }
        )

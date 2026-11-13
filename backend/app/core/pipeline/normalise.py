"""Stage 6: one frame per sheet, in which every later position is a page fraction.

Hello world: the pages as the file gives them. Fixing a rotated scan comes here later; the plans
on the sheet and its scale are read by the route's extractor in stage 7.
"""

from collections.abc import Sequence

from app.core.drawing.model import Page
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Sheet


def normalise(file: DrawingFile, pages: Sequence[Page]) -> Sheet:
    numbers = [page.page for page in pages]
    if not pages or numbers != list(range(1, len(pages) + 1)):
        raise InvalidInputError(f"{file.path}: pages must be numbered 1..n, got {numbers}")
    return Sheet(file=file, pages=tuple(pages))

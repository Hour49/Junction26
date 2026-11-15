"""`DISCIPLINE_PICTURES=template`: the picture lane in ingest (spec discipline-pictures.md).

`PictureLane` wraps the raster `Extractor`. It returns the inner reading unchanged, so a drawing
model is the same with the lane on or off (AC-14). Beside it, a page that triage names a services
or structural discipline (`Sheet.discipline`, never the sheet kind alone) and does not set aside
is read by the local readers: the legend and printed scale by OCR (`legend.OcrLegend`), its
symbols by `template`, its coloured runs by `mask`. Their readings become a `FactSheet`
(`picture_facts`), kept in `PictureSheets` by the page file's sha256. Each label has one reader,
so every fact is held: Low, never sure (decision 0011). No model is called; cost 0.

`PictureSheets` is also the `FactSource` the answers read it from (composition._facts). A page
the lane cannot read leaves no sheet, and the log says why: ingest never fails on it.
"""

import hashlib
import json
import logging
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath

from pydantic import Field

from app.adapters.discipline_pictures import legend as legend_module
from app.adapters.discipline_pictures import mask as mask_module
from app.adapters.discipline_pictures import template as template_module
from app.adapters.discipline_pictures.legend import OcrLegend
from app.adapters.discipline_pictures.mask import MaskReader
from app.adapters.discipline_pictures.template import TemplateReader
from app.adapters.whole_file import write_whole
from app.core import picture_facts as picture_facts_module
from app.core.discipline import discipline_from_sheet
from app.core.ifc_facts import Discipline, Fact, FactSheet
from app.core.ingest.model import FileStatus
from app.core.ingest.model import Sheet as SheetKind
from app.core.model import Frozen
from app.core.picture_facts import Checked, double_check, picture_facts, storey_of_title
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles, Extractor, PictureReader

log = logging.getLogger(__name__)
ROUTED = frozenset({"plumbing", "heating", "ventilation", "electrical", "fire", "structural"})
# The lane's version: a change to a reader, to the facts or to this lane reads the pages again
CODE = hashlib.sha256(
    b"".join(
        [
            *(
                Path(m.__file__ or "").read_bytes()
                for m in (legend_module, template_module, mask_module, picture_facts_module)
            ),
            Path(__file__).read_bytes(),
        ]
    )
).hexdigest()[:12]
SheetOf = Callable[[str], SheetKind | None]  # triage's sheet-kind reply for a file, by path
# In a fact's `source` after its readers: the discipline was the file name's (no sheet-kind reply)
FROM_FILE_NAME = ":discipline-from-file-name"


class PictureScale(Frozen):
    """The page's scale as the lane read it (the printed ratio at the file's dpi, or a scale
    bar): metres per pixel of page 1 and its size in pixels, so its size in metres is
    `width_px * m_per_px` by `height_px * m_per_px`."""

    width_px: float
    height_px: float
    m_per_px: float


class PictureFactSheet(FactSheet):
    """A picture's fact sheet with the page's scale. Picture-side: `core/ifc_facts.py` is part
    of the IFC sheets' CODE, so a field there would miss every stored IFC sheet. None (no scale
    read) is left out of the JSON, so such a sheet is the FactSheet it was."""

    scale: PictureScale | None = Field(default=None, exclude_if=lambda value: value is None)


def routed(found: SheetKind | None) -> bool:
    """The lane reads a page triage names a services or structural discipline and reads."""
    return found is not None and found.discipline in ROUTED and found.decision != "set_aside"


def kept_in(cache_dir: Path, reader: str) -> Path:
    """Where the lane keeps its sheets for DISCIPLINE_PICTURES=`reader`: `glyphs` and `gemini`
    each in its own folder, so switching readers never serves another reader's sheets."""
    return cache_dir / reader if reader in ("glyphs", "gemini") else cache_dir


class PictureSheets:
    """The lane's fact sheets on disk, `<cache>/<sha256>-<CODE>.json` by the page file's content;
    as a `FactSource`, the sheet of a file by its path."""

    def __init__(self, files: DrawingFiles | None, cache_dir: Path) -> None:
        self._files = files  # None: looked up by content only (`sheet`, `of_drawings`)
        self._dir = cache_dir

    def path(self, sha256: str) -> Path:
        return self._dir / f"{sha256}-{CODE}.json"

    def put(self, sha256: str, sheet: PictureFactSheet) -> None:
        write_whole(self.path(sha256), sheet.model_dump_json())

    def sheet(self, sha256: str) -> PictureFactSheet | None:
        """The sheet kept for a page file by its content, or None."""
        try:
            return PictureFactSheet.model_validate_json(
                self.path(sha256).read_text(encoding="utf-8")
            )
        except (OSError, ValueError, json.JSONDecodeError):  # none kept, or unreadable
            return None

    def facts(self, file: str) -> FactSheet | None:
        if self._files is None or PurePosixPath(file).suffix.lower() == ".ifc":
            return None
        try:
            data = self._files.read(file)
        except OSError:
            return None
        return self.sheet(hashlib.sha256(data).hexdigest())

    def of_drawings(
        self, files: Callable[[], Iterable[FileStatus]]
    ) -> Callable[[str], FactSheet | None]:
        """A drawing's kept sheet by its id, from a project's files, read when asked
        (ServiceFollower.pictures)."""

        def of(drawing_id: str) -> FactSheet | None:
            shas = (f.sha256 for f in files() if f.drawing_id == drawing_id and f.sha256)
            return next((found for sha in shas if (found := self.sheet(sha))), None)

        return of


class PictureLane:
    def __init__(
        self,
        inner: Extractor,
        files: DrawingFiles,
        sheet_of: SheetOf,
        sheets: PictureSheets,
        legend: OcrLegend,
        symbols: PictureReader | None = None,
        check: PictureReader | None = None,
    ) -> None:
        self._inner = inner
        self._sheet_of = sheet_of
        self._sheets = sheets
        self._legend = legend
        # the symbols' reader: `template` unless another is given (DISCIPLINE_PICTURES=glyphs)
        self._template = symbols or TemplateReader(files, legend.legend)
        # a second symbols reader (DISCIPLINE_PICTURES=gemini: template): a label whose count it
        # confirms (`double_check`) is not held; it adds no facts of its own
        self._check = check
        self._mask = MaskReader(files, legend.legend, legend.scale)

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        kind = self._sheet_of(sheet.file.path)
        # No sheet-kind reply (triage off, no keys): the service the file name names by a sheet code
        # or a strong word ("H-101 heating.png"), as for a services plan; a weak word ("pipe") names
        # none, and None leaves the file as it was. A reply, even with no discipline, wins.
        stem = PurePosixPath(sheet.file.path).stem
        named = discipline_from_sheet("mep_plan", stem, None) if kind is None else None
        if sheet.pages and (routed(kind) or named in ROUTED):
            try:
                self._read(source, sheet, kind, named)
            except Exception:  # the lane never fails ingest; the log has the trace
                log.exception("discipline pictures: %s not read", sheet.file.path)
        return found

    def _read(
        self, source: DrawingFile, sheet: Sheet, kind: SheetKind | None, named: Discipline | None
    ) -> None:
        storey = storey_of_title(kind.title if kind else None)
        # shortcut: a photo the rectifier could not flatten is matched as is; skip template there
        # once ingest says which photos it flattened
        readings = tuple(
            reading.model_copy(update={"storey": storey})
            for reading in (self._template.read(source, sheet), self._mask.read(source, sheet))
        )
        checked = Checked(readings=readings, agreed={}, disputed=())
        if self._check is not None:
            second = double_check(readings[0], self._check.read(source, sheet))
            checked = checked.model_copy(
                update={"agreed": second.agreed, "disputed": second.disputed}
            )
        # the page's own discipline (triage's, else the file name's) for labels that name none
        facts = picture_facts(sheet.file.sha256[:16], checked, kind.discipline if kind else named)
        if not facts.facts:
            notes = [note for reading in readings for note in reading.notes]
            said = "; ".join(notes)
            log.info("discipline pictures: no facts on %s (%s)", sheet.file.path, said)
            return
        if (
            named is not None
        ):  # said in each fact's source, after its readers, so a reason can quote it
            facts = facts.model_copy(update={"facts": [_named(f) for f in facts.facts]})
        kept = PictureFactSheet(**dict(facts), scale=self._scale(source, sheet))
        self._sheets.put(sheet.file.sha256, kept)

    def _scale(self, source: DrawingFile, sheet: Sheet) -> PictureScale | None:
        """Page 1's scale from the same OCR pass the readers used; None without one, or when
        the page is not measured in pixels."""
        page, m = sheet.pages[0], self._legend.scale(source, sheet).m_per_unit
        if m is None or page.unit != "px":
            return None
        return PictureScale(width_px=page.width, height_px=page.height, m_per_px=m)


def _named(fact: Fact) -> Fact:
    """`picture:<readers>[:...]` -> `picture:<readers>:discipline-from-file-name[:...]`: the route
    (before the first colon) and a held fact's ending stay where the levels read them."""
    route, _, rest = fact.source.partition(":")
    readers, colon, tail = rest.partition(":")
    return fact.model_copy(update={"source": f"{route}:{readers}{FROM_FILE_NAME}{colon}{tail}"})

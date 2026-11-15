"""Composition root: the one place that picks an adapter for each port, from the settings.

Entry points (app/cli.py now, API routes later) build a `Pipeline` here and call its two use
cases; they never import an adapter of a pipeline port themselves. Plugging in a new extractor,
second counter or parser: write the adapter, add its name to the Literal in app/settings.py and a
case below (docs/decisions/0005-pipeline-core.md).
"""

import logging
import secrets
import time
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache, partial
from pathlib import Path
from typing import cast

from app.adapters.answer_policy import load_policy
from app.adapters.answer_prior import DEV_PRIOR, NoPrior, TablePrior
from app.adapters.archive import (
    DiskProjectStore,
    ExifFrame,
    FileProbe,
    InlineRunner,
    NoRectifier,
    ThreadRunner,
    ZipUnpacker,
)
from app.adapters.archive.probe import is_scanned_pdf
from app.adapters.carbon import (
    CarbonChecked,
    CarbonClient,
    CarbonExtractor,
    CarbonReader,
    CarbonSwitch,
    CarbonThings,
)
from app.adapters.carbon.contract import READER_SHA, SOURCE
from app.adapters.chat_rules import RulesChatModel
from app.adapters.check_policy import load_check
from app.adapters.count_arbiter import ArbiterCountExtractor
from app.adapters.dataset_files import DatasetFiles, DatasetSheetModels
from app.adapters.decisions.client import DecisionsClient
from app.adapters.decisions.g1main import G1MainReader
from app.adapters.decisions.uses import DecisionsConfidence, DecisionsCountExtractor
from app.adapters.decisions_kind import KindReader
from app.adapters.decisions_kind.probe import KindProbe
from app.adapters.discipline_pictures.gemini import GeminiPictureReader
from app.adapters.discipline_pictures.glyphs import GlyphReader
from app.adapters.discipline_pictures.lane import CODE as PICTURES_CODE
from app.adapters.discipline_pictures.lane import PictureLane, PictureSheets, kept_in
from app.adapters.discipline_pictures.legend import OcrLegend
from app.adapters.discipline_pictures.runs_graph import GraphReader
from app.adapters.discipline_pictures.template import TemplateReader
from app.adapters.evidence.embedder import load_embedder
from app.adapters.evidence.pictures import SheetKindPictures
from app.adapters.evidence.project import CreditOf, ProjectEvidence
from app.adapters.evidence.store import SqliteEvidenceIndex
from app.adapters.evidence.texts import FileTextReader, StoredTexts
from app.adapters.gate_policy import load_gate
from app.adapters.hello import (
    HelloExtractor,
    HelloParser,
    HelloSecondCounter,
    HelloSourceFinder,
)
from app.adapters.ifc_model import IfcModelExtractor, IfcModels, IfcSecondCounter
from app.adapters.ifc_model.facts_source import IfcFactSource
from app.adapters.ifc_model.facts_store import StoredFacts
from app.adapters.ifc_model.glb import GlbModels
from app.adapters.llm_chat import OpenAiChatModel
from app.adapters.local_gate import load_local_gate
from app.adapters.one_at_a_time import OneAtATime
from app.adapters.openvlm.client import OpenVlmClient
from app.adapters.openvlm.decider import OpenVlmDecider
from app.adapters.openvlm.rooms import OpenVlmRoomExtractor, OpenVlmRoomModel
from app.adapters.page_sizes import PageSizes
from app.adapters.paths import inside
from app.adapters.pdf_tables import PdfTables
from app.adapters.pdf_tables.schedule_check import ScheduleTagCounter
from app.adapters.printed_scale import PrintedScale
from app.adapters.printed_scale.carbon import CarbonPrinted
from app.adapters.question_templates import TemplateParser
from app.adapters.raster import RoomPolicy, assemble, parse_components, parse_readers
from app.adapters.raster.photo import PHOTO, PhotoSwitch
from app.adapters.raster.precomputed import PrecomputedExtractor, WholePagePlan
from app.adapters.raster.room_words import room_word, swiss_label_rooms
from app.adapters.raster_detector import OnnxDetector
from app.adapters.raster_ocr.engine import RapidOcrEngine
from app.adapters.raster_ocr.gemini import GeminiClient, GeminiRoomExtractor, GeminiRoomReader
from app.adapters.raster_ocr.region_rooms import RegionRooms, SegmenterRegion
from app.adapters.raster_ocr.tiles import PrintedOcr
from app.adapters.raster_region import RegionDetector, load_region
from app.adapters.raster_remote import HttpReaderClient, RemoteReader
from app.adapters.raster_scale import PriorScale
from app.adapters.raster_scale.carbon_doors import CarbonDoorScale
from app.adapters.raster_scale.label import LabelScale
from app.adapters.rectifier import R3Rectifier
from app.adapters.rectifier.uvdoc import OnnxUvdoc
from app.adapters.resolver.carbon import CarbonClient as ResolverClient
from app.adapters.resolver.carbon import CarbonResolver
from app.adapters.scan_images import ScanImages, ScanRenders
from app.adapters.triage.gemini_describer import (
    CARBON_MIN_TIMEOUT_S,
    DESCRIBERS,
    GeminiDescribeClient,
    GeminiDescriber,
)
from app.adapters.triage.rules import RulesClassifier
from app.adapters.triage.rules_judge import RulesJudge
from app.adapters.triage.sheet_kind import (
    ADVANCED_LONG_SIDE,
    CONTRACTS,
    GeminiSheetKindClient,
    SheetKindClassifier,
    SheetKindReader,
    long_side,
)
from app.adapters.triage.siglip import SiglipClassifier
from app.adapters.vector_pdf import PdfSecondCounter, PdfVectorExtractor
from app.adapters.vector_pdf.unruled import Unruled
from app.core.agent.model import Caps
from app.core.agent.ports import ChatModel
from app.core.answering.answer import answer_questions
from app.core.answering.facts import FactSource, FirstSheet
from app.core.answering.model import Question
from app.core.answering.ports import (
    AnswerConfidence,
    AnswerPrior,
    AnswerSink,
    Clock,
    DrawingSource,
    QuestionParser,
)
from app.core.drawing.model import Room
from app.core.errors import DomainError, InvalidInputError
from app.core.evidence.chunks import passages
from app.core.evidence.pictures import EvidenceSteps
from app.core.ingest.judge import reading_flags
from app.core.ingest.model import CarbonRead, ContentKind, ProjectStatus
from app.core.ingest.model import Sheet as SheetKind
from app.core.ingest.ports import Classifier, ContentProbe, Describer, Rectifier
from app.core.ingest.service import IngestService
from app.core.ingest.triage import TriageSteps
from app.core.pipeline.ingest import ingest
from app.core.pipeline.model import IngestReport, Route
from app.core.pipeline.ports import (
    DrawingFiles,
    DrawingSink,
    Extractor,
    PageReader,
    SecondCounter,
    SourceFinder,
)
from app.core.pipeline.room_policy import generic_word_rooms, gold_label_rooms
from app.core.pipeline.route import RICHEST_FIRST
from app.core.review.check import (
    NO_SCORERS,
    CheckPolicy,
    Disputes,
    RoomWords,
    Scorer,
    gate_scorer,
    no_disputes,
    no_room_words,
)
from app.core.review.disputes import find_disputes
from app.core.review.ports import Resolver
from app.core.spend import SpendGuard
from app.settings import (
    AnswerPriorName,
    ExtractorName,
    QuestionParserName,
    RectifierName,
    RoomPolicyName,
    SecondCounterName,
    Settings,
    TablesName,
)

# The experiment arms' extraction_v1 files: data/stoa/exp/<track>/<arm>/ (RASTER_COMPONENTS exp:).
logger = logging.getLogger(__name__)
EXP_DIR = Path(__file__).resolve().parents[2] / "data" / "stoa" / "exp"
# core's exported detectors: data/models/detector/<arm>/ (RASTER_COMPONENTS detector:<arm>).
DETECTOR_DIR = Path(__file__).resolve().parents[2] / "data" / "models" / "detector"
# photo:<arm>: a detector trained on phone photos (photo track), data/models/photo/<arm>/
PHOTO_DIR = Path(__file__).resolve().parents[2] / "data" / "models" / "photo"
UVDOC_MODEL = Path(__file__).resolve().parents[2] / "data" / "models" / "photo" / "uvdoc.onnx"
# core's tune runs (counts.py tune): detector:<arm>:<run> reads <run>.thresholds.json from here.
DETECTOR_RUNS = EXP_DIR / "detector" / "raw"


@dataclass(frozen=True)
class Pipeline:
    """The use cases with their adapters wired in."""

    files: DrawingFiles
    finder: SourceFinder
    pages: PageReader
    extractors: Mapping[Route, Extractor]
    second_counter: SecondCounter
    parser: QuestionParser
    prior: AnswerPrior
    clock: Clock
    prior_families: frozenset[tuple[str, str]] = frozenset()  # ANSWER_POLICY
    # The routes whose extractor reads something: a route on "hello" never takes a drawing from
    # one that has a reader (stage 5)
    readable: frozenset[Route] = frozenset(RICHEST_FIRST)
    # Whether a PDF is a scan, which stage 5 routes to the raster reader; None: none is
    scanned: Callable[[bytes], bool] | None = None
    # Gemini Decisions' probability for each drawing answer (DECISIONS_CONFIDENCE); None: off
    confidence: AnswerConfidence | None = None
    # GATE_POLICY: family -> the confidence at or above which an answer is sure; None: ungated
    sure_at: Mapping[str, float] | None = None
    # What Carbon read of the raster route's drawing of a file (by path): "elements" when
    # CARBON_READER sent it there (the same yes/no its switch uses, or CarbonThings' record of the
    # pages it sent for few things found, so asked after reading), "part" when a composite takes
    # a part from the `carbon` source; ingest flags those drawings. None: no file is
    carbon_read: Callable[[str], CarbonRead | None] | None = None
    # VECTOR_FALLBACK=raster: whether a drawn PDF has no sheet style the vector reader has rules
    # for; when the vector route reads nothing of it, ingest reads it again on the raster route
    # (pipeline/ingest.py `fallback`) and flags it. None: off
    unruled: Callable[[bytes], bool] | None = None
    # How ingest read a file's page, by path (judge.reading_flags: a scan, a photo, Carbon): no
    # answer on a flagged page is sure, on this path as in the product's ask. None: none is
    flags: Callable[[str], tuple[str, ...]] | None = None
    facts: FactSource | None = None  # IFC_FACTS: an IFC model's fact sheet; None: off
    # The drawn PDFs `ingest` read as an image (VECTOR_FALLBACK), by path; `flags` reads it, so a
    # PDF the vector route read keeps its answers' level here as in the product (review-348 S1)
    read_as_image: set[str] = field(default_factory=set[str])

    def ingest(self, paths: Iterable[str], sink: DrawingSink) -> IngestReport:
        report = ingest(
            paths,
            files=self.files,
            finder=self.finder,
            pages=self.pages,
            extractors=self.extractors,
            second_counter=self.second_counter,
            sink=sink,
            readable=self.readable,
            scanned=self.scanned,
            fallback=None if self.unruled is None else self._unruled_file,
        )
        if self.unruled is not None:
            self.read_as_image.update(
                sheet.file for sheet in report.sheets if self._fell_back(sheet.route, sheet.source)
            )
        return report

    def _unruled_file(self, path: str) -> bool:
        """VECTOR_FALLBACK on a file the vector route read nothing of. Every file the CLI reads is
        its own page 1: it splits no PDF into pages (the service's later pages, which do not fall
        back, are files ingest split off: groups._fallback)."""
        return self.unruled is not None and self.unruled(self.files.read(path))

    def _fell_back(self, route: str, source: str) -> bool:
        """A PDF source read on the raster route that is not a scan was read by the fallback."""
        if route != "raster":
            return False
        data = self.files.read(source)
        return data.startswith(b"%PDF") and not (self.scanned is not None and self.scanned(data))

    def answer_questions(
        self, questions: Iterable[Question], drawings: DrawingSource, sink: AnswerSink
    ) -> dict[str, int]:
        return answer_questions(
            questions,
            drawings=drawings,
            parser=self.parser,
            clock=self.clock,
            sink=sink,
            prior=self.prior,
            prior_families=self.prior_families,
            confidence=self.confidence,
            sure_at=self.sure_at,
            flags=self.flags,
            facts=self.facts,
        )


def build_pipeline(
    settings: Settings,
    dataset: Path,
    kinds: Callable[[str], str | None] | None = None,
    advanced: Callable[[str], bool] | None = None,
    sheets: Callable[[str], SheetKind | None] | None = None,
    rectified: Callable[[str], bool] | None = None,
) -> Pipeline:
    """`dataset` is the folder that the drawings' paths (`data/<source>/<name>`) are relative to.
    `kinds` gives the content kind ingest identified a file as, by its path; None: the content
    probe is asked (the CLI reads the dataset's files as they are). `advanced`: whether the
    sheet-kind step called a file advanced, by its path (CARBON_READER=advanced); None: none
    was. `sheets`: the sheet-kind step's reply for a file, by its path (DISCIPLINE_PICTURES
    routes on its discipline); None: no file has one (the CLI). `rectified`: whether the rectifier
    straightened a file (LABEL_SCALE); None: none was (the CLI keeps no frame)."""
    files = DatasetFiles(dataset)
    unruled = _unruled(settings)
    as_image = _as_image(unruled)  # the PDFs the raster route reads: scans, and unruled ones
    scans = ScanImages(files, ScanRenders(as_image))  # the raster side: such a PDF as its page
    kind_of = kinds or _probed_kinds(settings, files)
    use_carbon = _carbon_read(settings, advanced, scans)
    took: set[str] = set()  # CARBON_READER=large: the files read by Carbon for few things found
    models = IfcModels(files)
    # A sheet is paired with its building model only when the model route can read it.
    with_models = settings.extractor_bim == "ifc"
    # One Decisions reader for the count swap and the confidence, made only when one is used.
    decisions = cache(lambda: decisions_reader(settings))
    carbon_read = _carbon_counted(settings, _or_took(use_carbon, took), kind_of)
    images: set[str] = set()  # the drawn PDFs ingest read as an image (Pipeline.read_as_image)
    return Pipeline(
        files=files,
        finder=DatasetSheetModels(dataset) if with_models else HelloSourceFinder(),
        pages=PageSizes(files),
        extractors={
            "bim": _extractor(settings.extractor_bim, files, models),
            "cad": _extractor(settings.extractor_cad, files, models),
            "vector": _tables(
                settings.tables, _extractor(settings.extractor_vector, files, models), files
            ),
            # A precomputed arm finds an uploaded sheet in the Stoa dataset by its content. A PDF
            # whose page 1 is not a vector plan is read here, so its schedules are read (and its
            # schedule checks noted) as on the vector route.
            "raster": _pictures(
                settings,
                _tables(
                    settings.tables,
                    _labelled(
                        settings,
                        _printed(
                            settings,
                            _raster(settings, scans, decisions, kind_of, use_carbon, took),
                            scans,
                            kind_of,
                        ),
                        kind_of,
                        rectified or (lambda path: False),
                    ),
                    files,
                ),
                scans,
                sheets,
            ),
        },
        second_counter=_checked(
            settings.tables, _second_counter(settings.second_counter, files, models), files
        ),
        parser=_parser(settings.question_parser),
        prior=_prior(settings.answer_prior),
        clock=time.perf_counter,
        prior_families=_policy(settings.answer_policy),
        readable=_readable(settings),
        scanned=is_scanned_pdf,
        confidence=DecisionsConfidence(scans, decisions())
        if settings.decisions_confidence
        else None,
        sure_at=_gate(settings),
        carbon_read=carbon_read,
        unruled=unruled,
        flags=partial(_page_flags, kind_of=kind_of, carbon_read=carbon_read, images=images),
        read_as_image=images,
        facts=_facts(settings, files),
    )


def _facts(settings: Settings, files: DrawingFiles) -> FactSource | None:
    """The fact sources in order, first sheet wins; a new one (a picture read) is one more entry."""
    sources: list[FactSource] = []
    if settings.ifc_facts:
        cache = Path(settings.ifc_facts_cache) if settings.ifc_facts_cache else None
        sources.append(IfcFactSource(files, cache))
    if settings.discipline_pictures != "off":
        sources.append(PictureSheets(files, _pictures_cache(settings)))
    return FirstSheet(sources) if sources else None


def _pictures(
    settings: Settings,
    inner: Extractor,
    files: DrawingFiles,
    sheets: Callable[[str], SheetKind | None] | None,
) -> Extractor:
    """DISCIPLINE_PICTURES: the picture lane beside the raster reader (lane.py); off: `inner`."""
    if settings.discipline_pictures == "off":
        return inner
    legend = OcrLegend(files, _ocr())
    symbols = check = None
    if settings.discipline_pictures == "glyphs":
        symbols = GlyphReader(files, legend.legend, settings.discipline_glyphs_model)
    elif settings.discipline_pictures == "gemini":
        key = settings.gemini_api_key.get_secret_value()
        client = CarbonClient(
            key,
            settings.carbon_timeout_s,
            budget=spend_guard(settings),
            in_flight=settings.carbon_calls_in_flight,
        )
        replies = kept_in(settings.discipline_pictures_cache_dir, "gemini") / "replies"
        symbols = GeminiPictureReader(files, client, replies)
        check = TemplateReader(files, legend.legend)  # its agreement unholds a label (pic-det)
    runs = None
    if settings.discipline_runs == "graph":
        runs = GraphReader(files, legend.legend, legend.scale)
    return PictureLane(
        inner,
        files,
        sheets or (lambda _path: None),
        PictureSheets(files, _pictures_cache(settings)),
        legend,
        symbols,
        runs=runs,
        check=check,
    )


def _pictures_cache(settings: Settings) -> Path:
    kept = kept_in(settings.discipline_pictures_cache_dir, settings.discipline_pictures)
    # another runs reader keeps its own sheets: switching never serves the other one's
    return kept if settings.discipline_runs == "mask" else kept / f"runs-{settings.discipline_runs}"


@cache
def _ocr() -> RapidOcrEngine:
    """One OCR engine per process: loading its models takes a second (raster_ocr/engine.py)."""
    return RapidOcrEngine()


def _stored_sheets(store: DiskProjectStore, project_id: str) -> Callable[[str], SheetKind | None]:
    """The sheet-kind step's reply for a project's file (`triage.sheet`, saved before the
    readers run); None for a file it did not classify."""

    def sheet(path: str) -> SheetKind | None:
        status, _ = store.load_project(project_id)
        file = next((file for file in status.files if file.path == path), None)
        return None if file is None or file.triage is None else file.triage.sheet

    return sheet


def _unruled(settings: Settings) -> Callable[[bytes], bool] | None:
    return Unruled() if settings.vector_fallback == "raster" else None


def _as_image(unruled: Callable[[bytes], bool] | None) -> Callable[[bytes], bool]:
    """Whether the raster route reads a PDF as the image of its page: a scan, and with
    VECTOR_FALLBACK=raster a drawn PDF the vector reader has no rules for."""
    if unruled is None:
        return is_scanned_pdf
    return lambda data: is_scanned_pdf(data) or unruled(data)


def _or_took(
    use_carbon: Callable[[str], bool] | None, took: set[str]
) -> Callable[[str], bool] | None:
    """Whether Carbon counted a file's things: `use_carbon` said so, or CarbonThings sent it there
    after the shipped reader found few (asked after the file is read, as ingest does)."""
    if use_carbon is None:
        return None
    return lambda path: use_carbon(path) or path in took


def _page_flags(
    path: str,
    kind_of: Callable[[str], str | None],
    carbon_read: Callable[[str], CarbonRead | None] | None,
    images: Collection[str],
) -> tuple[str, ...]:
    """The reading flags ingest stores for a file's page (judge.reading_flags), for the CLI's
    answers (review-283 M1: without them a scanned or Carbon-read page could come back sure). A
    photo's flag is worded as if not rectified (the CLI keeps no frame); only whether there is a
    flag is used here. Carbon's flag is given whatever the route: a page another route read has no
    Decisions probability, so it is not sure either way. VECTOR_FALLBACK's only on a drawn PDF
    `images` says ingest read as an image (Pipeline.read_as_image), not on one the vector route
    read (review-348 S1)."""
    kind = kind_of(path)
    carbon = None if carbon_read is None else carbon_read(path)
    as_image = kind == "pdf_vector" and path in images
    return reading_flags(cast(ContentKind, kind), None, carbon, as_image)


def _carbon_counted(
    settings: Settings,
    use_carbon: Callable[[str], bool] | None,
    kind_of: Callable[[str], str | None],
) -> Callable[[str], CarbonRead | None] | None:
    """What Carbon read of a file's raster drawing, by path: its elements when CARBON_READER sent
    it there ("elements"), a part when the composite that reads it takes one (elements, a class,
    rooms, plans or scale) from the `carbon` source ("part"; the elements are then not known to
    be all Carbon's), else None. Ingest flags those drawings, so no answer on them is certified
    (a Carbon answer is never sure, brief r8 AS). A double-check reader counts nothing and is not
    a part. None: no file is."""
    if settings.extractor_raster != "composite":
        return None if use_carbon is None else _elements_if(use_carbon)
    main = _carbon_part(settings.raster_components)
    photo = settings.raster_photo_components
    on_photos = _carbon_part(photo) if photo else main
    if use_carbon is None and not main and not on_photos:
        return None

    def counted(path: str) -> CarbonRead | None:
        if use_carbon is not None and use_carbon(path):
            return "elements"
        part = main if main == on_photos else on_photos if kind_of(path) == PHOTO else main
        return "part" if part else None

    return counted


def _elements_if(use_carbon: Callable[[str], bool]) -> Callable[[str], CarbonRead | None]:
    return lambda path: "elements" if use_carbon(path) else None


def _carbon_part(spec: str) -> bool:
    """Whether a RASTER_COMPONENTS-style spec takes a part from the `carbon` source."""
    sources = (part.partition("=")[2].strip() for part in spec.split(","))
    return any(source.partition(":")[0] == "carbon" for source in sources)


# CARBON_READER=large: on a raster image longer than this on its long side Carbon counts the things
# drawn (the sheet-kind step's size rule, #251); below it the shipped reader stays (CubiCasa pages)
LARGE_PX = ADVANCED_LONG_SIDE
# ... and on a smaller raster page where the shipped reader found fewer elements than this (a scan
# or photo the detector cannot read; confidence, carbon-reader.md 5.8-5.9: K = 3 moves no CubiCasa
# page of val or golden dev, K = 10 would)
FEW_THINGS = 3


def _carbon_read(
    settings: Settings, advanced: Callable[[str], bool] | None, files: DrawingFiles
) -> Callable[[str], bool] | None:
    """CARBON_READER's choice of the files Carbon reads alone, by path: all of them, the ones the
    sheet-kind step called advanced (a file without that record: not), the images longer than
    LARGE_PX (their PNG or JPEG header's size; a PDF or another format: not; CarbonThings also
    sends a page where the shipped reader found few things), or none (None)."""
    match settings.carbon_reader:
        case "off":
            return None
        case "all":
            return lambda _: True
        case "advanced":
            return advanced or (lambda _: False)
        case "large":
            return cache(lambda path: (long_side(files.read(path)) or 0) > LARGE_PX)


def _stored_advanced(store: DiskProjectStore, project_id: str) -> Callable[[str], bool]:
    """Whether the sheet-kind step called a project's file advanced (`triage.sheet.advanced`,
    saved with the kind before the readers run). A file it did not classify is not."""

    def advanced(path: str) -> bool:
        status, _ = store.load_project(project_id)
        file = next((file for file in status.files if file.path == path), None)
        sheet = None if file is None or file.triage is None else file.triage.sheet
        return sheet is not None and sheet.advanced

    return advanced


def _probed_kinds(settings: Settings, files: DrawingFiles) -> Callable[[str], str | None]:
    """A file's content kind from ingest's probe, made only when asked."""
    probe = cache(lambda: _probe(settings))
    return lambda path: probe().probe(files.read(path)).kind


def _stored_kinds(store: DiskProjectStore, project_id: str) -> Callable[[str], str | None]:
    """The content kind ingest recorded for a project's file (saved before the readers run): the
    file the readers see may be the rectified page, which no longer looks like a photo."""

    def kind_of(path: str) -> str | None:
        status, _ = store.load_project(project_id)
        return next((file.kind for file in status.files if file.path == path), None)

    return kind_of


def _stored_rectified(store: DiskProjectStore, project_id: str) -> Callable[[str], bool]:
    """Whether the rectifier straightened a project's file (its frame, saved before the readers
    run)."""

    def rectified(path: str) -> bool:
        status, _ = store.load_project(project_id)
        file = next((file for file in status.files if file.path == path), None)
        return file is not None and file.normalised is not None and file.normalised.rectified

    return rectified


def _probe(settings: Settings) -> ContentProbe:
    """Ingest's content probe; with DECISIONS_KIND, the Gemini sheet-kind signal on top."""
    if not settings.decisions_kind:
        return FileProbe()
    client = (
        OpenVlmDecider(_eu(settings))
        if settings.kind_provider == "eu"
        else DecisionsClient(
            settings.gemini_api_key.get_secret_value(),
            settings.decisions_timeout_s,
            budget=spend_guard(settings),
        )
    )
    return KindProbe(FileProbe(), KindReader(client, settings.decisions_cache_dir))


def _triage(settings: Settings) -> TriageSteps | None:
    """File triage (decision 0010); None when both the classifier and the sheet-kind step are
    off, whatever else is set. SHEET_KIND wraps the classifier (or stands alone)."""
    inner: Classifier | None = None
    match settings.triage_classifier:
        case "off":
            pass
        case "rules":
            inner = RulesClassifier()
        case "siglip":
            try:
                inner = SiglipClassifier.from_folder()
            except DomainError as error:
                raise InvalidInputError(f"TRIAGE_CLASSIFIER=siglip: {error}") from error
    name = f"classifier={settings.triage_classifier}, "
    if settings.sheet_kind == "carbon":
        reader = _sheet_kind_reader(settings)
        classifier: Classifier = SheetKindClassifier(
            inner, reader, settings.sheet_kind_cut, settings.sheet_kind_set_aside
        )
        name += f"sheet_kind={settings.sheet_kind}, "  # named only when on: the same keys as before
    elif inner is None:
        return None
    else:
        classifier = inner
    name += f"describer={settings.triage_describer}, judge={settings.triage_judge}"
    judge = RulesJudge() if settings.triage_judge == "rules" else None
    describer = _describer(settings)
    return TriageSteps(classifier=classifier, describer=describer, judge=judge, name=name)


def _sheet_kind_reader(settings: Settings) -> SheetKindReader:
    """The sheet-kind model of SHEET_KIND and of the evidence step: one cache, one guard."""
    contract = CONTRACTS[settings.sheet_discipline]
    client = GeminiSheetKindClient(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_timeout_s,
        budget=spend_guard(settings),
        contract=contract,
    )
    return SheetKindReader(client, settings.sheet_kind_cache_dir, contract)


def _describer(settings: Settings) -> Describer | None:
    """TRIAGE_DESCRIBER, for triage and for the evidence step; None: off."""
    if settings.triage_describer == "off":
        return None
    model, thinking, usd_per_m = DESCRIBERS[settings.triage_describer]
    if settings.triage_describer == "carbon" and settings.gemini_timeout_s < CARBON_MIN_TIMEOUT_S:
        raise InvalidInputError(
            f"TRIAGE_DESCRIBER=carbon needs GEMINI_TIMEOUT_S of {CARBON_MIN_TIMEOUT_S:.0f} s "
            f"or more: its replies take up to that long (it is {settings.gemini_timeout_s:g})"
        )
    client = GeminiDescribeClient(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_timeout_s,
        model=model,
        thinking=thinking,
        budget=spend_guard(settings),
        usd_per_m=usd_per_m,
    )
    return GeminiDescriber(client, settings.triage_describer_cache_dir)


def _evidence_steps(settings: Settings) -> EvidenceSteps | None:
    """EVIDENCE_SCOPE (decision 0012 sources v2): all_non_plan asks every picture triage did not
    set aside its kind and describes the ones that are not floor plan sheets; set_aside: None."""
    if settings.evidence_scope == "set_aside":
        return None
    kinds = SheetKindPictures(_sheet_kind_reader(settings), settings.sheet_kind_cut)
    return EvidenceSteps(kinds=kinds, describer=_describer(settings), texts=FileTextReader())


def _rectifier(name: RectifierName) -> Rectifier:
    match name:
        case "none":
            return NoRectifier()
        case "r3":
            try:
                return R3Rectifier(OnnxUvdoc(UVDOC_MODEL))
            except DomainError as error:
                raise InvalidInputError(f"RECTIFIER=r3: {error}") from error


def _readable(settings: Settings) -> frozenset[Route]:
    """The routes whose extractor is not the hello-world one."""
    names: dict[Route, str] = {
        "bim": settings.extractor_bim,
        "cad": settings.extractor_cad,
        "vector": settings.extractor_vector,
        "raster": settings.extractor_raster,
    }
    return frozenset(found for found, name in names.items() if name != "hello")


@dataclass(frozen=True)
class Answering:
    """What the API answers a question with: the parser and prior the settings name."""

    parser: QuestionParser
    prior: AnswerPrior
    clock: Clock
    prior_families: frozenset[tuple[str, str]]  # ANSWER_POLICY, as the pipeline has it
    # DECISIONS_CONFIDENCE: the answer confidence over the files a drawing was read from; None: off
    confidence: Callable[[DrawingFiles], AnswerConfidence] | None = None
    signal: str | None = None  # what that confidence's score is, by name (`g1main`)
    sure_at: Mapping[str, float] | None = None  # GATE_POLICY on that signal; None: ungated
    check: CheckPolicy | None = None  # CHECK_POLICY; None: off, no answer asks for a check
    disputes: Disputes = no_disputes  # where a double-check request points
    scorers: Mapping[str, Scorer] = NO_SCORERS  # LOCAL_GATES, by signal name (lower case)
    resolver: Resolver | None = None  # RESOLVER; None: off
    carbon_ladder: bool = False  # CARBON_LEVELS=ladder: a Medium answer Carbon reads alike is High
    room_words: RoomWords = no_room_words  # what a room's printed label names (room_word_doubt)
    # IFC_FACTS: the files' stored fact sheets by sha256, built apart when ingest is done with a
    # model or on a miss, never parsed here (adapters/ifc_model/facts_store.py). None: off
    facts: StoredFacts | None = None


def build_answering(settings: Settings) -> Answering:
    confidence: Callable[[DrawingFiles], AnswerConfidence] | None = None
    signal: str | None = None
    if settings.decisions_confidence:
        reader = decisions_reader(settings)  # one reader: its disk cache is the count swap's too
        # one cache for every answer: each answer on a scan re-rendered its page (review-280 S2);
        # it renders what ingest's raster readers read as images (scans, and unruled PDFs)
        renders = ScanRenders(_as_image(_unruled(settings)))
        confidence = partial(_scan_confidence, reader=reader, renders=renders)
        signal = DECISIONS_SIGNAL
    # LOCAL_GATES only serve CHECK_POLICY: with it off, a bad path can't stop startup
    scorers = _scorers(settings.local_gates) if settings.check_policy else {}
    return Answering(
        parser=_parser(settings.question_parser),
        prior=_prior(settings.answer_prior),
        clock=time.perf_counter,
        prior_families=_policy(settings.answer_policy),
        confidence=confidence,
        signal=signal,
        sure_at=_gate(settings),
        check=(
            load_check(Path(settings.check_policy), signal, scorers)
            if settings.check_policy
            else None
        ),
        disputes=find_disputes,
        scorers=scorers,
        resolver=_resolver(settings),
        carbon_ladder=settings.carbon_levels == "ladder",
        room_words=room_word,
        facts=_chat_facts(settings),
    )


def _chat_facts(settings: Settings) -> StoredFacts | None:
    if not settings.ifc_facts:
        return None
    if settings.ifc_facts_cache:
        return StoredFacts(Path(settings.ifc_facts_cache))
    return StoredFacts(settings.projects_dir.parent / "cache" / "facts")


def _scan_confidence(
    files: DrawingFiles, reader: G1MainReader, renders: ScanRenders
) -> AnswerConfidence:
    """The answer confidence over a raster drawing's file as ingest's readers read it: a scanned
    PDF (or an unruled one, VECTOR_FALLBACK) as the image of its page (scan_images.py), so Gemini
    is asked about the same image. The page is rendered once in `renders`, shared by every
    answer."""
    return DecisionsConfidence(ScanImages(files, renders), reader)


def _resolver(settings: Settings) -> Resolver | None:
    match settings.resolver:
        case "off":
            return None
        case "carbon":
            client = ResolverClient(
                settings.gemini_api_key.get_secret_value(),
                settings.resolver_timeout_s,
                settings.resolver_model,
                budget=spend_guard(settings),
            )
            return CarbonResolver(client, settings.resolver_cache_dir)


def readers(settings: Settings) -> dict[str, str]:
    """The adapter each port uses, by port, as the API reports it."""
    return {
        "bim": settings.extractor_bim,
        "cad": settings.extractor_cad,
        "vector": settings.extractor_vector,
        "raster": settings.extractor_raster,
        "tables": settings.tables,
        "second_counter": settings.second_counter,
        "rectifier": settings.rectifier,
        "question_parser": settings.question_parser,
        "answer_prior": settings.answer_prior,
        "decisions_kind": str(settings.decisions_kind),  # as ingest records it
    }


# The answer confidence's score: Gemini Decisions' probability for the answered count (G1main's
# choice distribution), raw: not calibrated against right answers
DECISIONS_SIGNAL = "g1main"
# Raster sources that call a service with a key (Gemini or our EU model server, the Verda
# detector), in RASTER_COMPONENTS, RASTER_PHOTO_COMPONENTS and DOUBLE_CHECK_READERS
KEYED_SOURCES = frozenset(
    {"gemini", "regionrooms", "verda", "decisions", "decisions-s1536", "carbon"}
)


def uses_keys(settings: Settings) -> bool:
    """Whether a reader, the answer confidence or file triage calls a service that needs an API
    key."""
    specs = (
        settings.raster_components,
        settings.raster_photo_components,
        settings.double_check_readers,
    )
    sources = [part.partition("=")[2] for spec in specs for part in spec.split(",") if part]
    keyed = any(source.split(":", 1)[0] in KEYED_SOURCES for source in sources)
    carbon = settings.carbon_reader != "off" or settings.carbon_levels != "off"
    raster = settings.extractor_raster == "composite" and (keyed or carbon)
    # the describer is built only when triage is on (`_triage`)
    triage = settings.triage_classifier != "off" or settings.sheet_kind != "off"
    describer = triage and settings.triage_describer != "off"
    sheet_kind = settings.sheet_kind != "off"
    evidence = settings.evidence_scope == "all_non_plan"  # it always makes the kind call
    return (
        raster
        or settings.decisions_confidence
        or settings.decisions_kind
        or describer
        or sheet_kind
        or evidence
    )


def build_evidence(settings: Settings, root: Path) -> SqliteEvidenceIndex:
    """The projects' evidence index (decision 0012), `evidence.sqlite` in each project's folder
    under `root`: hybrid with the manifest's embedder, BM25 alone without a manifest."""
    manifest = settings.evidence_embedder_manifest
    try:
        embedder = load_embedder(manifest)
    except DomainError as error:  # a broken model folder stops startup, naming the setting
        raise InvalidInputError(f"EVIDENCE_EMBEDDER_MANIFEST={manifest}: {error}") from error
    if embedder is None:
        logger.info("evidence index: no embedder manifest, BM25 only")
    texts = StoredTexts(DiskProjectStore(root), FileTextReader())
    return SqliteEvidenceIndex(root, passages, embedder, texts)


class EvidenceIndexes:
    """Opens one project's evidence index for the agent's tools and the REST routes. The
    agent loop calls `evidence_index(project_id)` once per chat; NotFoundError for an unknown
    project."""

    def __init__(
        self,
        store: SqliteEvidenceIndex,
        status_of: Callable[[str], ProjectStatus],
        credit_of: CreditOf,
    ) -> None:
        self._store, self._status_of, self._credit_of = store, status_of, credit_of

    def evidence_index(self, project_id: str) -> ProjectEvidence:
        return ProjectEvidence(self._store, self._status_of(project_id), self._credit_of)


def build_models_3d(settings: Settings) -> GlbModels | None:
    """MODEL_3D: the 3D views of IFC files, cached beside the projects' drawing models; None off."""
    if not settings.model_3d:
        return None
    return GlbModels(
        settings.projects_dir / "models-3d",
        settings.model_3d_memory_mb,
        settings.model_3d_timeout_s,
    )


def build_ingest(
    settings: Settings,
    root: Path,
    *,
    background: bool = True,
    triage: TriageSteps | None = None,
    evidence: SqliteEvidenceIndex | None = None,
) -> IngestService:
    """Project ingest over the projects folder `root` (data/projects/). `background` False runs
    each upload inside `start` (CLI, tests). The readers' names are part of the cache key, so a
    changed reader ingests a file again. Reader settings that do not build raise here, so the
    app fails at startup instead of setting every upload aside. `triage`: file triage's ports,
    instead of the settings' (tests). `evidence`: the evidence index to keep in step, shared with
    the REST routes (one embedder session); by default the settings' one."""
    build_pipeline(settings, root)
    store = DiskProjectStore(root)
    names = {
        "bim": settings.extractor_bim,
        "cad": settings.extractor_cad,
        "vector": settings.extractor_vector,
        "raster": settings.extractor_raster,
        "raster_components": settings.raster_components,
        "tables": settings.tables,
        "second_counter": settings.second_counter,
        "rectifier": settings.rectifier,  # it makes the frame every box is in
        "decisions_kind": str(settings.decisions_kind),  # it can make an image a photo
    }
    if settings.raster_scale != "off":  # named only when on: the default keeps its cache keys
        names["raster_scale"] = settings.raster_scale
    if settings.scale_carbon_doors != "off":  # the same
        names["scale_carbon_doors"] = settings.scale_carbon_doors
    if settings.raster_printed_scale != "off":  # the same
        names["raster_printed_scale"] = settings.raster_printed_scale
    if settings.printed_total_answers != "off":  # the same
        names["printed_total_answers"] = settings.printed_total_answers
    if settings.printed_ocr_check != "off" and settings.raster_printed_scale != "off":  # the same
        names["printed_ocr_check"] = settings.printed_ocr_check
    if settings.gross_net_check != "off" and settings.raster_printed_scale != "off":  # the same
        names["gross_net_check"] = settings.gross_net_check
    if settings.door_prior_boxes != "off":  # the same
        names["door_prior_boxes"] = settings.door_prior_boxes
    if settings.door_prior_units != "off":  # the same
        names["door_prior_units"] = settings.door_prior_units
    if settings.scale_signatures != "off":  # the same
        names["scale_signatures"] = settings.scale_signatures
    if settings.raster_photo_components:  # the same
        names["raster_photo_components"] = settings.raster_photo_components
    if settings.room_policy != "furniture":  # the same
        names["room_policy"] = settings.room_policy
    if settings.extractor_raster == "composite":  # its rooms take their Swiss printed names
        # (room_words.py): readings stored before that are read again
        names["room_words"] = "swiss+generic:v1"  # +generic: "Rum", "H" are no bedrooms
        names["floor_plans"] = "rooms:v2"  # v2: drop only a box with no room (plan_rooms.py)
    if settings.double_check_readers:  # the same
        names["double_check_readers"] = settings.double_check_readers
    if settings.raster_tiles != "off":  # the same
        names["raster_tiles"] = settings.raster_tiles
    if settings.vector_fallback != "off":  # the same; v2 reads the page only when the vector
        # reader read nothing, and keeps that reading only when it found something (r10)
        names["vector_fallback"] = f"{settings.vector_fallback}:v2"
    if settings.carbon_reader != "off" or _names_carbon(settings):  # the same; with the
        # contract's hash, so a changed prompt or rule reads the files again
        rule = (
            f"large+few{FEW_THINGS}+snap"  # +snap: door boxes on the detector's (#310)
            if settings.carbon_reader == "large"
            else settings.carbon_reader
        )
        # +storey: a plan's floor from its caption or the sheet's title (contract.py)
        names["carbon_reader"] = f"{rule}+storey:{READER_SHA[:12]}"
    if settings.discipline_pictures != "off":  # the same; with the lane's code version
        names["discipline_pictures"] = f"{settings.discipline_pictures}:{PICTURES_CODE}"
        if settings.discipline_runs != "mask":  # named only when not the default
            names["discipline_runs"] = settings.discipline_runs
    if settings.carbon_levels != "off":  # the same; demote and ladder store the same reading
        # (ladder acts only when answering), so they share one name and a switch reads nothing again
        names["carbon_levels"] = f"demote:{READER_SHA[:12]}"
    service = IngestService(
        unpacker=ZipUnpacker(),
        probe=_probe(settings),
        frame=ExifFrame(),
        rectifier=_rectifier(settings.rectifier),
        store=store,
        readers=lambda project_id: build_pipeline(
            settings,
            store.files_dir(project_id),
            _stored_kinds(store, project_id),
            _stored_advanced(store, project_id),
            _stored_sheets(store, project_id),
            _stored_rectified(store, project_id),
        ),
        reader_names=names,
        runner=ThreadRunner() if background else InlineRunner(),
        clock=time.perf_counter,
        now=lambda: datetime.now(UTC).isoformat(timespec="seconds"),
        new_id=lambda: secrets.token_hex(6),
        triage=triage or _triage(settings),
        evidence=evidence or build_evidence(settings, root),
        evidence_steps=_evidence_steps(settings),
        groups_in_flight=settings.ingest_groups_in_flight,
    )
    service.recover()  # a project a restart cut off is marked failed, not left running
    return service


def _extractor(name: ExtractorName, files: DrawingFiles, models: IfcModels) -> Extractor:
    match name:
        case "hello":
            return HelloExtractor()
        case "pdf":
            return PdfVectorExtractor(files)
        case "ifc":
            return IfcModelExtractor(files, models)


def _tables(name: TablesName, inner: Extractor, files: DrawingFiles) -> Extractor:
    match name:
        case "off":
            return inner
        case "pdf":
            return PdfTables(inner, files)


def _raster(
    settings: Settings,
    files: DrawingFiles,
    decisions: Callable[[], G1MainReader],
    kind_of: Callable[[str], str | None],
    use_carbon: Callable[[str], bool] | None = None,
    took: set[str] | None = None,
) -> Extractor:
    photo = settings.raster_photo_components
    if settings.scale_carbon_doors == "on" and (
        settings.raster_scale != "priors" or settings.carbon_reader != "large"
    ):  # it changes PriorScale's no-door refusal, using CarbonThings' doors
        raise InvalidInputError(
            "SCALE_CARBON_DOORS=on needs RASTER_SCALE=priors and CARBON_READER=large"
        )
    match settings.extractor_raster:
        case "hello":
            if photo:
                raise InvalidInputError("RASTER_PHOTO_COMPONENTS needs EXTRACTOR_RASTER=composite")
            if settings.carbon_reader != "off":
                raise InvalidInputError("CARBON_READER needs EXTRACTOR_RASTER=composite")
            if settings.carbon_levels != "off":
                raise InvalidInputError("CARBON_LEVELS needs EXTRACTOR_RASTER=composite")
            if settings.double_check_readers:
                raise InvalidInputError("DOUBLE_CHECK_READERS needs EXTRACTOR_RASTER=composite")
            return _scaled(settings, HelloExtractor())
        case "composite":
            built = cache(lambda source: _raster_component(source, settings, files, decisions))
            policy = _room_policy(settings.room_policy)
            checks = _double_check(settings.double_check_readers, built)
            shipped = _composite(
                "RASTER_COMPONENTS", settings.raster_components, built, policy, checks
            )
            if photo:
                shipped = PhotoSwitch(
                    shipped,
                    _composite("RASTER_PHOTO_COMPONENTS", photo, built, policy, checks),
                    kind_of,
                )
            shipped = OneAtATime(shipped, settings.ingest_local_in_flight)  # held in memory at once
            shipped = _scaled(settings, shipped)  # PriorScale's door constants fit the detector
            if settings.carbon_reader == "advanced" and settings.sheet_kind == "off":
                raise InvalidInputError(
                    "CARBON_READER=advanced reads the sheet-kind step's `advanced` flag: set "
                    "SHEET_KIND=carbon, or use CARBON_READER=off or all"
                )
            read = shipped
            if use_carbon is not None and settings.carbon_reader == "large":  # things drawn
                read = CarbonThings(shipped, _carbon(settings, files), use_carbon, FEW_THINGS, took)
                if settings.scale_carbon_doors == "on":  # outside CarbonThings: Carbon's doors
                    read = CarbonDoorScale(read)
            elif use_carbon is not None:
                read = CarbonSwitch(shipped, _carbon(settings, files, policy), use_carbon)
            if settings.carbon_levels != "off":  # Carbon reading on its own, as integ's test
                return CarbonChecked(read, _carbon(settings, files, policy))
            return read


def _room_policy(name: RoomPolicyName) -> RoomPolicy:
    """ROOM_POLICY after the Swiss room names, which every raster reading takes (a correctness
    fix, think-acc's certified-wrong Swiss bathroom, orchestrator 2026-11-14): a Swiss sheet's
    room is typed by its printed name as the drawn route types it (room_words.py)."""
    match name:
        case "furniture":
            return _label_rooms
        case "gold-labels":
            return lambda rooms: gold_label_rooms(_label_rooms(rooms))


def _label_rooms(rooms: Sequence[Room]) -> Sequence[Room]:
    """What every raster reading's rooms get: the Swiss names, then a bedroom whose label says
    only "room" is `other` (room_policy.generic_word_rooms)."""
    return generic_word_rooms(swiss_label_rooms(rooms))


def _double_check(readers: str, build: Callable[[str], Extractor]) -> dict[str, str]:
    """DOUBLE_CHECK_READERS parsed, each source built once here (`build` is cached), so one that
    does not build is refused under the setting's own name."""
    try:
        checks = parse_readers(readers)
        for source in checks.values():
            build(source)
    except DomainError as error:
        raise InvalidInputError(f"DOUBLE_CHECK_READERS={readers!r}: {error}") from error
    return checks


def _composite(
    name: str,
    components: str,
    build: Callable[[str], Extractor],
    policy: RoomPolicy | None,
    checks: Mapping[str, str],
) -> Extractor:
    """A spec's composite; a source both specs name is built once (`build` is cached)."""
    try:
        return assemble(parse_components(components), build, policy, checks)
    except DomainError as error:
        raise InvalidInputError(f"{name}={components!r}: {error}") from error


def _scaled(settings: Settings, inner: Extractor) -> Extractor:
    """RASTER_SCALE=priors: a raster sheet without a scale gets an estimated one."""
    match settings.raster_scale:
        case "off":
            return inner
        case "priors":
            composite = settings.extractor_raster == "composite"
            if composite and "scale" in parse_components(settings.raster_components):
                raise InvalidInputError(
                    "RASTER_SCALE=priors estimates the scale itself: drop scale= from "
                    "RASTER_COMPONENTS, or set RASTER_SCALE=off"
                )
            carbon = SOURCE if settings.door_prior_boxes == "on" else None  # Carbon's boxes
            return PriorScale(inner, carbon)


def _labelled(
    settings: Settings,
    inner: Extractor,
    kind_of: Callable[[str], str | None],
    rectified: Callable[[str], bool],
) -> Extractor:
    """LABEL_SCALE=on: the areas printed in room labels give a raster sheet's scale."""
    match settings.label_scale:
        case "off":
            return inner
        case "on" | "always":
            return LabelScale(inner, kind_of, rectified, settings.label_scale == "always")


def _printed(
    settings: Settings,
    inner: Extractor,
    files: DrawingFiles,
    kind_of: Callable[[str], str | None],
) -> Extractor:
    """RASTER_PRINTED_SCALE=carbon: the printed scale and counts (app/adapters/printed_scale/),
    read by gemini-4-carbon on the process's spend guard, cached with the Carbon reader's
    replies (its page reply is shared). PRINTED_OCR_CHECK=on: PP-OCR reads its values again."""
    match settings.raster_printed_scale:
        case "off":
            return inner
        case "carbon":
            key = settings.gemini_api_key.get_secret_value()
            client = CarbonClient(
                key,
                settings.carbon_timeout_s,
                budget=spend_guard(settings),
                in_flight=settings.carbon_calls_in_flight,
            )
            reader = CarbonPrinted(client, files, settings.carbon_cache_dir)
            answers = settings.printed_total_answers == "on"
            checker = PrintedOcr(_ocr(), files) if settings.printed_ocr_check == "on" else None
            gross_net = settings.gross_net_check == "on"
            door_units = settings.door_prior_units == "on"
            return PrintedScale(  # kind: no camera dpi
                inner,
                reader,
                files,
                kind_of,
                answers=answers,
                checker=checker,
                gross_net=gross_net,
                door_units=door_units,
                signatures=settings.scale_signatures,
            )


def _raster_component(
    source: str, settings: Settings, files: DrawingFiles, decisions: Callable[[], G1MainReader]
) -> Extractor:
    """The reader of one RASTER_COMPONENTS source name. A precomputed arm finds an uploaded sheet
    in the Stoa dataset (CREDIT_DATASET, the folder its files are relative to) by its content."""
    kind, _, where = source.partition(":")
    tiles = settings.raster_tiles == "auto"
    match kind:
        case "one-plan" if not where:
            return WholePagePlan()
        case "exp" if where:
            return PrecomputedExtractor(EXP_DIR / where, settings.credit_dataset)
        case "dir" if where:
            return PrecomputedExtractor(Path(where), settings.credit_dataset)
        case "detector" if where:
            arm, _, run = where.partition(":")
            tuned = inside(DETECTOR_RUNS, f"{run}.thresholds.json") if run else None
            return OnnxDetector.from_folder(files, inside(DETECTOR_DIR, arm), tuned, tiles=tiles)
        case "detector-v2" | "detector-v4" | "detector-v8" if where:
            views = int(kind.removeprefix("detector-v"))
            folder = inside(DETECTOR_DIR, where)
            return OnnxDetector.from_folder(files, folder, views=views, tiles=tiles)
        case "verda" if not where:
            client = HttpReaderClient(
                settings.verda_reader_url,
                settings.verda_inference_api_key.get_secret_value(),
                max_in_flight=settings.verda_reader_max_in_flight,
            )
            return RemoteReader(files, client)
        case "gemini" if not where:
            return _gemini_rooms(settings, files)
        case "carbon":  # carbon, or carbon:<READER_SHA[:12]> to pin the contract it reads by
            if where not in ("", READER_SHA[:12]):
                raise InvalidInputError(
                    f"RASTER_COMPONENTS: {source} is not the Carbon reader this build has "
                    f"({SOURCE}, or carbon)"
                )
            return _carbon(settings, files)
        case "regionrooms" if not where:
            if not settings.region_model_dir:
                raise InvalidInputError("RASTER_COMPONENTS: regionrooms needs REGION_MODEL_DIR")
            region = SegmenterRegion(*load_region(Path(settings.region_model_dir)))
            return RegionRooms(_gemini_rooms(settings, files), files, region)
        case "photo" if where:
            return OnnxDetector.from_folder(files, inside(PHOTO_DIR, where))
        case "region" if where:
            region = Path(settings.region_model_dir) if settings.region_model_dir else None
            return RegionDetector.from_folders(files, inside(DETECTOR_DIR, where), region)
        case "arbiter-t1" if where:
            arm, _, run = where.partition(":")
            folder = inside(DETECTOR_DIR, arm)
            tuned = inside(DETECTOR_RUNS, f"{run}.thresholds.json") if run else None
            base = OnnxDetector.from_folder(files, folder, views=8, tiles=tiles)
            second = OnnxDetector.from_folder(files, folder, tuned, tiles=tiles)
            return ArbiterCountExtractor.from_folder(
                base, second, files, Path(settings.arbiter_model_dir)
            )
        case "decisions" if where:
            inner = _raster_component(where, settings, files, decisions)
            return DecisionsCountExtractor(inner, files, decisions())
        case "decisions-s1536" if where:
            inner = _raster_component(where, settings, files, decisions)
            return DecisionsCountExtractor(inner, files, decisions(), arm="S1536")
        case _:
            raise InvalidInputError(
                f"RASTER_COMPONENTS: unknown source {source!r}; sources are "
                "exp:<track>/<arm>, dir:<path>, detector:<arm>[:<tune run>], "
                "detector-v<2|4|8>:<arm>, photo:<arm>, "
                "region:<arm>, verda, gemini, regionrooms, carbon[:<reader hash>], "
                "decisions:<source>, "
                "arbiter-t1:<arm>[:<one-view tune run>], "
                "decisions-s1536:<source> and one-plan"
            )


def _gemini_rooms(settings: Settings, files: DrawingFiles) -> Extractor:
    if settings.rooms_provider == "eu":  # Qwen's own box order (val: region mask works with it)
        reader = GeminiRoomReader(OpenVlmRoomModel(_eu(settings)), settings.gemini_cache_dir)
        return OpenVlmRoomExtractor(files, reader)
    client = GeminiClient(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_model,
        settings.gemini_timeout_s,
        budget=spend_guard(settings),
    )
    return GeminiRoomExtractor(files, GeminiRoomReader(client, settings.gemini_cache_dir))


def _carbon(
    settings: Settings, files: DrawingFiles, policy: RoomPolicy | None = None
) -> CarbonExtractor:
    """The Carbon reader (app/adapters/carbon/) on the process's spend guard. `policy`: ROOM_POLICY
    when it reads a drawing on its own (as a composite's source, the composite applies it)."""
    key = settings.gemini_api_key.get_secret_value()
    client = CarbonClient(
        key,
        settings.carbon_timeout_s,
        budget=spend_guard(settings),
        in_flight=settings.carbon_calls_in_flight,
    )
    reader = CarbonReader(client, settings.carbon_cache_dir, settings.carbon_read_workers)
    return CarbonExtractor(files, reader, policy)


def _names_carbon(settings: Settings) -> bool:
    """Whether a raster spec names the `carbon` source."""
    specs = (
        settings.raster_components,
        settings.raster_photo_components,
        settings.double_check_readers,
    )
    sources = (part.partition("=")[2].strip() for spec in specs for part in spec.split(","))
    return any(source.partition(":")[0] == "carbon" for source in sources)


def decisions_reader(settings: Settings) -> G1MainReader:
    """Gemini Decisions' count reader. The count swap and the answer confidence share its cache
    (DECISIONS_CACHE_DIR), so each page is paid for once."""
    if settings.decisions_provider == "eu":  # joint: one call per page (val: beats the walk)
        decider = OpenVlmDecider(_eu(settings), joint=True)
        return G1MainReader(decider, settings.decisions_cache_dir)
    key = settings.gemini_api_key.get_secret_value()
    client = DecisionsClient(key, settings.decisions_timeout_s, budget=spend_guard(settings))
    return G1MainReader(client, settings.decisions_cache_dir)


def spend_guard(settings: Settings) -> SpendGuard:
    """The process's one Gemini ledger (GEMINI_BUDGET_USD, GEMINI_BUDGET_USD_PER_HOUR; how to use
    it: app/core/spend.py), shared by every Gemini caller built from these limits. With neither
    set it only counts and never refuses."""
    return _spend_guard(settings.gemini_budget_usd, settings.gemini_budget_usd_per_hour)


@cache
def _spend_guard(total_usd: float | None, per_hour_usd: float | None) -> SpendGuard:
    return SpendGuard(total_usd, per_hour_usd)


def _eu(settings: Settings) -> OpenVlmClient:
    """Our open-model server (EU_VLM_*); one client per step that uses it."""
    return OpenVlmClient(
        settings.eu_vlm_base_url,
        settings.eu_vlm_api_key.get_secret_value(),
        settings.eu_vlm_model,
        settings.eu_vlm_timeout_s,
    )


def _checked(name: TablesName, inner: SecondCounter, files: DrawingFiles) -> SecondCounter:
    """TABLES=pdf also counts the doors of a PDF set twice: its door schedule, its plans' tags."""
    match name:
        case "off":
            return inner
        case "pdf":
            return ScheduleTagCounter(inner, files)


def second_counter_of(names: Mapping[str, str], route: Route | None) -> str:
    """The second counter that measured a drawing of `route`, by name (`names`: readers()): the
    IFC one measures a model (the bim route) and passes every other file on to the PDF counter
    (_second_counter)."""
    name = names["second_counter"]
    return "pdf" if name == "ifc" and route != "bim" else name


def _second_counter(
    name: SecondCounterName, files: DrawingFiles, models: IfcModels
) -> SecondCounter:
    match name:
        case "hello":
            return HelloSecondCounter()
        case "pdf":
            return PdfSecondCounter(files)
        case "ifc":
            return IfcSecondCounter(files, models, PdfSecondCounter(files))


def _parser(name: QuestionParserName) -> QuestionParser:
    match name:
        case "hello":
            return HelloParser()
        case "templates":
            return TemplateParser()


def _gate(settings: Settings) -> dict[str, float] | None:
    """GATE_POLICY's thresholds on the answer confidence's signal; None without a gate file or
    without the confidence (a threshold on a signal nothing computes would mark nothing)."""
    if not settings.gate_policy or not settings.decisions_confidence:
        return None
    return load_gate(Path(settings.gate_policy), DECISIONS_SIGNAL)


def _scorers(paths: str) -> dict[str, Scorer]:
    """LOCAL_GATES: the local gate models a check policy's family may be certified on, by their
    signal name in lower case (app/adapters/check_policy.py compares names without case)."""
    scorers: dict[str, Scorer] = {}
    for path in filter(None, (part.strip() for part in paths.split(","))):
        model = load_local_gate(Path(path))
        if (name := model.name.lower()) in scorers:
            raise InvalidInputError(f"LOCAL_GATES: two models are named {model.name}")
        scorers[name] = gate_scorer(model)
    return scorers


def _policy(path: str) -> frozenset[tuple[str, str]]:
    return load_policy(Path(path)) if path else frozenset()


def _prior(name: AnswerPriorName) -> AnswerPrior:
    match name:
        case "none":
            return NoPrior()
        case "dev":
            return TablePrior(DEV_PRIOR)


def chat_model(settings: Settings) -> tuple[ChatModel | None, str | None]:
    """The project chat's model by CHAT_MODEL, or None and why the chat is not available."""
    match settings.chat_model:
        case "off":
            return None, "the agent chat is off (CHAT_MODEL=off)"
        case "rules":
            return RulesChatModel(), None
        case "gemini":
            key = settings.gemini_api_key.get_secret_value()
            if not key:
                return None, "the agent chat needs GEMINI_API_KEY"
            model = OpenAiChatModel(
                settings.agent_base_url,
                key,
                settings.agent_model,
                settings.agent_price_in_per_m,
                settings.agent_price_out_per_m,
                thinking=settings.agent_thinking,
                price_cached=settings.agent_price_cached_per_m,
            )
            return model, None


def chat_caps(settings: Settings) -> Caps:
    return Caps(max_steps=settings.agent_max_steps, turn_usd=settings.agent_turn_usd)

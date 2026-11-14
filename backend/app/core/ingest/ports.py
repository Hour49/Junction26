"""What project ingest needs from outside, as Protocols. app/adapters/archive implements them,
app/composition.py wires them, and the tests pass fakes."""

from collections.abc import Callable, Collection, Iterator, Mapping
from typing import Protocol

from app.core.drawing.model import Drawing
from app.core.ingest.model import (
    Classified,
    ContentKind,
    Description,
    Entry,
    FileTrace,
    Normalised,
    Outcome,
    Probed,
    ProjectContext,
    ProjectStatus,
    Rectified,
    Relevance,
    Unavailable,
)
from app.core.pipeline.model import Route
from app.core.pipeline.ports import (
    DrawingFiles,
    Extractor,
    PageReader,
    SecondCounter,
    SourceFinder,
)


class Unpacker(Protocol):
    """Stage 1: the files of an upload. A zip (by content) is unpacked safely; anything else is
    a one-file project. A file the unpacker refuses (unsafe path, size cap, symlink...) comes
    back as an `Entry` with `refused` set, so it is listed with its reason. Raises
    InvalidInputError when the upload as a whole cannot be read."""

    def entries(self, name: str, data: bytes) -> Iterator[Entry]: ...


class ContentProbe(Protocol):
    """Stage 3: what a file is from its bytes, never from its name."""

    def probe(self, data: bytes) -> Probed: ...


class ImageFrame(Protocol):
    """Stage 6 for an image, before the pipeline reads it: the image brought upright (EXIF
    orientation now; the photo rectifier later). Returns the bytes the pipeline reads and
    serves, and how they were made. None: `data` is not an image."""

    def normalise(self, data: bytes) -> tuple[bytes, Normalised] | None: ...


class Rectifier(Protocol):
    """Stage 6 for a photo of a drawing: find the paper and undo the perspective. It gets the
    upright image (EXIF orientation applied) and its content kind, and returns the paper seen
    straight on with the paper's corners in the image it got, or None to keep the image as it
    is (not a photo, no paper found). The pipeline then reads, and the API serves, its image,
    so every box is in its frame. The default reads nothing and returns None."""

    def rectify(self, image: bytes, kind: ContentKind) -> Rectified | None: ...


class Classifier(Protocol):
    """Triage step 1 (decision 0010): is this image a floor plan, another drawing or not a
    drawing. It gets the bytes and what the probe said. Unsure must come back as `floor_plan`
    (a plan set aside is never read). `Unavailable`: the file goes on as today."""

    def classify(self, image: bytes, probed: Probed) -> Classified | Unavailable: ...


class Describer(Protocol):
    """Triage step 2: what a file that is not a floor plan shows, in words. An adapter tells
    its model not to transcribe personal data (names of private people, phone numbers, number
    plates, home addresses): `text_seen` is title-block and caption text only. The repo and
    demo are public (decision 0010, board #152 item 11)."""

    def describe(self, image: bytes, classified: Classified) -> Description | Unavailable: ...


class RelevanceJudge(Protocol):
    """Triage step 3: does a described file belong to the project, judged against the project's
    own data once its plans are read. Always a suggestion; a person can overrule it."""

    def judge(
        self, description: Description, context: ProjectContext
    ) -> Relevance | Unavailable: ...


class Readers(Protocol):
    """The pipeline's ports for the files of one project (app/composition.py's `Pipeline`)."""

    @property
    def files(self) -> DrawingFiles: ...
    @property
    def finder(self) -> SourceFinder: ...
    @property
    def pages(self) -> PageReader: ...
    @property
    def extractors(self) -> Mapping[Route, Extractor]: ...
    @property
    def second_counter(self) -> SecondCounter: ...
    @property
    def readable(self) -> Collection[Route]:
        """The routes whose extractor reads something (stage 5 prefers them)."""
        ...

    @property
    def scanned(self) -> Callable[[bytes], bool] | None:
        """Whether a PDF is a scan (stage 5 routes it to the raster reader)."""
        ...


class ProjectStore(Protocol):
    """Projects, their files, and the drawings and outcomes kept by content."""

    def put_file(self, project_id: str, path: str, data: bytes) -> None:
        """The file the pipeline reads (an image: normalised)."""
        ...

    def read_file(self, project_id: str, path: str) -> bytes: ...
    def put_upload(self, project_id: str, path: str, data: bytes) -> None:
        """The upload's own bytes, kept when the file the pipeline reads differs from them."""
        ...

    def read_upload(self, project_id: str, path: str) -> bytes:
        """The file as uploaded: what `put_upload` kept, else the file itself."""
        ...

    def save_project(self, status: ProjectStatus, traces: Mapping[str, FileTrace]) -> None: ...
    def load_project(self, project_id: str) -> tuple[ProjectStatus, dict[str, FileTrace]]:
        """Raises NotFoundError for an unknown project."""
        ...

    def project_ids(self) -> list[str]: ...

    def outcome(self, key: str) -> Outcome | None: ...
    def save_outcome(self, outcome: Outcome, drawing: Drawing | None) -> None: ...
    def drawing(self, drawing_id: str) -> Drawing:
        """Raises NotFoundError for an unknown drawing."""
        ...


class Runner(Protocol):
    """Runs a job in the background, one at a time, in the order given."""

    def submit(self, job: Callable[[], None]) -> None: ...
    def close(self) -> None: ...


Clock = Callable[[], float]  # seconds, monotonic
Now = Callable[[], str]  # the time as ISO 8601 UTC
NewId = Callable[[], str]  # a fresh project id

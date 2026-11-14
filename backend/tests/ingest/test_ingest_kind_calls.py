"""The sheet-kind signal (DECISIONS_KIND) at ingest: asked only where it can change a file's
kind (a drawing image the probe calls png_plan or jpeg_plan), and asked for several files at
once, at most PROBES_IN_FLIGHT, with the results applied in upload order. Offline: a stand-in
reader; no timing decides a result (a wait has a deadlock guard only)."""

import io
import threading
import zipfile
from pathlib import Path

import pytest
from conftest import MakeService
from PIL import Image

import app.core.ingest.service as service
from app.adapters.archive import FileProbe
from app.adapters.decisions_kind import KINDS, KindSignal, KindUnavailable
from app.adapters.decisions_kind.probe import KindProbe
from app.core.ingest.model import FileTrace
from scripts.make_sample_archive import build_archive

LIMIT = 4  # signal calls in flight at most (the brief: as serve's client)
GUARD_S = 5.0  # only ever reached when the code under test is wrong (a deadlock)


def drawing(width: int) -> bytes:
    """A small line drawing on white, told apart by its width."""
    image = Image.new("RGB", (width, 300), "white")
    image.paste((0, 0, 0), (20, 40, width - 20, 48))
    image.paste((0, 0, 0), (20, 200, width - 20, 208))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def upload(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


WIDTHS = (401, 402, 403, 404, 405, 406)
DRAWINGS = {f"scans/{n}.png": drawing(width) for n, width in enumerate(WIDTHS, start=1)}


def width_of(data: bytes) -> int:
    with Image.open(io.BytesIO(data)) as image:
        return image.width


def signal(width: int) -> KindSignal:
    """Every other drawing is flagged a photo of a plan, so kinds differ by file."""
    top = "photo_plan" if width % 2 == 0 else "floor_plan"
    return KindSignal(dict.fromkeys(KINDS, 0.0) | {top: 0.95}, f"stand-in for {width}")


class Recording:
    """Answers at once and keeps what it was sent."""

    def __init__(self) -> None:
        self.asked: list[bytes] = []
        self._lock = threading.Lock()

    def read(self, data: bytes) -> KindSignal | KindUnavailable:
        with self._lock:
            self.asked.append(data)
        try:
            return signal(width_of(data))
        except OSError:  # not an image
            return KindUnavailable("kind signal not available: stand-in reads images only")


class Gate:
    """Holds every call until LIMIT calls are in at the same time, and counts the
    most that ever were."""

    def __init__(self) -> None:
        self.most = self.now = 0
        self.full = threading.Event()
        self._lock = threading.Lock()

    def read(self, data: bytes) -> KindSignal | KindUnavailable:
        with self._lock:
            self.now += 1
            self.most = max(self.most, self.now)
            if self.now == LIMIT:
                self.full.set()
        self.full.wait(GUARD_S)
        with self._lock:
            self.now -= 1
        return signal(width_of(data))


class LateFirst:
    """The first drawing's answer comes only after the third's has: finished out of order."""

    def __init__(self) -> None:
        self.third_done = threading.Event()
        self.waited_in_vain = False

    def read(self, data: bytes) -> KindSignal | KindUnavailable:
        width = width_of(data)
        if width == WIDTHS[0]:
            self.waited_in_vain = not self.third_done.wait(GUARD_S)
        answer = signal(width)
        if width == WIDTHS[2]:
            self.third_done.set()
        return answer


def trace_of(
    make_service: MakeService, root: Path, reader: object, files: dict[str, bytes]
) -> list[FileTrace]:
    ingest = make_service(root=root, probe=KindProbe(FileProbe(), reader))  # type: ignore[arg-type]
    status = ingest.status(ingest.start("upload.zip", upload(files)))
    return [ingest.trace(status.id, file.id) for file in status.files]


def test_only_a_drawing_image_is_asked_for_its_kind(
    make_service: MakeService, tmp_path: Path
) -> None:
    """The signal changes only a png_plan/jpeg_plan (to photo_plan). A PDF, and a photo the
    probe already knows by its camera EXIF, are not sent (they were, for a trace line)."""
    with zipfile.ZipFile(io.BytesIO(build_archive())) as archive:
        pdf, photo = archive.read("plans/flat-a.pdf"), archive.read("photos/plan-photo.jpg")
    files = {"a.pdf": pdf, "b.png": drawing(401), "c.jpg": photo}
    reader = Recording()
    kinds = [t.file.kind for t in trace_of(make_service, tmp_path, reader, files)]
    assert kinds == ["pdf_vector", "png_plan", "photo_plan"]
    assert reader.asked == [files["b.png"]]


def test_at_most_four_signal_calls_are_in_flight_and_four_are_reached(
    make_service: MakeService, tmp_path: Path
) -> None:
    gate = Gate()
    traces = trace_of(make_service, tmp_path, gate, DRAWINGS)
    assert gate.full.is_set() and gate.most == LIMIT
    assert [t.file.path for t in traces] == list(DRAWINGS)


def test_results_finished_out_of_order_are_applied_in_upload_order(
    make_service: MakeService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    late = LateFirst()
    concurrent = trace_of(make_service, tmp_path / "a", late, DRAWINGS)
    assert not late.waited_in_vain
    monkeypatch.setattr(service, "PROBES_IN_FLIGHT", 1, raising=False)
    serial = trace_of(make_service, tmp_path / "b", Recording(), DRAWINGS)

    def shown(traces: list[FileTrace]) -> list[object]:
        return [
            (t.file.id, t.file.path, t.file.kind, t.file.state, t.file.reason, t.stages)
            for t in traces
        ]

    assert shown(concurrent) == shown(serial)
    assert [t.file.kind for t in serial] == ["png_plan", "photo_plan"] * 3

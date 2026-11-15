"""Groups read as soon as their files are identified (app/core/ingest/groups.py `Feed`)."""

import io
import threading
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

from conftest import MakeService
from PIL import Image
from test_ingest_parallel import zipped

from app.adapters.archive import FileProbe
from app.core.drawing.model import Scale
from app.core.ingest.groups import Feed
from app.core.ingest.model import Entry, Probed, ProjectStatus
from app.core.ingest.progress import Run
from app.core.pipeline.model import DrawingFile, DrawingGroup, Extracted, Sheet
from scripts.make_sample_archive import png_bytes, raster_plan


def plans(count: int) -> list[bytes]:
    """`count` different raster plans."""
    base = raster_plan()
    turned = [base.rotate(turn, expand=True) for turn in (0, 90, 180, 270)]
    turned += [plan.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for plan in turned]
    return [png_bytes(plan) for plan in turned[:count]]


class Gated:
    """A probe that holds the file `slow` until the reader has started on `first`."""

    def __init__(self, slow: bytes, timeout: float = 10) -> None:
        self.slow, self.timeout = slow, timeout
        self.reading = threading.Event()
        self.waited: list[bool] = []

    def probe(self, data: bytes) -> Probed:
        if data == self.slow:
            self.waited.append(self.reading.wait(self.timeout))
        return FileProbe().probe(data)


class Reads:
    """A raster reader that says when it started and which files it read."""

    def __init__(self, gate: Gated, first: str) -> None:
        self.gate, self.first = gate, first
        self.paths: list[str] = []

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.paths.append(source.path)
        if source.path == self.first:
            self.gate.reading.set()
        return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))


def test_a_group_is_read_before_a_later_file_s_check_has_ended(make_service: MakeService) -> None:
    a, b = plans(2)
    gate = Gated(slow=b)
    reader = Reads(gate, "a.png")
    ingest = make_service(probe=gate, raster=lambda files: reader, groups_in_flight=2)
    status = ingest.status(ingest.start("two.zip", zipped({"a.png": a, "b.png": b})))
    assert gate.waited == [True]  # b's check ended only after a's reading had started
    assert [file.state for file in status.files] == ["ready", "ready"]
    assert sorted(reader.paths) == ["a.png", "b.png"]


def test_a_slow_check_holds_up_only_its_own_file(make_service: MakeService) -> None:
    """a.png's check is slow: b.png, after it in the upload, is identified and read first."""
    a, b = plans(2)
    gate = Gated(slow=a)
    reader = Reads(gate, "b.png")
    ingest = make_service(probe=gate, raster=lambda files: reader, groups_in_flight=2)
    status = ingest.status(ingest.start("two.zip", zipped({"a.png": a, "b.png": b})))
    assert gate.waited == [True]
    assert [file.path for file in status.files] == ["a.png", "b.png"]  # upload order
    assert [file.state for file in status.files] == ["ready", "ready"]


class FirstSlow:
    """A probe whose first call for `data` takes 0.6 s, so a later copy's check ends first."""

    def __init__(self, data: bytes) -> None:
        self.data, self.calls, self.lock = data, 0, threading.Lock()

    def probe(self, data: bytes) -> Probed:
        if data == self.data:
            with self.lock:
                self.calls += 1
                first = self.calls == 1
            if first:
                threading.Event().wait(0.6)
        return FileProbe().probe(data)


def test_a_copy_is_named_after_the_file_first_in_the_upload(make_service: MakeService) -> None:
    """The copy's check ends first, but the earlier upload is still the one it copies."""
    a, b = plans(2)
    ingest = make_service(probe=FirstSlow(a))
    status = ingest.status(ingest.start("c.zip", zipped({"a.png": a, "b.png": b, "c.png": a})))
    hashes = {
        file.path: next(s.did for s in ingest.trace(status.id, file.id).stages if s.stage == "hash")
        for file in status.files
    }
    assert hashes["c.png"].endswith("same content as a.png")
    assert "same content" not in hashes["a.png"]


def test_a_group_waits_for_a_later_file_of_its_name(make_service: MakeService) -> None:
    """a.png is identified first, a.jpg (the same drawing) last, its check slow and its entry
    unpacked only after a.png's check: group a is read with both files, after a.jpg's check."""
    a, *others = plans(6)
    buffer = io.BytesIO()
    Image.open(io.BytesIO(a)).convert("RGB").save(buffer, "JPEG")
    gate = Gated(slow=buffer.getvalue(), timeout=1)
    reader = Reads(gate, "a.png")
    files = {"a.png": a, **{f"{n}.png": data for n, data in enumerate(others[:4])}}
    files["a.jpg"] = buffer.getvalue()
    ingest = make_service(probe=gate, raster=lambda files: reader, groups_in_flight=4)
    status = ingest.status(ingest.start("six.zip", zipped(files)))
    assert gate.waited == [False]  # nothing of group a was read before a.jpg was identified
    by_path = {file.path: file for file in status.files}
    assert by_path["a.png"].group == by_path["a.jpg"].group == "a"
    assert all(file.state in ("ready", "flagged") for file in status.files), status.files


def drawing(path: str, sha256: str | None = None) -> DrawingFile:
    return DrawingFile(path=path, size=1, sha256=sha256 or path, kind="pdf")


class Finder:
    def __init__(self, sources: dict[str, Sequence[str]]) -> None:
        self._sources = sources

    def sources(self, path: str) -> Sequence[str]:
        return self._sources.get(path, ())


class Recorded:
    """A group's read: records the group, holds the one named `held` until `go`."""

    def __init__(self, held: str = "") -> None:
        self.held, self.go = held, threading.Event()
        self.groups: list[tuple[str, tuple[str, ...]]] = []
        self.inside, self.most = 0, 0
        self.changed = threading.Condition()

    def __call__(self, run: Any, readers: Any, members: DrawingGroup, asked: Any) -> None:
        with self.changed:
            self.groups.append((members.key, tuple(file.path for file in members.files)))
            self.inside += 1
            self.most = max(self.most, self.inside)
            self.changed.notify_all()
        if members.key == self.held:
            assert self.go.wait(10)
        with self.changed:
            self.inside -= 1


def feed(read: Recorded, sources: dict[str, Sequence[str]] | None = None) -> Feed:
    run = Run(ProjectStatus(id="p", name="p", state="running", created_at="now"), fresh=False)
    for path in ("a.pdf", "b.pdf", "m.ifc", "s.pdf", "s#p2.png", "x/c.png", "y/c.png"):
        run.add(Entry(path=path, size=1))
    readers = SimpleNamespace(finder=Finder(sources or {}))
    return Feed(read, 2, run, readers, lambda: None)  # pyright: ignore[reportArgumentType]


def test_a_sheet_s_group_waits_for_its_model_still_being_identified() -> None:
    read = Recorded()
    fed = feed(read, {"a.pdf": ["m.ifc"]})
    for path in ("a.pdf", "m.ifc"):
        fed.pending(path, path)
    fed.unpacked()
    fed.identified("a.pdf", drawing("a.pdf"))
    assert read.groups == []  # its source m.ifc may join it
    fed.identified("m.ifc", drawing("m.ifc"))
    fed.wait()
    assert sorted(read.groups) == [("a", ("a.pdf", "m.ifc")), ("m", ("m.ifc",))]


def test_a_group_waits_for_the_pdf_whose_page_it_could_be() -> None:
    read = Recorded()
    fed = feed(read)
    for path in ("s#p2.png", "s.pdf"):
        fed.pending(path, path)
    fed.unpacked()
    fed.identified("s#p2.png", drawing("s#p2.png"))
    assert read.groups == []  # s.pdf's page 2 would be the file s#p2.pdf, group s#p2
    fed.identified("s.pdf", drawing("s.pdf"))
    fed.wait()
    assert sorted(key for key, _ in read.groups) == ["s", "s#p2"]


def test_nothing_is_read_before_the_upload_is_unpacked() -> None:
    read = Recorded()
    fed = feed(read)
    fed.pending("a.pdf", "a.pdf")
    fed.identified("a.pdf", drawing("a.pdf"))
    assert read.groups == []
    fed.unpacked()
    fed.wait()
    assert read.groups == [("a", ("a.pdf",))]


def test_a_copy_started_later_is_read_after_the_first() -> None:
    """Same content, two groups started at different times: the copy waits for the first, so
    it can reuse what the first stored."""
    read = Recorded(held="x/c")
    fed = feed(read)
    for path in ("x/c.png", "y/c.png"):
        fed.pending(path, path)
    fed.unpacked()
    fed.identified("x/c.png", drawing("x/c.png", "same"))
    fed.identified("y/c.png", drawing("y/c.png", "same"))
    with read.changed:  # x/c is held: y/c must not start
        assert not read.changed.wait_for(lambda: len(read.groups) > 1, timeout=0.5)
    read.go.set()
    fed.wait()
    assert [key for key, _ in read.groups] == ["x/c", "y/c"]
    assert read.most == 1


def test_a_later_copy_identified_first_waits_for_the_earlier_one() -> None:
    """y/c.png (a copy of x/c.png, after it in the upload) is identified first: it is read only
    after x/c.png, so x/c.png is the reading and y/c.png the one that reuses it."""
    read = Recorded()
    fed = feed(read)
    for path in ("x/c.png", "y/c.png"):
        fed.pending(path, "same")
    fed.unpacked()
    fed.identified("y/c.png", drawing("y/c.png", "same"))
    assert read.groups == []
    fed.identified("x/c.png", drawing("x/c.png", "same"))
    fed.wait()
    assert [key for key, _ in read.groups] == ["x/c", "y/c"]


def test_files_with_nothing_in_common_are_read_side_by_side() -> None:
    read = Recorded(held="a")
    fed = feed(read)
    for path in ("a.pdf", "b.pdf"):
        fed.pending(path, path)
    fed.unpacked()
    fed.identified("a.pdf", drawing("a.pdf"))
    fed.identified("b.pdf", drawing("b.pdf"))
    with read.changed:
        assert read.changed.wait_for(lambda: len(read.groups) == 2, timeout=10)
    read.go.set()
    fed.wait()
    assert read.most == 2


def test_the_status_is_saved_as_each_group_ends() -> None:
    """b ends while a is still held: a save follows b's end before a ends (review-453 Should 1:
    the saves all came at the end)."""
    read = Recorded(held="a")
    ended: list[str] = []
    saves: list[tuple[str, ...]] = []
    saved = threading.Event()

    def save() -> None:
        saves.append(tuple(ended))
        if ended:
            saved.set()

    def reading(run: Any, readers: Any, members: DrawingGroup, asked: Any) -> None:
        read(run, readers, members, asked)
        ended.append(members.key)

    run = Run(ProjectStatus(id="p", name="p", state="running", created_at="now"), fresh=False)
    for path in ("a.pdf", "b.pdf"):
        run.add(Entry(path=path, size=1))
    fed = Feed(reading, 2, run, SimpleNamespace(finder=Finder({})), save)  # pyright: ignore[reportArgumentType]
    for path in ("a.pdf", "b.pdf"):
        fed.pending(path, path)
    fed.unpacked()
    fed.identified("a.pdf", drawing("a.pdf"))
    fed.identified("b.pdf", drawing("b.pdf"))
    waiting = threading.Thread(target=fed.wait)
    waiting.start()
    assert saved.wait(10)  # b's end is saved while a is still held
    assert ("b",) in saves
    read.go.set()
    waiting.join(10)
    assert saves[-1] == ("b", "a")

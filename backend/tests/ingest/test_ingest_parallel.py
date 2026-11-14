"""Drawing groups read at once (INGEST_GROUPS_IN_FLIGHT, groups.py), and the cap on Carbon calls in
flight (carbon/reader.py). Overlap is shown with barriers, never with sleeps or timings."""

import io
import threading
import urllib.request
import zipfile
from typing import Any

import pytest
from conftest import MakeService
from PIL import Image

from app.adapters.carbon import reader as carbon
from app.core import cost
from app.core.drawing.model import Scale
from app.core.ingest import groups
from app.core.pipeline.model import DrawingFile, DrawingGroup, Extracted, Sheet
from scripts.make_sample_archive import png_bytes, raster_plan


def zipped(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


def two_scans() -> bytes:
    plan = raster_plan()
    turned = plan.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return zipped({"a.png": png_bytes(plan), "b.png": png_bytes(turned)})


class Together:
    """A raster reader whose reads wait for each other: two groups read one by one never meet,
    so the first one fails at the barrier. Each read charges its own price."""

    def __init__(self, parties: int) -> None:
        self.met = threading.Barrier(parties, timeout=10)

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.met.wait()
        cost.charge(0.01 if source.path == "a.png" else 0.02)
        return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))


def test_two_groups_are_read_at_once_and_each_file_keeps_its_own_cost(
    make_service: MakeService,
) -> None:
    reader = Together(2)
    ingest = make_service(raster=lambda files: reader, groups_in_flight=2)
    status = ingest.status(ingest.start("two.zip", two_scans()))
    assert status.state == "done"
    a, b = status.files
    assert [a.path, b.path] == ["a.png", "b.png"]  # upload order, whichever was read first
    assert (a.state, b.state) == ("ready", "ready"), (a.reason, b.reason)
    assert (a.cost_usd, b.cost_usd) == (0.01, 0.02)
    for file, usd in ((a, 0.01), (b, 0.02)):
        (extract,) = [s for s in ingest.trace(status.id, file.id).stages if s.stage == "extract"]
        assert extract.cost_usd == usd
    assert status.cost_usd == pytest.approx(0.03)


def test_one_group_in_flight_reads_them_one_by_one(make_service: MakeService) -> None:
    reader = Together(2)
    reader.met = threading.Barrier(2, timeout=0.5)  # alone at the barrier: it breaks
    ingest = make_service(raster=lambda files: reader, groups_in_flight=1)
    status = ingest.status(ingest.start("two.zip", two_scans()))
    assert [file.state for file in status.files] == ["set_aside", "set_aside"]
    assert all("BrokenBarrierError" in file.reason for file in status.files)


def test_the_status_is_saved_after_each_group_on_the_run_s_thread(
    make_service: MakeService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Saves never run side by side: the run's thread writes the status, the groups don't."""
    ingest = make_service(raster=lambda files: Together(2), groups_in_flight=2)
    saved_on: list[str] = []
    save = ingest._save  # pyright: ignore[reportPrivateUsage]

    def noted(run: Any) -> None:
        saved_on.append(threading.current_thread().name)
        save(run)

    monkeypatch.setattr(ingest, "_save", noted)
    status = ingest.status(ingest.start("two.zip", two_scans()))
    assert status.state == "done"
    assert set(saved_on) == {threading.current_thread().name}
    assert len(saved_on) >= 2 + 2  # unpacked, groups known, then once per group, then done


def test_a_group_that_raises_fails_the_project_after_the_other_group_is_read(
    make_service: MakeService, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = groups.Groups._group  # pyright: ignore[reportPrivateUsage]

    def broken(self: groups.Groups, run: Any, readers: Any, members: DrawingGroup, asked: Any):
        if members.key == "a":
            raise RuntimeError("the store broke")
        return read(self, run, readers, members, asked)

    monkeypatch.setattr(groups.Groups, "_group", broken)
    reader = Together(1)
    ingest = make_service(raster=lambda files: reader, groups_in_flight=2)
    status = ingest.status(ingest.start("two.zip", two_scans()))
    assert (status.state, status.error) == ("failed", "RuntimeError: the store broke")
    a, b = status.files
    assert (a.state, a.reason) == ("set_aside", "not ingested: RuntimeError: the store broke")
    assert b.state == "ready"


def test_a_copy_in_another_group_reuses_the_first_reading(make_service: MakeService) -> None:
    """The same content under two names: read one after the other, so the copy is served from
    what the first stored (one paid reading), as when groups were read one by one."""
    reader = Together(1)
    plan = png_bytes(raster_plan())
    ingest = make_service(raster=lambda files: reader, groups_in_flight=2)
    status = ingest.status(ingest.start("copy.zip", zipped({"a.png": plan, "b.png": plan})))
    a, b = status.files
    assert (a.state, a.reused, b.state, b.reused) == ("ready", False, "ready", True)


def drawing(path: str) -> DrawingFile:
    return DrawingFile(path=path, size=1, sha256=path, kind="pdf")


def group(key: str, *paths: str) -> tuple[DrawingGroup, list[DrawingFile]]:
    files = [drawing(path) for path in paths]
    return DrawingGroup(key=key, files=tuple(files)), files


def test_groups_that_share_a_source_are_one_lane_in_upload_order() -> None:
    """A building's sheets and its model are read one after another (the readers keep the parsed
    model, which is not safe to read from two threads); other groups each get their own lane."""
    model, sheet1, photo, sheet2 = (
        group("model", "m.ifc"),
        group("s1", "s1.pdf", "s1.svg"),
        group("photo", "p.jpg"),
        group("s2", "s2.pdf"),
    )
    sources = {"s1.pdf": [drawing("m.ifc")], "s2.pdf": [drawing("m.ifc")]}
    lanes = groups._lanes([model, sheet1, photo, sheet2], sources)  # pyright: ignore[reportPrivateUsage]
    assert [[found[0].key for found in lane] for lane in lanes] == [
        ["model", "s1", "s2"],
        ["photo"],
    ]
    # a later group that joins two lanes makes them one, still in upload order
    joined = groups._lanes(  # pyright: ignore[reportPrivateUsage]
        [sheet1, photo, group("both", "x.pdf")], {"x.pdf": [drawing("s1.pdf"), drawing("p.jpg")]}
    )
    assert [[found[0].key for found in lane] for lane in joined] == [["s1", "photo", "both"]]


class Response(io.BytesIO):
    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_carbon_calls_in_flight_never_pass_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """More callers than the cap: the cap's worth are inside at once, the rest wait their turn."""
    inside, most, go = [0], [0], threading.Event()
    changed = threading.Condition()

    def urlopen(request: Any, timeout: float) -> Response:
        with changed:
            inside[0] += 1
            most[0] = max(most[0], inside[0])
            changed.notify_all()
        assert go.wait(10)
        with changed:
            inside[0] -= 1
        return Response(b'{"usageMetadata": {}}')

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    client = carbon.CarbonClient("key", timeout_s=5)
    callers = [
        threading.Thread(target=client.generate, args=(b"", "p", {}, 10))
        for _ in range(carbon.CALLS_IN_FLIGHT + 3)
    ]
    for caller in callers:
        caller.start()
    with changed:
        assert changed.wait_for(lambda: inside[0] == carbon.CALLS_IN_FLIGHT, timeout=10)
        # the three others are held: none gets in while the cap's worth wait
        assert not changed.wait_for(lambda: inside[0] > carbon.CALLS_IN_FLIGHT, timeout=0.5)
    go.set()
    for caller in callers:
        caller.join(10)
    assert most[0] == carbon.CALLS_IN_FLIGHT

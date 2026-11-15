"""A sheet read while a model call failed is shown as it was read, but never reused: the next
upload of the same file asks again (a 429 or 503 must not become the file's reading for good)."""

from conftest import MakeService
from test_ingest_service import zipped

from app.core import cost
from app.core.drawing.model import Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles
from scripts.make_sample_archive import png_bytes, raster_plan

NO_SCALE = Scale(status="no_scale")
SCAN = png_bytes(raster_plan())


class Flaky:
    """A raster reader whose model calls fail while `down`: it counts the failure as the real
    adapters do (`cost.fail`) and reads nothing."""

    down = True
    reads = 0

    def __init__(self, files: DrawingFiles) -> None:
        self.files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        Flaky.reads += 1
        if Flaky.down:
            cost.fail()
            return Extracted(
                method="other", scale=NO_SCALE, notes=("carbon: the page call failed: HTTP 503",)
            )
        return Extracted(method="other", scale=NO_SCALE)


def test_a_read_that_met_a_model_failure_is_asked_again_by_the_next_upload(
    make_service: MakeService,
) -> None:
    Flaky.down, Flaky.reads = True, 0
    ingest = make_service(raster=Flaky)
    first = ingest.status(ingest.start("a.zip", zipped({"scan.png": SCAN})))
    assert [file.reused for file in first.files] == [False] and Flaky.reads == 1
    assert "1 model call got no answer" in first.files[0].reason
    Flaky.down = False  # the fault clears
    second = ingest.status(ingest.start("b.zip", zipped({"scan.png": SCAN})))
    assert [file.reused for file in second.files] == [False] and Flaky.reads == 2
    third = ingest.status(ingest.start("c.zip", zipped({"scan.png": SCAN})))
    assert [file.reused for file in third.files] == [True] and Flaky.reads == 2

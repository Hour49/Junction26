"""Which second counter measured a drawing, by its route (R2-qa4-1, R2-qa-1-2)."""

from app.api.views import reader_of
from app.composition import second_counter_of
from app.core.ingest.model import DrawingInfo


def test_the_ifc_counter_names_the_pdf_counter_for_every_file_that_is_no_model() -> None:
    names = {"second_counter": "ifc"}
    assert second_counter_of(names, "bim") == "ifc"
    assert [second_counter_of(names, route) for route in ("vector", "raster", "cad", None)] == [
        "pdf"
    ] * 4
    assert second_counter_of({"second_counter": "pdf"}, "vector") == "pdf"
    assert second_counter_of({"second_counter": "hello"}, "vector") == "hello"


def test_a_sheet_drawn_from_its_model_names_the_sheet_reader_first_and_the_model_second() -> None:
    """R3-qa-5-1: an IFC sheet's card read "IFC model read project.ifc (bim route), second count by
    IFC model", while the shown count is what the sheet draws (plan_drawing) and the model is the
    second count. The model asked about on its own stays "ifc" read from the .ifc."""
    names = {
        "bim": "ifc", "vector": "pdf", "second_counter": "ifc", "question_parser": "templates",
    }  # fmt: skip
    sheet = DrawingInfo(
        drawing_id="d1", project_id="p", path="bim/house_plan-01.pdf", kind="pdf",
        route="bim", source="bim/house.ifc",
    )  # fmt: skip
    model = sheet.model_copy(update={"path": "bim/house.ifc", "kind": "ifc"})
    read = reader_of(sheet, True, names)
    assert (read.extractor, read.source, read.second_counter) == (
        "ifc_sheet", "bim/house_plan-01.pdf", "ifc",
    )  # fmt: skip
    assert read.extractor != read.second_counter
    read = reader_of(model, False, names)
    assert (read.extractor, read.source, read.second_counter) == ("ifc", "bim/house.ifc", "none")
    vector = sheet.model_copy(update={"route": "vector", "source": "bim/house_plan-01.pdf"})
    assert reader_of(vector, True, names).extractor == "pdf"

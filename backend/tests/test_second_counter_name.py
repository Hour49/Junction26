"""Which second counter measured a drawing, by its route (R2-qa4-1, R2-qa-1-2)."""

from app.composition import second_counter_of


def test_the_ifc_counter_names_the_pdf_counter_for_every_file_that_is_no_model() -> None:
    names = {"second_counter": "ifc"}
    assert second_counter_of(names, "bim") == "ifc"
    assert [second_counter_of(names, route) for route in ("vector", "raster", "cad", None)] == [
        "pdf"
    ] * 4
    assert second_counter_of({"second_counter": "pdf"}, "vector") == "pdf"
    assert second_counter_of({"second_counter": "hello"}, "vector") == "hello"

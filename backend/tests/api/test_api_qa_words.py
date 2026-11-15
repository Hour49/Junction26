"""Words a user reads on the sample project (Tudor's QA batch 1, #430: B2 and B5)."""

from typing import Any

from fastapi.testclient import TestClient

from app.core.pipeline.ingest import no_sheet

INDOOR_AREA = "What is the net floor area of all indoor rooms?"


def sample(client: TestClient) -> dict[str, Any]:
    return client.get(client.post("/api/projects/sample").json()["url"]).json()


def test_a_lone_dxf_is_set_aside_with_a_reason_a_user_can_act_on(client: TestClient) -> None:
    """B2: a DXF with no PDF, PNG or JPEG beside it said "no page to place a drawing model on"."""
    skipped = {found["path"]: found["reason"] for found in sample(client)["skipped"]}
    assert skipped["cad/detail.dxf"] == (
        "this DXF file has no sheet to show on its own; upload it with the drawing's PDF or image"
    )


def test_a_building_model_with_nothing_read_says_so_in_plain_words() -> None:
    """B2: the same reason reached an IFC whose reader found nothing; it is not a missing page."""
    said = no_sheet("ifc")
    assert said == (
        "no spaces, walls, doors, windows or other building parts were read from this building "
        "model, and no sheet of it came with it"
    )
    assert "drawing model" not in said and "PDF, PNG or JPEG" not in said


def test_a_model_s_space_area_says_it_is_the_footprint_not_the_stated_net_area(
    client: TestClient,
) -> None:
    """B5: the number is each space's footprint in the model (what the dataset's room areas
    equal), so the rule must not call it the net floor area the model states: a file's own
    NetFloorArea can differ (1939.37 against a 2266.66 footprint on an office model)."""
    model = next(d for d in sample(client)["drawings"] if d["file"].endswith(".ifc"))
    reply = client.post(
        "/api/ask", json={"drawing_id": model["drawing_id"], "question": INDOOR_AREA}
    )
    assert reply.status_code == 200, reply.text
    answer = reply.json()
    assert (answer["answer"], answer["unit"]) == (48.0, "m2")  # the number is unchanged
    rule = answer["quantity"]["rule"]
    assert rule["id"] == "model-spaces"
    assert rule["text"] == (
        "the floor area of each of the storey's spaces as the footprint of its shape in the "
        "model, drawn on this sheet or not (not the net floor area the file may state, which can "
        "differ), else the area of the room the sheet draws it as; unknown when a space has "
        "neither"
    )

"""Building-code pre-checks over HTTP (decision 0009): the packs in GET /api/info, a drawing's
checks and a project's, with the TEST pack (tests/fixtures/rules/test.json) on the synthetic
swiss sheet (2 doors of 0.71 m at 1:100, no bedroom, no WC)."""

from pathlib import Path
from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from pdf_sheets import SheetPdf, rect
from test_vector_pdf import DOOR_GREY, swiss_room, swiss_window

from app.adapters.rule_packs import load_packs
from app.composition import build_ingest
from app.core.errors import InvalidInputError
from app.main import create_app
from app.settings import Settings

RULES = Path(__file__).parents[1] / "fixtures" / "rules"
SHIPPED = Settings.model_fields["rule_packs_dir"].default


def checks_sheet() -> bytes:
    """A swiss-style flat at 1:100 (1 m = 28.35 pt) for the Finnish pack: bedroom 4.01 (12 m2,
    a window, a 0.95 m door from the hall), bedroom 4.02 (6 m2, no window, a 0.71 m door from
    4.01), a living room (20 m2, a window, a 0.85 m door from the hall) and a dining nook typed
    living, which the pack skips by its label."""
    sheet = SheetPdf(600, 400)
    swiss_room(sheet, (60, 60, 173, 145), "Schlafzimmer", "4.01", "12.00 m²")
    swiss_room(sheet, (173, 60, 258, 117), "Schlafzimmer", "4.02", "6.00 m²")
    swiss_room(sheet, (258, 60, 400, 173), "Wohnen", "4.03", "20.00 m²")
    swiss_room(sheet, (60, 145, 258, 180), "Korridor", "4.04", "6.90 m²")
    swiss_room(sheet, (400, 60, 457, 145), "Essen", "4.05", "6.00 m²")
    swiss_window(sheet, (90, 56, 150, 62), degrees=0)
    swiss_window(sheet, (300, 56, 360, 62), degrees=0)
    for door in ((100, 141, 127, 149), (169, 80, 177, 100), (254, 149, 262, 173)):
        sheet.path(rect(*door), stroke=DOOR_GREY, width=0.37)
    sheet.text("Massstab 1:100 (A3)", 450, 380)
    return sheet.pdf()


@pytest.fixture
def checked(settings: Settings) -> TestClient:
    """The app with the TEST pack only."""
    settings = settings.model_copy(update={"rule_packs_dir": RULES})
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    return TestClient(create_app(settings, ingest))


@pytest.fixture
def project(checked: TestClient, plan_pdf: bytes) -> dict[str, Any]:
    return checked.get(f"/api/projects/{upload(checked, plan_pdf)}").json()


def get(client: TestClient, path: str, **params: str) -> dict[str, Any]:
    reply = client.get(path, params=params)
    assert reply.status_code == 200, reply.text
    return reply.json()


def test_info_lists_the_packs_for_the_country_picker(checked: TestClient) -> None:
    (pack,) = get(checked, "/api/info")["rule_packs"]
    assert {key: pack[key] for key in ("id", "country", "country_name", "name")} == {
        "id": "test",
        "country": "ZZ",
        "country_name": "Testland",
        "name": "Test pack",
    }
    assert pack["note"] == "A pre-check of a few rules, not a compliance certificate."
    area = pack["rules"][0]
    assert (area["op"], area["comparison"], area["comparison_text"]) == (
        "room_area",
        ">=",
        "at least",
    )
    assert area["clause"]["url"] == "https://example.org/test#1"


def test_info_serves_the_shipped_packs_by_default(client: TestClient) -> None:
    served = [pack["id"] for pack in get(client, "/api/info")["rule_packs"]]
    assert served == [pack.id for pack in load_packs(SHIPPED)]
    assert "fi" in served


def test_a_drawings_checks_in_its_project(checked: TestClient, project: dict[str, Any]) -> None:
    entry = project["drawings"][0]
    found = get(
        checked,
        f"/api/drawings/{entry['drawing_id']}/checks",
        pack="test",
        project=project["id"],
    )
    assert (found["file"], found["file_id"], found["pack"]) == ("plan.pdf", "f1", "test")
    assert found["note"].startswith("A pre-check")
    by_rule = {rule["rule_id"]: rule for rule in found["rules"]}
    assert {rule_id: rule["status"] for rule_id, rule in by_rule.items()} == {
        "test-bedroom-area": "not_applicable",
        "test-bedroom-window": "not_applicable",
        "test-door-width": "fail",
        "test-wc-count": "fail",
    }
    assert found["status"] == "fail"
    door = by_rule["test-door-width"]["results"][0]
    assert door["value"] == pytest.approx(0.706, abs=0.001)
    assert (door["quantity"], door["marks"][0]["quantity"], door["marks"][0]["mark_id"]) == (
        "door",
        "door",
        "m1",
    )
    # the mark is where the takeoff's door row draws its first mark
    takeoff = get(checked, f"/api/drawings/{entry['drawing_id']}/takeoff", project=project["id"])
    row = next(row for row in takeoff["quantities"] if row["key"] == "door")
    assert row["marks"][0]["id"] == "m1"
    assert row["marks"][0]["box"] == door["marks"][0]["box"]


def test_a_drawing_shared_by_two_projects_is_named_as_each_uploaded_it(
    checked: TestClient, plan_pdf: bytes
) -> None:
    first = checked.get(f"/api/projects/{upload(checked, plan_pdf, 'a/one.pdf')}").json()
    second = checked.get(f"/api/projects/{upload(checked, plan_pdf, 'b/two.pdf')}").json()
    drawing_id = first["drawings"][0]["drawing_id"]
    assert second["drawings"][0]["drawing_id"] == drawing_id  # one drawing, by content
    for project, name in ((first, "one.pdf"), (second, "two.pdf")):
        found = get(
            checked, f"/api/drawings/{drawing_id}/checks", pack="test", project=project["id"]
        )
        assert found["file"].endswith(name)
        listed = get(checked, f"/api/projects/{project['id']}/checks", pack="test")
        assert listed["drawings"][0]["file"].endswith(name)


def test_a_projects_checks_list_every_drawing(checked: TestClient, project: dict[str, Any]) -> None:
    found = get(checked, f"/api/projects/{project['id']}/checks", pack="test")
    assert (found["project_id"], found["pack"], found["status"]) == (project["id"], "test", "fail")
    (drawing,) = found["drawings"]
    assert (drawing["drawing_id"], drawing["file"], drawing["file_id"]) == (
        project["drawings"][0]["drawing_id"],
        "plan.pdf",
        "f1",
    )


def test_an_unknown_pack_is_404_with_its_own_code(
    checked: TestClient, project: dict[str, Any]
) -> None:
    drawing_id = project["drawings"][0]["drawing_id"]
    for path in (f"/api/drawings/{drawing_id}/checks", f"/api/projects/{project['id']}/checks"):
        reply = checked.get(path, params={"pack": "xx"})
        assert (reply.status_code, reply.json()) == (
            404,
            {"detail": "no rule pack 'xx'", "code": "unknown-pack"},
        )


def test_no_pack_is_a_validation_error(checked: TestClient, project: dict[str, Any]) -> None:
    reply = checked.get(f"/api/projects/{project['id']}/checks")
    assert (reply.status_code, reply.json()["code"]) == (422, "validation")


def test_an_unknown_drawing_or_project_is_404_not_found(
    checked: TestClient, project: dict[str, Any]
) -> None:
    for path in ("/api/drawings/0123456789abcdef/checks", "/api/projects/0123456789ab/checks"):
        reply = checked.get(path, params={"pack": "test"})
        assert (reply.status_code, reply.json()["code"]) == (404, "not-found")
    drawing_id = project["drawings"][0]["drawing_id"]
    reply = checked.get(
        f"/api/drawings/{drawing_id}/checks", params={"pack": "test", "project": "0123456789ab"}
    )
    assert (reply.status_code, reply.json()["code"]) == (404, "not-found")


def test_a_project_not_done_is_409(
    checked: TestClient, project: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest = checked.app.state.ingest  # type: ignore[attr-defined]
    running = ingest.status(project["id"]).model_copy(update={"state": "running"})
    monkeypatch.setattr(ingest, "status", lambda project_id: running)
    reply = checked.get(f"/api/projects/{project['id']}/checks", params={"pack": "test"})
    assert (reply.status_code, reply.json()["code"]) == (409, "not-allowed")


def test_a_pack_without_its_clause_stops_the_app(settings: Settings, tmp_path: Path) -> None:
    folder = tmp_path / "rules"
    folder.mkdir()
    text = (
        (RULES / "test.json").read_text().replace('"quote": "A test door', '"note": "A test door')
    )
    (folder / "test.json").write_text(text)
    with pytest.raises(InvalidInputError, match=r"clause\.quote"):
        create_app(settings.model_copy(update={"rule_packs_dir": folder}))

"""R4-B10 (Tudor's QA round 4, surveyor): a sign-off carries the value the client showed, so the
server never signs a value the person did not see."""

from typing import Any

from fastapi.testclient import TestClient

from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings


def door_row(found: dict[str, Any]) -> dict[str, Any]:
    return next(row for row in found["quantities"] if row["key"] == "door")


def test_a_sign_off_of_a_value_that_changed_is_refused_with_the_current_value(
    settings: Settings, plan_pdf: bytes
) -> None:
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    with TestClient(create_app(settings, ingest)) as client:
        started = client.post("/api/projects", params={"name": "plan.pdf"}, content=plan_pdf)
        (drawing,) = client.get(started.json()["url"]).json()["drawings"]
        drawing_id = drawing["drawing_id"]
        url = f"/api/drawings/{drawing_id}/signoff"
        shown = door_row(client.get(f"/api/drawings/{drawing_id}/takeoff").json())
        assert (shown["value"], shown["unit"]) == (2, "count")

        # Someone else settles 3 while the screen still shows 2
        edit = {"quantity": "door", "action": "settle", "value": 3}
        assert client.post(f"/api/drawings/{drawing_id}/review", json=edit).status_code == 200

        stale = client.post(url, json={"quantity": "door", "by": "Ana", "expected_value": 2})
        assert stale.status_code == 409, stale.text
        body = stale.json()
        assert body["code"] == "value-changed"
        assert body["detail"] == (
            "door count is now 3 count, not the 2 count shown: nothing was signed. Look at it "
            "again before you sign it off."
        )
        assert body["errors"] == [
            {"loc": ["body", "expected_value"], "current_value": 3, "unit": "count"}
        ]
        row = door_row(client.get(f"/api/drawings/{drawing_id}/takeoff").json())
        assert row["status"] != "signed" and row["signed"] is None

        unit = client.post(
            url, json={"quantity": "door", "by": "Ana", "expected_value": 3, "expected_unit": "m2"}
        )
        assert unit.status_code == 409 and unit.json()["code"] == "value-changed"

        seen = client.post(
            url,
            json={"quantity": "door", "by": "Ana", "expected_value": 3, "expected_unit": "count"},
        )
        assert seen.status_code == 200, seen.text
        assert door_row(seen.json())["status"] == "signed"

        # Without it, as today: the value in use is signed (Tudor's frontend sends it later)
        undo = client.post(url, json={"quantity": "door", "by": "Ana", "undo": True})
        assert undo.status_code == 200
        plain = client.post(url, json={"quantity": "door", "by": "Ana"})
        assert plain.status_code == 200 and door_row(plain.json())["status"] == "signed"

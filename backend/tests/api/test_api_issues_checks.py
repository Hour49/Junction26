"""Failed building-code checks in a project's issues (decision 0009 "Issues (0008)", story #139):
with `?pack=` each failed check is one `code_check_failed` issue, placed on its room or door;
without a pack there are none, and the project list's open count stays packless."""

import csv
import io
import zipfile
from pathlib import Path
from typing import Any

from conftest import upload
from fastapi.testclient import TestClient
from test_api_checks import RULES, checks_sheet, get

from app.composition import build_ingest
from app.core.checks.model import NOTE
from app.main import create_app
from app.settings import Settings


def flat(client: TestClient) -> dict[str, Any]:
    return client.get(f"/api/projects/{upload(client, checks_sheet(), 'flat-fi.pdf')}").json()


def failed(found: dict[str, Any]) -> list[dict[str, Any]]:
    return [issue for issue in found["issues"] if issue["kind"] == "code_check_failed"]


def serving(settings: Settings, rules: Path) -> TestClient:
    """The app with the packs in `rules` only."""
    settings = settings.model_copy(update={"rule_packs_dir": rules})
    return TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )


def test_each_failed_check_is_an_issue_on_its_room_or_door(client: TestClient) -> None:
    project = flat(client)
    drawing_id = project["drawings"][0]["drawing_id"]
    path = f"/api/projects/{project['id']}/issues"
    found = get(client, path, pack="fi")
    assert found["pack"] == "fi"
    checks = get(client, f"/api/drawings/{drawing_id}/checks", pack="fi", project=project["id"])
    results = [result for rule in checks["rules"] for result in rule["results"]]
    fails = [result for result in results if result["status"] == "fail"]
    assert any(result["status"] == "cannot_tell" for result in results)  # not an issue
    issues = failed(found)
    assert sorted(issue["check"] for issue in issues) == sorted(f"fi:{r['id']}" for r in fails)
    assert found["issues"][: len(issues)] == issues  # fails_rule comes first
    clauses = {rule["rule_id"]: rule["clause"]["ref"] for rule in checks["rules"]}
    for issue in issues:
        result = next(r for r in fails if f"fi:{r['id']}" == issue["check"])
        (subject,) = [mark for mark in result["marks"] if mark["role"] == "subject"]
        assert (issue["severity"], issue["state"], issue["drawing_id"]) == (
            "fails_rule",
            "open",
            drawing_id,
        )
        assert (issue["file"], issue["file_id"]) == ("flat-fi.pdf", "f1")
        assert (issue["page"], issue["box"], issue["polygon"], issue["mark_id"]) == (
            subject["page"],
            subject["box"],
            subject["polygon"],
            subject["mark_id"],
        )
        assert issue["quantity"] == result["quantity"]
        assert issue["why"] == f"{result['why']} ({clauses[result['rule_id']]})"
        assert issue["links"]["checks"] == (
            f"/api/drawings/{drawing_id}/checks?pack=fi&project={project['id']}"
        )
    # the checks link answers the same checks
    link = client.get(issues[0]["links"]["checks"]).json()
    assert link["rules"] == checks["rules"] and link["note"] == NOTE
    room = [issue["check"] for issue in issues if issue["mark_id"] == issues[0]["mark_id"]]
    assert len(room) == 2 and room == sorted(room)  # one room's fails: by their source ref
    assert get(client, path, pack="fi") == found  # ids and order stable between calls
    assert len({issue["id"] for issue in found["issues"]}) == len(found["issues"])


def test_without_a_pack_no_check_is_listed_nor_counted(client: TestClient) -> None:
    project = flat(client)
    path = f"/api/projects/{project['id']}/issues"
    plain = get(client, path)
    assert plain["pack"] is None and not failed(plain)
    with_pack = get(client, path, pack="fi")
    assert len(failed(with_pack)) == 3  # bedroom 4.02 area and window, the 0.71 m door
    others = [issue for issue in with_pack["issues"] if issue["kind"] != "code_check_failed"]
    assert others == plain["issues"]  # the rest of the list is unchanged
    (summary,) = [p for p in get(client, "/api/projects")["projects"] if p["id"] == project["id"]]
    assert summary["issues_open"] == sum(issue["state"] == "open" for issue in plain["issues"])


def test_a_failed_check_without_a_subject_has_no_place(settings: Settings, plan_pdf: bytes) -> None:
    checked = serving(settings, RULES)
    project = checked.get(f"/api/projects/{upload(checked, plan_pdf)}").json()
    found = get(checked, f"/api/projects/{project['id']}/issues", pack="test")
    doors = [issue for issue in failed(found) if issue["check"].startswith("test:test-door")]
    sheets = [issue for issue in failed(found) if issue["check"].startswith("test:test-wc")]
    assert len(doors) + len(sheets) == len(failed(found))
    assert sorted((door["page"], door["mark_id"], door["quantity"]) for door in doors) == [
        (1, "m1", "door"),
        (1, "m2", "door"),
    ]  # the sheet's two 0.71 m doors, each on its own mark
    (sheet,) = sheets  # the sheet's WC count: no room or door to open
    assert (sheet["page"], sheet["box"], sheet["mark_id"]) == (None, None, None)


def test_the_csv_and_zip_carry_the_failed_checks(client: TestClient) -> None:
    project = flat(client)
    issues = failed(get(client, f"/api/projects/{project['id']}/issues", pack="fi"))
    reply = client.get(f"/api/projects/{project['id']}/issues.csv", params={"pack": "fi"})
    assert reply.status_code == 200
    assert 'filename="flat-fi-issues-fi.csv"' in reply.headers["content-disposition"]
    rows = [row for row in csv.DictReader(io.StringIO(reply.text)) if row["check"]]
    assert [(row["id"], row["check"]) for row in rows] == [
        (issue["id"], issue["check"]) for issue in issues
    ]
    reply = client.get(f"/api/projects/{project['id']}/issues.zip", params={"pack": "fi"})
    with zipfile.ZipFile(io.BytesIO(reply.content)) as archive:
        assert "flat-fi-p1.png" in archive.namelist()  # the fails are drawn on their page


def test_one_rooms_fails_are_in_their_checks_order(settings: Settings, tmp_path: Path) -> None:
    """Two fails on one room (bedroom 4.02: area and window) sort by their source ref, whichever
    way the rule ids sort; each order is tried, so the issue ids' hashes can't decide it."""
    for area_id in ("test-bedroom-area", "zz-bedroom-area"):
        folder = tmp_path / area_id
        folder.mkdir()
        text = (RULES / "test.json").read_text().replace('"test-bedroom-area"', f'"{area_id}"')
        (folder / "test.json").write_text(text)
        client = serving(settings, folder)
        found = failed(get(client, f"/api/projects/{flat(client)['id']}/issues", pack="test"))
        room = [issue["check"] for issue in found if issue["check"].endswith(":r2")]  # 4.02
        assert len(room) == 2 and room == sorted(room), room

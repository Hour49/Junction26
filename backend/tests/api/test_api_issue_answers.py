"""Tudor's asks on board #14 (1, 3, 4): a person's answer to an issue, kept with the project;
each issue's answer chips and legend label; the open counts on the single-project GET."""

import csv
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from test_api_issues import listed, sample, waits_for_you
from test_review_core import BOX_A, disputed, quantity

from app.api import issue_answers, takeoff
from app.api.issue_answers import IssueAnswer
from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings


def window_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every drawing's takeoff: a window count two methods disagree on, no rule decides."""
    found = {"window": quantity("window", 2, "count", BOX_A, conflict=disputed(False))}
    monkeypatch.setattr(takeoff, "known_quantities", lambda drawing: found)


def answer(client: TestClient, project_id: str, issue_id: str, body: dict[str, Any]) -> Any:
    return client.post(f"/api/projects/{project_id}/issues/{issue_id}/answer", json=body)


def test_an_answer_is_kept_with_the_issue_across_a_restart_and_can_be_taken_back(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    window_conflict(monkeypatch)
    project_id = upload(client, plan_pdf)
    (issue,) = listed(client, project_id)
    assert issue["answer"] is None
    reply = answer(client, project_id, issue["id"], {"text": "3 is right", "by": "Ana"})
    assert reply.status_code == 200, reply.text
    said = reply.json()["answer"]
    assert (said["text"], said["by"]) == ("3 is right", "Ana") and said["at"].endswith("Z")
    assert reply.json() == {**issue, "answer": said}  # nothing else changes, state neither
    restarted = TestClient(create_app(settings, build_ingest(settings, settings.projects_dir)))
    assert listed(restarted, project_id) == [{**issue, "answer": said}]
    again = answer(client, project_id, issue["id"], {"text": "Check it on site", "by": "Bo"})
    assert again.json()["answer"]["text"] == "Check it on site"  # replaces the first
    undone = answer(client, project_id, issue["id"], {"undo": True})
    assert undone.status_code == 200 and undone.json()["answer"] is None
    assert listed(client, project_id) == [issue]
    assert answer(client, project_id, issue["id"], {"undo": True}).status_code == 200  # no-op


def test_the_csv_and_zip_carry_the_answer_who_gave_it_and_when(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    """QA fe-ui2: an exported issue list kept "open" and lost every answer given on the screen."""
    window_conflict(monkeypatch)
    project_id = upload(client, plan_pdf)
    (issue,) = listed(client, project_id)
    said = answer(client, project_id, issue["id"], {"text": "3 is right", "by": "Ana"}).json()
    reply = client.get(f"/api/projects/{project_id}/issues.csv")
    (row,) = csv.DictReader(io.StringIO(reply.content.decode("utf-8-sig")))
    assert (row["answer"], row["answered_by"], row["answered_at"]) == (
        "3 is right", "Ana", said["answer"]["at"],
    )  # fmt: skip
    bundle = client.get(f"/api/projects/{project_id}/issues.zip").content
    zipped = zipfile.ZipFile(io.BytesIO(bundle))
    (row,) = csv.DictReader(io.StringIO(zipped.read("issues.csv").decode("utf-8-sig")))
    assert (row["n"], row["answer"], row["answered_by"]) == ("1", "3 is right", "Ana")
    answer(client, project_id, issue["id"], {"undo": True})
    (row,) = csv.DictReader(io.StringIO(client.get(f"/api/projects/{project_id}/issues.csv").text))
    assert row["answer"] == row["answered_by"] == row["answered_at"] == ""


def test_an_answer_to_an_unknown_issue_or_project_is_404_and_a_bad_body_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    window_conflict(monkeypatch)
    project_id = upload(client, plan_pdf)
    (issue,) = listed(client, project_id)
    said = {"text": "fine", "by": "Ana"}
    assert answer(client, project_id, "conflict-000000000000", said).status_code == 404
    assert answer(client, "0123456789ab", issue["id"], said).status_code == 404
    for body in (
        {"text": "fine"},
        {"by": "Ana"},
        {"text": "", "by": "Ana"},
        {"undo": True, **said},
    ):
        assert answer(client, project_id, issue["id"], body).status_code == 422, body
    assert listed(client, project_id) == [issue]


def test_a_code_check_issue_is_answered_with_its_pack(client: TestClient) -> None:
    project = sample(client)
    url = f"/api/projects/{project['id']}/issues"
    packs = client.get("/api/info").json()["rule_packs"]
    pack = packs[0]["id"]
    checked = client.get(url, params={"pack": pack}).json()["issues"]
    failed = next(issue for issue in checked if issue["kind"] == "code_check_failed")
    said = {"text": "Accepted as drawn", "by": "Ana"}
    assert answer(client, project["id"], failed["id"], said).status_code == 404  # no pack
    reply = client.post(f"{url}/{failed['id']}/answer", params={"pack": pack}, json=said)
    assert reply.status_code == 200 and reply.json()["answer"]["text"] == "Accepted as drawn"


def test_each_issue_has_a_label_and_answer_chips_that_restate_no_value(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    window_conflict(monkeypatch)
    (issue,) = listed(client, upload(client, plan_pdf))
    assert issue["label"] == "Window count"  # the takeoff row's label
    assert issue["suggestions"] == ["Check it on site"]  # not "2 is right" (board #14)


def test_the_sample_issues_get_chips_and_a_label_by_kind(client: TestClient) -> None:
    found = {issue["kind"]: issue for issue in listed(client, sample(client)["id"])}
    room = found["conflict"]
    assert room["label"] == "Area of room (name Küche · 1.01)"
    assert room["suggestions"] == ["Check it on site"]
    assert (found["set_aside"]["label"], found["set_aside"]["suggestions"]) == (
        "Set aside",
        ["Not needed", "I'll send a readable copy"],
    )
    assert found["reading_flag"]["label"] == "How it was read"


def test_the_project_get_has_the_lists_open_counts_as_the_client_counts_them(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    window_conflict(monkeypatch)
    project = sample(client)
    open_ones = [issue for issue in listed(client, project["id"]) if issue["state"] == "open"]
    to_answer = [issue for issue in open_ones if waits_for_you(issue)]
    conflicts = [i for i in open_ones if i["kind"] == "conflict" and i["severity"] != "note"]
    counts = ("conflicts_open", "issues_open", "issues_to_answer")
    (summary,) = client.get("/api/projects").json()["projects"]
    assert [project[key] for key in counts] == [summary[key] for key in counts]
    assert [project[key] for key in counts] == [len(conflicts), len(open_ones), len(to_answer)]
    assert conflicts  # open conflicts nobody looked at: on Ingest, not to answer on Documents


def test_an_open_conflict_no_model_looked_at_is_not_counted_to_answer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, plan_pdf: bytes
) -> None:
    """QA R3-G1: the badge said "1 issue in Documents needs you" while Documents (which lists no
    conflict without `resolved`, DOC-3) said "Nothing needs your answer"."""
    window_conflict(monkeypatch)
    project_id = upload(client, plan_pdf)
    (issue,) = listed(client, project_id)
    assert (issue["kind"], issue["severity"], issue["state"]) == (
        "conflict",
        "needs_person",
        "open",
    )
    assert "resolved" not in issue and not waits_for_you(issue)
    counts = ("conflicts_open", "issues_open", "issues_to_answer")
    (summary,) = client.get("/api/projects").json()["projects"]
    project = client.get(f"/api/projects/{project_id}").json()
    assert [project[key] for key in counts] == [summary[key] for key in counts] == [1, 1, 0]


def test_a_running_project_has_no_counts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = sample(client)
    ingest = client.app.state.ingest  # type: ignore[attr-defined]
    running = ingest.status(project["id"]).model_copy(update={"state": "running"})
    monkeypatch.setattr(ingest, "status", lambda project_id: running)
    found = client.get(f"/api/projects/{project['id']}").json()
    assert (found["conflicts_open"], found["issues_open"], found["issues_to_answer"]) == (
        None,
        None,
        None,
    )


def test_the_answers_file_is_replaced_whole_under_the_lock_so_a_crash_keeps_the_last_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = IssueAnswer(text="fine", by="Ana", at="2026-11-14T08:00:00Z")
    issue_answers.save(tmp_path, "p1", "conflict-a", first)
    held: list[bool] = []

    def crash(source: Any, target: Any) -> None:  # the process dies before the rename
        held.append(issue_answers._lock.locked())  # pyright: ignore[reportPrivateUsage]
        raise OSError("disk gone")

    monkeypatch.setattr(issue_answers.os, "replace", crash)
    second = IssueAnswer(text="not fine", by="Bo", at="2026-11-14T08:01:00Z")
    with pytest.raises(OSError):
        issue_answers.save(tmp_path, "p1", "conflict-b", second)
    assert held == [True]  # written while no other answer can be
    assert issue_answers.answers(tmp_path, "p1") == {"conflict-a": first}  # never half a file
    monkeypatch.undo()
    issue_answers.save(tmp_path, "p1", "conflict-b", second)  # the leftover part is overwritten
    assert issue_answers.answers(tmp_path, "p1") == {"conflict-a": first, "conflict-b": second}


def test_answers_saved_at_once_from_many_threads_are_all_kept(tmp_path: Path) -> None:
    said = IssueAnswer(text="fine", by="Ana", at="2026-11-14T08:00:00Z")
    ids = [f"conflict-{n:02d}" for n in range(40)]
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda issue: issue_answers.save(tmp_path, "p1", issue, said), ids))
    assert sorted(issue_answers.answers(tmp_path, "p1")) == ids

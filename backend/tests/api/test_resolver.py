"""RESOLVER: a model picks a value for a conflict no rule decides,
or checks an answer CHECK_POLICY does not certify. A fake resolver stands in for the model here.
With the setting off nothing changes; a pick is the value in use until a person settles or signs
it, never certified; one call per conflict, asked again only when the conflict changes."""

from collections.abc import Callable
from typing import Any

import pytest
from conftest import plan_png, raster_arm, upload
from fastapi.testclient import TestClient
from test_api_check import gate, policy
from test_review_core import AT, BOX_A, BOX_B, DRAWING, disputed, quantity

from app import composition
from app.api import takeoff as takeoff_api
from app.composition import build_ingest
from app.core.pipeline.model import Quantity, QuantityConflict, ValueMark
from app.core.review import ask as review_ask
from app.core.review import conflict_card
from app.core.review.model import (
    Edit,
    Resolved,
    ResolveRequest,
    ResolverUnavailable,
    ReviewState,
    Row,
)
from app.core.review.resolve import conflict_request, resolve_conflicts
from app.core.review.review import apply, reset, row, sign
from app.main import create_app
from app.settings import Settings
from scripts.make_sample_archive import sample_files

BY = "fake:resolver"
KEY = "area:room|name=1.01"  # flat-b's room 1.01: 22.40 m2 by outline, 30 m2 printed


def reply(value: float | None, reason: str = "the doors have leaves") -> Resolved:
    verdict = "cannot_tell" if value is None else "picked"
    return Resolved(verdict=verdict, value=value, reason=reason, by=BY, at=AT)


class Fake:
    """Answers every request with `answer` and records what it was asked."""

    def __init__(self, answer: Resolved | ResolverUnavailable) -> None:
        self.answer = answer
        self.asked: list[ResolveRequest] = []

    def resolve(
        self, request: ResolveRequest, page: Callable[[int, int], bytes]
    ) -> Resolved | ResolverUnavailable:
        self.asked.append(request)
        return self.answer


NO_EDITS = ReviewState()


def no_page(page: int, width: int) -> bytes:  # the fakes never look at a page
    return b""


def doors(state: ReviewState = NO_EDITS, resolved: bool = False) -> Row:
    """2 doors by the sheet, 3 by the model; no rule decides unless `resolved`."""
    found = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=resolved))
    return row(found, DRAWING, state, {})


def door_quantity() -> Quantity:
    return quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=False))


def picked(value: float | None) -> ReviewState:
    return ReviewState(resolved={"door": reply(value).model_copy(update={"of": (2, 3)})})


# The review: a pick is the value in use, never a person's


def test_a_pick_is_the_value_in_use_and_no_person_has_to_choose() -> None:
    shown = doors(picked(3))
    assert (shown.value, shown.status, shown.needs_person) == (3, "conflict", False)
    assert shown.resolved is not None and shown.resolved.by == BY
    assert shown.settled is None and shown.signed is None  # no person's word
    assert "A model (fake:resolver) checked the drawing and picked 3" in conflict_card.why(shown)
    assert conflict_card.why(shown).endswith("You can still choose another value.")


def test_cannot_tell_leaves_the_conflict_to_a_person_and_says_why() -> None:
    shown = doors(picked(None))
    assert (shown.value, shown.status, shown.needs_person) == (2, "conflict", True)
    assert conflict_card.why(shown).endswith(
        "a model (fake:resolver) could not tell: the doors have leaves."
    )


def test_without_a_reply_nothing_changes() -> None:
    assert doors() == doors(ReviewState())
    assert doors().resolved is None
    assert "resolved" not in doors().model_dump(mode="json")  # left out of the JSON when off


def test_a_pick_for_other_values_or_a_conflict_a_rule_decides_is_ignored() -> None:
    stale = ReviewState(resolved={"door": reply(3).model_copy(update={"of": (2, 4)})})
    assert (doors(stale).value, doors(stale).status, doors(stale).resolved) == (2, "conflict", None)
    ruled = doors(picked(3), resolved=True)
    assert (ruled.value, ruled.status, ruled.resolved) == (2, "conflict", None)


def test_a_person_s_settle_wins_and_unsettle_or_reset_bring_the_pick_back() -> None:
    found = door_quantity()
    settle = Edit(quantity="door", action="settle", value=2)
    settled = apply(picked(3), settle, found, DRAWING, AT)
    shown = row(found, DRAWING, settled, {})
    assert (shown.value, shown.status, shown.settled is not None) == (2, "edited", True)
    unsettled = apply(settled, Edit(quantity="door", action="unsettle"), found, DRAWING, AT)
    assert row(found, DRAWING, unsettled, {}).value == 3
    for undone in (reset(settled, "door"), reset(settled, None)):
        assert row(found, DRAWING, undone, {}).value == 3  # the pick is in use again


def test_a_person_can_sign_off_the_pick_and_it_is_theirs_then() -> None:
    signed = sign(picked(3), door_quantity(), DRAWING, "QA Cee", AT)
    shown = row(door_quantity(), DRAWING, signed, {})
    assert (shown.status, shown.value, shown.signed is not None) == ("signed", 3, True)


# The use case: what is asked, once


def test_the_request_holds_each_method_s_value_and_its_places() -> None:
    marks = (
        (ValueMark(page=1, box=BOX_A, label="door 1"),),
        (ValueMark(page=1, box=BOX_B, label="door 2"),),
    )
    conflict = disputed(resolved=False).model_copy(update={"value_marks": marks})
    found = row(
        quantity("door", 2, "count", BOX_A, BOX_B, conflict=conflict), DRAWING, ReviewState(), {}
    )
    request = conflict_request("d1", found)
    assert [c.value for c in request.candidates] == [2, 3]
    assert [s.box for s in request.spots] == [BOX_A, BOX_B]
    assert request.kind == "conflict" and request.question.endswith("2 or 3?")


def test_each_conflict_needing_a_person_is_asked_once() -> None:
    fake = Fake(reply(3))
    found, notes = resolve_conflicts("d1", [doors()], ReviewState(), fake, no_page)
    assert (list(found), found["door"].of, notes, len(fake.asked)) == (["door"], (2, 3), [], 1)
    again, _ = resolve_conflicts("d1", [doors(picked(3))], picked(3), fake, no_page)
    assert again == {} and len(fake.asked) == 1  # the pick is kept: no second call
    resolve_conflicts(
        "d1", [doors(resolved=True)], ReviewState(), fake, no_page
    )  # a rule decides it
    assert len(fake.asked) == 1


def test_a_pick_no_method_read_or_no_reply_is_kept_out_with_a_note() -> None:
    for answer, said in (
        (reply(7), "picked 7, which no method read"),
        (ResolverUnavailable(note="Gemini budget used up"), "Gemini budget used up"),
    ):
        found, notes = resolve_conflicts("d1", [doors()], ReviewState(), Fake(answer), no_page)
        assert found == {} and len(notes) == 1 and said in notes[0]


# The API


def with_resolver(monkeypatch: pytest.MonkeyPatch, fake: Fake | None) -> None:
    """RESOLVER on, with `fake` in place of the model (the Carbon adapter isn't built yet)."""
    monkeypatch.setattr(composition, "_resolver", lambda settings: fake)


def client_of(settings: Settings) -> TestClient:
    return TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )


@pytest.fixture
def undecided(monkeypatch: pytest.MonkeyPatch) -> None:
    """flat-b's room 1.01 with no rule deciding it, so it needs a person."""
    known = takeoff_api.known_quantities

    def without_rule(drawing: Any) -> dict[str, Quantity]:
        found = dict(known(drawing))
        for key, value in found.items():
            if value.conflict is not None:
                conflict = QuantityConflict.model_validate(
                    value.conflict.model_dump() | {"resolution": None}
                )
                found[key] = value.model_copy(update={"conflict": conflict})
        return found

    monkeypatch.setattr(takeoff_api, "known_quantities", without_rule)
    monkeypatch.setattr(review_ask, "known_quantities", without_rule)


def flat_b(client: TestClient) -> str:
    response = client.post(
        "/api/projects", params={"name": "flat-b.pdf"}, content=sample_files()["plans/flat-b.pdf"]
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def entry(client: TestClient, project_id: str) -> dict[str, Any]:
    review = client.get(f"/api/projects/{project_id}/review").json()
    return next(found for found in review["conflicts"] if found["quantity"] == KEY)


def test_off_resolve_is_409_and_no_field_appears(client: TestClient) -> None:
    project_id = flat_b(client)
    response = client.post(f"/api/projects/{project_id}/resolve")
    assert response.status_code == 409 and "RESOLVER is off" in response.json()["detail"]
    assert "resolved" not in entry(client, project_id)


def test_resolve_picks_a_conflict_once_and_a_get_never_asks(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    fake = Fake(ResolverUnavailable(note="timeout"))  # the run after ingest gets no reply
    with_resolver(monkeypatch, fake)
    client = client_of(settings)
    project_id = flat_b(client)
    assert entry(client, project_id)["needs_person"] is True and len(fake.asked) == 1
    fake.answer = reply(22.4, "the outline is drawn to scale")
    done = client.post(f"/api/projects/{project_id}/resolve")
    assert done.status_code == 200, done.text
    asked = len(fake.asked)
    assert asked >= 1 and done.json()["notes"] == []
    shown = entry(client, project_id)
    assert shown["value"] == pytest.approx(22.4, abs=0.005)  # the method's exact value
    assert (shown["needs_person"], shown["resolved"]["by"]) == (False, BY)
    assert "picked 22.40 m²" in shown["why"]
    assert client.post(f"/api/projects/{project_id}/resolve").status_code == 200
    entry(client, project_id)
    assert len(fake.asked) == asked  # kept with the review: not asked again, a GET never asks


def doors_asked(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, fake: Fake | None, threshold: float
) -> dict[str, Any]:
    """ "How many doors?" on the raster arm's plan under a check policy (test_api_check)."""
    with_resolver(monkeypatch, fake)
    root = settings.projects_dir.parent
    raster_arm(root / "arm", "plan.png")
    settings = settings.model_copy(
        update={
            "extractor_raster": "composite",
            "raster_components": "elements=dir:arm,plans=dir:arm,rooms=dir:arm",
            "check_policy": str(policy(root, threshold, threshold - 0.1)),
            "local_gates": str(gate(root)),
        }
    )
    client = client_of(settings)
    project = client.get(f"/api/projects/{upload(client, plan_png(), 'plan.png')}").json()
    ask = {"drawing_id": project["drawings"][0]["drawing_id"], "question": "How many doors?"}
    return client.post("/api/ask", json=ask).json()


def test_an_answer_that_asks_gets_the_model_s_check_beside_it_never_certified(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake(reply(3, "a third door hides behind the stair"))
    answer = doors_asked(settings, monkeypatch, fake, threshold=0.9)
    assert answer["check"] is not None and answer["line"]["sure"] is False
    assert answer["answer"] == 2  # the reader's value stays
    assert answer["level"]["level"] != "high"
    assert answer["resolved"]["value"] == 3 and "resolver_note" not in answer
    (request,) = fake.asked
    assert (request.kind, request.candidates[0].value, request.question) == (
        "answer",
        2,
        "How many doors?",
    )


def test_a_certified_answer_is_not_sent_and_no_reply_gives_a_note(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake(reply(3))
    certified = doors_asked(settings, monkeypatch, fake, threshold=0.7)
    assert certified["check"] is None and fake.asked == [] and "resolved" not in certified
    budget = Fake(ResolverUnavailable(note="Gemini budget used up"))
    answer = doors_asked(settings, monkeypatch, budget, threshold=0.9)
    assert answer["resolver_note"] == "Gemini budget used up" and "resolved" not in answer


def resolved_flat_b(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, answer: Resolved
) -> tuple[TestClient, str]:
    """flat-b with RESOLVER on (the fake answering `answer`), resolved once."""
    with_resolver(monkeypatch, Fake(answer))
    monkeypatch.setattr(settings, "resolver", "carbon")
    client = client_of(settings)
    project_id = flat_b(client)
    assert client.post(f"/api/projects/{project_id}/resolve").status_code == 200
    return client, project_id


def conflict_issue(client: TestClient, project_id: str) -> dict[str, Any]:
    issues = client.get(f"/api/projects/{project_id}/issues").json()["issues"]
    return next(
        found for found in issues if found["kind"] == "conflict" and found["quantity"] == KEY
    )


def test_a_picked_conflict_stays_listed_checked_by_the_model_and_needs_no_answer(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    client, project_id = resolved_flat_b(settings, monkeypatch, reply(22.4))
    issue = conflict_issue(client, project_id)
    assert (issue["state"], issue["severity"], issue["resolved"]["by"]) == ("open", "note", BY)
    assert f"no rule decides, a model picked 22.4 m² ({BY}): you can change it" in issue["why"]
    assert "a person must settle it" not in issue["why"]
    project = client.get(f"/api/projects/{project_id}").json()
    (summary,) = client.get("/api/projects").json()["projects"]
    for counts in (project, summary):
        assert (counts["conflicts_open"], counts["conflicts_picked"]) == (0, 1)
        assert counts["issues_to_answer"] == sum(
            found["severity"] != "note" and found["answer"] is None
            for found in client.get(f"/api/projects/{project_id}/issues").json()["issues"]
            if found["state"] == "open"
        )


def test_cannot_tell_keeps_the_conflict_open_and_to_answer(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    client, project_id = resolved_flat_b(settings, monkeypatch, reply(None, "the label is cut"))
    issue = conflict_issue(client, project_id)
    assert (issue["severity"], issue["resolved"]["verdict"]) == ("needs_person", "cannot_tell")
    assert "which could not tell" in issue["why"]
    project = client.get(f"/api/projects/{project_id}").json()
    assert (project["conflicts_open"], project["conflicts_picked"]) == (1, 0)


def test_off_no_pick_count_appears(client: TestClient) -> None:
    project_id = flat_b(client)
    project = client.get(f"/api/projects/{project_id}").json()
    (summary,) = client.get("/api/projects").json()["projects"]
    assert "conflicts_picked" not in project and "conflicts_picked" not in summary
    assert "resolved" not in conflict_issue(client, project_id)


def test_settle_unsettle_and_reset_answer_with_the_model_s_reply(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    client, project_id = resolved_flat_b(settings, monkeypatch, reply(22.4))
    drawing_id = entry(client, project_id)["drawing_id"]
    url = f"/api/drawings/{drawing_id}/review?project={project_id}"
    edits = (
        {"quantity": KEY, "action": "settle", "value": 30},
        {"quantity": KEY, "action": "unsettle"},
        {"quantity": KEY, "action": "settle", "value": 30},
        {"quantity": KEY, "action": "reset"},
        {"action": "reset"},
    )
    for edit in edits:
        response = client.post(url, json=edit)
        assert response.status_code == 200, response.text
        shown = next(found for found in response.json()["quantities"] if found["key"] == KEY)
        assert shown["resolved"]["by"] == BY, edit
        assert shown["value"] == pytest.approx(
            30 if edit["action"] == "settle" else 22.4, abs=0.005
        )
    assert entry(client, project_id)["resolved"]["value"] == pytest.approx(22.4, abs=0.005)


# codecheck's review of #252 (.agents/qa/r9/review-252.md)


def test_a_person_s_mark_edit_wins_over_the_pick_and_reset_brings_it_back() -> None:
    """M1: rejecting a mark on a picked row counts as before the pick; needs a person again."""
    found = door_quantity()
    reject = Edit(quantity="door", action="reject", mark="m1")
    edited = apply(picked(3), reject, found, DRAWING, AT)
    shown = row(found, DRAWING, edited, {})
    assert (shown.value, shown.needs_person) == (1, True)
    assert "picked 3 before the marks were edited" in conflict_card.why(shown)
    assert row(found, DRAWING, reset(edited, "door"), {}).value == 3


def test_cannot_tell_is_kept_and_not_asked_again() -> None:
    """S2: a stored cannot_tell is the reply: a second resolve asks nothing."""
    fake = Fake(reply(None))
    found, _ = resolve_conflicts("d1", [doors()], ReviewState(), fake, no_page)
    state = ReviewState(resolved=found)
    again, _ = resolve_conflicts("d1", [doors(state)], state, fake, no_page)
    assert (len(fake.asked), again, found["door"].verdict) == (1, {}, "cannot_tell")


def test_with_no_reply_the_stored_state_has_no_resolved_key() -> None:
    """S2: RESOLVER off leaves every stored review as it was before the PR."""
    assert "resolved" not in ReviewState().model_dump_json()
    assert "resolved" in picked(3).model_dump_json()


def test_asking_about_a_picked_conflict_shows_the_pick_and_makes_no_call(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    """S1: the answer's check is the stored pick, with its reason; the model is not asked."""
    root = settings.projects_dir.parent
    root.mkdir(parents=True, exist_ok=True)
    settings = settings.model_copy(update={"check_policy": str(policy(root, 0.9, 0.8))})
    fake = Fake(reply(22.4, "the outline is drawn to scale"))
    with_resolver(monkeypatch, fake)
    client = client_of(settings)
    project_id = flat_b(client)
    drawing_id = entry(client, project_id)["drawing_id"]
    ask = {"drawing_id": drawing_id, "question": "What is the area of room 1.01?"}
    before = client.post("/api/ask", json={**ask, "project_id": project_id}).json()
    assert before["check"] is not None
    assert [request.kind for request in fake.asked] == ["conflict"]  # both sides, as resolve
    assert client.post(f"/api/projects/{project_id}/resolve").status_code == 200
    asked = len(fake.asked)
    answer = client.post("/api/ask", json={**ask, "project_id": project_id}).json()
    assert answer["resolved"]["reason"] == "the outline is drawn to scale"
    assert answer["answer"] == pytest.approx(22.4, abs=0.005)
    assert len(fake.asked) == asked  # no call: the stored pick


def test_with_resolver_on_an_upload_is_resolved_when_its_ingest_is_done(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    """D: no POST needed; the explicit POST then asks nothing new."""
    fake = Fake(reply(22.4))
    with_resolver(monkeypatch, fake)
    client = client_of(settings)
    project_id = flat_b(client)  # ingested inline here, so resolved before the 202
    shown = entry(client, project_id)
    assert (shown["needs_person"], shown["resolved"]["by"]) == (False, BY)
    asked = len(fake.asked)
    assert asked >= 1
    assert client.post(f"/api/projects/{project_id}/resolve").json()["notes"] == []
    assert len(fake.asked) == asked


# codecheck's re-check at dccae51


def ask_open_conflict(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, answer: Resolved
) -> tuple[Fake, dict[str, Any]]:
    """flat-b's room 1.01 needing a person (the upload's resolve got no reply), then asked about
    under a check policy with the model answering `answer`."""
    root = settings.projects_dir.parent
    root.mkdir(parents=True, exist_ok=True)
    settings = settings.model_copy(update={"check_policy": str(policy(root, 0.9, 0.8))})
    fake = Fake(ResolverUnavailable(note="timeout"))
    with_resolver(monkeypatch, fake)
    client = client_of(settings)
    project_id = flat_b(client)
    shown = entry(client, project_id)
    assert shown["needs_person"] is True and "resolved" not in shown
    fake.answer = answer
    ask = {"drawing_id": shown["drawing_id"], "question": "What is the area of room 1.01?"}
    return fake, client.post("/api/ask", json={**ask, "project_id": project_id}).json()


def test_asking_about_an_open_conflict_sends_both_sides_and_keeps_only_a_method_s_value(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    """M3 (codecheck's p3) and B3: 25 is no method's value, so it is no reply, with a note."""
    fake, answer = ask_open_conflict(settings, monkeypatch, reply(25.0, "made up"))
    assert [request.kind for request in fake.asked] == ["conflict", "conflict"]
    assert [found.value for found in fake.asked[-1].candidates] == pytest.approx([22.401, 30.0])
    assert "resolved" not in answer
    assert answer["resolver_note"] == "the resolver picked 25.0, which no method read"


def test_asking_about_an_open_conflict_shows_a_method_s_value_as_it_was_read(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    _, answer = ask_open_conflict(settings, monkeypatch, reply(22.4))
    assert answer["resolved"]["value"] == 22.401 and "resolver_note" not in answer


def test_a_pick_a_mark_edit_overrules_is_not_counted_as_picked(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    """B5: once a person edits the marks, the conflict is open again, not picked."""
    client, project_id = resolved_flat_b(settings, monkeypatch, reply(22.4))
    shown = entry(client, project_id)
    marks = client.get(f"/api/drawings/{shown['drawing_id']}/takeoff?project={project_id}").json()
    room = next(found for found in marks["quantities"] if found["key"] == KEY)
    edit = {"quantity": KEY, "action": "reject", "mark": room["marks"][0]["id"]}
    url = f"/api/drawings/{shown['drawing_id']}/review?project={project_id}"
    assert client.post(url, json=edit).status_code == 200
    project = client.get(f"/api/projects/{project_id}").json()
    assert (project["conflicts_open"], project["conflicts_picked"]) == (1, 0)


def test_after_a_person_settles_the_issue_no_longer_gives_the_model_s_word(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, undecided: None
) -> None:
    """B7: a person's settle or sign-off is the word; the model's reply leaves the issue."""
    client, project_id = resolved_flat_b(settings, monkeypatch, reply(22.4))
    drawing_id = entry(client, project_id)["drawing_id"]
    url = f"/api/drawings/{drawing_id}"
    settle = {"quantity": KEY, "action": "settle", "value": 30}
    assert client.post(f"{url}/review?project={project_id}", json=settle).status_code == 200
    issue = conflict_issue(client, project_id)
    assert "resolved" not in issue and "model" not in issue["why"]
    sign = {"quantity": KEY, "by": "QA Cee"}
    assert client.post(f"{url}/signoff?project={project_id}", json=sign).status_code == 200
    issue = conflict_issue(client, project_id)
    assert "resolved" not in issue and "model" not in issue["why"]

"""The Gemini spend guard (GEMINI_BUDGET_USD, GEMINI_BUDGET_USD_PER_HOUR; app/core/spend.py): every
Gemini client stops calling once the shared ledger is spent, across threads; the hourly limit
rolls; a refused call takes each step's "not available" path; unset changes nothing. No network:
fake transports and a stubbed urlopen."""

import io
import json
import threading
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from test_triage_describer import NOT_DRAWING, form
from test_triage_describer import answer as describer_answer

from app.adapters.decisions.client import DecisionsClient, DecisionsError
from app.adapters.decisions_kind import KindReader, KindUnavailable
from app.adapters.decisions_kind.probe import KindProbe
from app.adapters.raster_ocr.gemini import GeminiClient, GeminiError, GeminiRoomExtractor
from app.adapters.triage.gemini_describer import GeminiDescribeClient, GeminiDescriber
from app.adapters.triage.sheet_kind import SheetKindClassifier
from app.composition import (  # pyright: ignore[reportPrivateUsage]
    _gemini_rooms,
    _probe,
    _spend_guard,
    _triage,
    build_ingest,
    decisions_reader,
    spend_guard,
)
from app.core.ingest.model import Unavailable
from app.core.spend import SpendGuard
from app.main import create_app
from app.settings import Settings

KEY = "test-key-not-real"
CENT = {"answers": {}, "usage": {"total_input_tokens": 100_000}}  # 100k x 0.10 USD/M = 0.01 USD
# 20k prompt tokens x 1.50 USD/M = 0.03 USD; the room reader's reply text: no rooms
GEMINI = {
    "candidates": [{"content": {"parts": [{"text": "[]"}]}}],
    "usageMetadata": {"promptTokenCount": 20_000},
}


@pytest.fixture(autouse=True)
def fresh_ledgers() -> None:
    _spend_guard.cache_clear()  # one ledger per process: each test starts with its own


class CentTransport:
    """The Decisions API, faked: every call is a paid reply of 0.01 USD. Counts calls."""

    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, body: bytes, key: str, timeout: float) -> tuple[int, bytes]:
        with self._lock:
            self.calls += 1
        return 200, json.dumps(CENT).encode()


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 48), "white").save(out, format="PNG")
    return out.getvalue()


def decisions(guard: SpendGuard | None, transport: CentTransport) -> DecisionsClient:
    return DecisionsClient(KEY, 5.0, transport=transport, budget=guard)


def stub_gemini(monkeypatch: pytest.MonkeyPatch, reply: dict[str, Any]) -> list[int]:
    """generateContent, faked: each call returns `reply`. The list counts the calls."""
    calls: list[int] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        calls.append(1)
        return io.BytesIO(json.dumps(reply).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return calls


def test_three_cent_calls_spend_a_three_cent_budget_and_the_fourth_is_never_sent() -> None:
    transport = CentTransport()
    client = decisions(SpendGuard(0.03), transport)
    for _ in range(3):
        client.decide({})
    with pytest.raises(DecisionsError, match=r"Gemini budget used up \(0.03 USD spent, "):
        client.decide({})
    assert transport.calls == 3


def test_the_budget_stops_calls_across_threads() -> None:
    """Eight threads call until refused. A call that passed the check before the budget was spent
    still finishes, so at most 2 charged + 1 + 7 others in flight = 10 calls; never more."""
    guard, transport = SpendGuard(0.03), CentTransport()
    client = decisions(guard, transport)
    start = threading.Barrier(8)

    def run() -> None:
        start.wait()
        for _ in range(100):  # a broken guard fails the bound below instead of hanging
            try:
                client.decide({})
            except DecisionsError:
                return

    threads = [threading.Thread(target=run) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert 3 <= transport.calls <= 10
    assert guard.spent_usd == pytest.approx(transport.calls * 0.01)
    assert guard.exhausted() is not None


def test_charges_from_many_threads_add_up_exactly() -> None:
    guard = SpendGuard(None)

    def charge() -> None:
        for _ in range(500):
            guard.charge(0.01)

    threads = [threading.Thread(target=charge) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert guard.spent_usd == 40.0  # whole micro-dollars: no lost update, no float drift


def test_the_hourly_limit_rolls_with_the_last_hour() -> None:
    now = [0.0]
    guard = SpendGuard(None, per_hour_usd=0.02, clock=lambda: now[0])
    guard.charge(0.01)
    now[0] = 100.0
    guard.charge(0.01)
    now[0] = 200.0
    assert guard.exhausted() == (
        "Gemini hourly budget used up (0.02 USD in the last hour, GEMINI_BUDGET_USD_PER_HOUR=0.02)"
    )
    now[0] = 3600.0  # the charge at 0 s is an hour old
    assert guard.exhausted() is None
    guard.charge(0.01)
    assert guard.exhausted() is not None
    now[0] = 3700.0  # the charge at 100 s left the window too
    assert guard.exhausted() is None
    assert guard.spent_usd == pytest.approx(0.03)  # the total is never forgotten


def test_both_gemini_generate_content_clients_refuse_without_sending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_gemini(monkeypatch, GEMINI)
    rooms = GeminiClient(KEY, "gemini-3.5-flash", 5.0, budget=SpendGuard(0.03))
    rooms.ask(png(), "rooms")
    with pytest.raises(GeminiError, match="Gemini budget used up"):
        rooms.ask(png(), "rooms")
    describer = GeminiDescribeClient(KEY, 5.0, budget=SpendGuard(0.03))
    describer.ask(b"jpeg")
    with pytest.raises(GeminiError, match="Gemini budget used up"):
        describer.ask(b"jpeg")
    assert len(calls) == 2


def test_a_refused_call_takes_each_steps_not_available_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spent = SpendGuard(0.01)
    spent.charge(0.01)
    calls = stub_gemini(monkeypatch, describer_answer(form()))
    kind = KindReader(decisions(spent, CentTransport()), tmp_path / "kind").read(png())
    assert isinstance(kind, KindUnavailable) and "Gemini budget used up" in kind.note
    client = GeminiDescribeClient(KEY, 5.0, budget=spent)
    described = GeminiDescriber(client, tmp_path / "describer").describe(png(), NOT_DRAWING)
    assert isinstance(described, Unavailable) and "Gemini budget used up" in described.note
    assert calls == []
    assert not any((tmp_path / "describer").glob("*.json"))  # nothing half-written is cached


def test_unset_is_no_limit_and_info_leaves_the_field_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    settings = Settings(projects_dir=tmp_path / "projects")
    assert not spend_guard(settings).limited and spend_guard(settings).exhausted() is None
    transport = CentTransport()
    client = decisions(None, transport)
    for _ in range(50):
        client.decide({})
    assert transport.calls == 50
    app = create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    assert "gemini" not in TestClient(app).get("/api/info").json()


def test_info_says_when_the_budget_is_used_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(projects_dir=tmp_path / "projects", gemini_budget_usd=0.05)
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    assert client.get("/api/info").json()["gemini"] == "ok"
    spend_guard(settings).charge(0.05)
    assert client.get("/api/info").json()["gemini"] == "budget_exhausted"


def test_every_gemini_client_the_app_builds_charges_the_one_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Gemini client built without the ledger is the bug this guard exists to prevent."""
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        gemini_api_key=KEY,  # pyright: ignore[reportArgumentType]
        gemini_budget_usd=1.0,
        gemini_budget_usd_per_hour=0.5,
        decisions_kind=True,
        triage_classifier="rules",
        triage_describer="gemini",
        triage_describer_cache_dir=tmp_path / "describer",
        sheet_kind="carbon",
    )
    guard = spend_guard(settings)
    assert spend_guard(settings) is guard
    counts = decisions_reader(settings)._decider  # pyright: ignore[reportPrivateUsage]
    probe = _probe(settings)
    assert isinstance(probe, KindProbe)
    kind = probe._reader._decider  # pyright: ignore[reportPrivateUsage]
    rooms = _gemini_rooms(settings, Files())
    assert isinstance(rooms, GeminiRoomExtractor)
    room_client = rooms._gemini._model  # pyright: ignore[reportPrivateUsage]
    steps = _triage(settings)
    assert steps is not None and isinstance(steps.describer, GeminiDescriber)
    describe_client = steps.describer._model  # pyright: ignore[reportPrivateUsage]
    assert isinstance(steps.classifier, SheetKindClassifier)
    sheet_client = steps.classifier._reader._model  # pyright: ignore[reportPrivateUsage]
    for client in (counts, kind, room_client, describe_client, sheet_client):
        assert client._budget is guard  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]


class Files:
    def read(self, path: str) -> bytes:
        return b""


def test_an_empty_limit_is_unset_and_a_negative_one_fails_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_BUDGET_USD", "")
    monkeypatch.setenv("GEMINI_BUDGET_USD_PER_HOUR", "2.5")
    settings = Settings()
    assert (settings.gemini_budget_usd, settings.gemini_budget_usd_per_hour) == (None, 2.5)
    monkeypatch.setenv("GEMINI_BUDGET_USD", "-1")
    with pytest.raises(ValidationError, match="gemini_budget_usd"):
        Settings()


@pytest.mark.parametrize("name", ["GEMINI_BUDGET_USD", "GEMINI_BUDGET_USD_PER_HOUR"])
def test_a_zero_limit_is_the_kill_switch_no_gemini_call_from_the_first(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deploy runbook's kill switch: restart with the limit at 0 and nothing is sent."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(name, "0")
    settings = Settings(projects_dir=tmp_path / "projects")
    app = create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    assert TestClient(app).get("/api/info").json()["gemini"] == "budget_exhausted"
    transport = CentTransport()
    with pytest.raises(DecisionsError, match="budget used up"):
        decisions(spend_guard(settings), transport).decide({})
    assert transport.calls == 0


def test_a_plain_caller_shares_the_ledger_through_its_public_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Code that is not one of our Gemini adapters (an agent chat on Gemini's OpenAI-compatible
    endpoint) asks, charges and reads the same ledger; its spend stops our clients too."""
    monkeypatch.chdir(tmp_path)
    settings = Settings(gemini_budget_usd=0.10)
    guard = spend_guard(settings)
    assert guard.exhausted() is None and guard.remaining() == pytest.approx(0.10)
    for _ in range(3):  # the agent: ask, call, charge the reply's cost
        assert guard.exhausted() is None
        guard.charge(0.03, "agent chat")
    assert guard.remaining() == pytest.approx(0.01)
    transport = CentTransport()
    ours = DecisionsClient(KEY, 5.0, transport=transport, budget=spend_guard(settings))
    ours.decide({})  # the last cent
    assert guard.remaining() == 0.0
    assert guard.spent_by() == pytest.approx({"agent chat": 0.09, "decisions": 0.01})
    why = guard.exhausted()
    assert why is not None and why.startswith("Gemini budget used up")
    with pytest.raises(DecisionsError, match="Gemini budget used up"):
        ours.decide({})
    assert transport.calls == 1


def test_remaining_is_the_nearer_limit_and_none_without_one() -> None:
    assert SpendGuard().remaining() is None
    guard = SpendGuard(1.0, per_hour_usd=0.25, clock=lambda: 0.0)
    guard.charge(0.2)
    assert guard.remaining() == pytest.approx(0.05)  # the hourly limit is nearer

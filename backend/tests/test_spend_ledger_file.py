"""SPEND_LEDGER_PATH (brief r8 BT): each auto-deploy restarts the app, and an in-memory ledger
restarted the 25 USD / 6 USD-per-hour caps with it. In a file, a new process sees the old total,
the hourly window survives a restart, and two processes charging at once lose no charge."""

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.adapters.spend_file import FileSpend
from app.composition import _spend_guard, spend_guard  # pyright: ignore[reportPrivateUsage]
from app.core.spend import SpendGuard
from app.settings import Settings

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def fresh_guards() -> Iterator[None]:
    _spend_guard.cache_clear()
    yield
    _spend_guard.cache_clear()


def in_new_process(code: str) -> None:
    subprocess.run([sys.executable, "-c", code], cwd=BACKEND, check=True, timeout=60)


def charge_in_new_process(ledger: Path, usd: float, times: int = 1) -> str:
    return (
        "from pathlib import Path\n"
        "from app.composition import spend_guard\n"
        "from app.settings import Settings\n"
        f"guard = spend_guard(Settings(spend_ledger_path=Path({str(ledger)!r}), "
        "gemini_budget_usd=25.0))\n"
        f"for _ in range({times}):\n"
        f"    guard.charge({usd!r}, 'carbon reader')\n"
    )


def test_a_new_process_sees_the_old_total(tmp_path: Path) -> None:
    ledger = tmp_path / "spend.json"
    in_new_process(charge_in_new_process(ledger, 0.75))
    settings = Settings(spend_ledger_path=ledger, gemini_budget_usd=0.75)
    guard = spend_guard(settings)
    assert guard.spent_usd == 0.75 and guard.spent_by() == {"carbon reader": 0.75}
    assert guard.exhausted() == "Gemini budget used up (0.75 USD spent, GEMINI_BUDGET_USD=0.75)"
    assert guard.remaining() == 0


def test_unset_keeps_the_ledger_in_memory(tmp_path: Path) -> None:
    guard = spend_guard(Settings(gemini_budget_usd=1.0))
    guard.charge(0.5)
    _spend_guard.cache_clear()  # a restart
    assert spend_guard(Settings(gemini_budget_usd=1.0)).spent_usd == 0
    assert not list(tmp_path.iterdir())


def test_an_empty_setting_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """As .env.example has it."""
    monkeypatch.setenv("SPEND_LEDGER_PATH", "")
    assert Settings().spend_ledger_path is None


def test_the_hourly_window_survives_a_restart(tmp_path: Path) -> None:
    ledger = tmp_path / "spend.json"
    now = [1_000.0]
    SpendGuard(None, 0.02, clock=lambda: now[0], store=FileSpend(ledger)).charge(0.02)
    now[0] += 1_800  # half an hour later, a new process on the same file
    restarted = SpendGuard(None, 0.02, clock=lambda: now[0], store=FileSpend(ledger))
    assert restarted.exhausted() == (
        "Gemini hourly budget used up (0.02 USD in the last hour, GEMINI_BUDGET_USD_PER_HOUR=0.02)"
    )
    now[0] += 1_800  # an hour after the charge: it no longer counts
    assert restarted.exhausted() is None and restarted.remaining() == 0.02
    restarted.charge(0.01)  # and a charge drops it from the file
    assert json.loads(ledger.read_text())["recent"] == [[now[0], 10_000]]
    assert restarted.spent_usd == 0.03


def test_two_processes_charging_at_once_lose_no_charge(tmp_path: Path) -> None:
    ledger = tmp_path / "spend.json"
    code = charge_in_new_process(ledger, 0.001, times=200)
    running = [subprocess.Popen([sys.executable, "-c", code], cwd=BACKEND) for _ in range(2)]
    assert [process.wait(timeout=60) for process in running] == [0, 0]
    assert FileSpend(ledger).read().total == 400 * 1_000


def test_an_unreadable_ledger_is_an_error_not_0(tmp_path: Path) -> None:
    """A ledger that forgot its spend would lift the caps."""
    ledger = tmp_path / "spend.json"
    ledger.write_text(json.dumps({"total": 1}))
    guard = SpendGuard(1.0, store=FileSpend(ledger))
    with pytest.raises(ValueError, match="spend_ledger_v1"):
        guard.exhausted()

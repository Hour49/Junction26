"""tools/qa-env.sh refuses bad input before it exports or starts anything. (Starting a commit's
backend is checked by hand: it needs the models, uv and a port; see the script's header.)"""

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).with_name("qa-env.sh")
ROOT = SCRIPT.parent.parent


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=30, check=False
    )


def test_no_arguments_print_the_usage() -> None:
    found = run()
    assert found.returncode == 1
    assert "usage: tools/qa-env.sh <commit> [port] [--frontend] | stop <commit>" in found.stderr


def test_an_unknown_commit_is_refused() -> None:
    found = run("no-such-commit-0000", "8799")
    assert (found.returncode, found.stderr.strip()) == (1, "qa-env: no commit no-such-commit-0000")


def test_the_port_must_be_a_number() -> None:
    found = run("HEAD", "eighty")
    assert (found.returncode, found.stderr.strip()) == (1, "qa-env: port must be a number: eighty")


def test_stop_needs_an_environment_it_made() -> None:
    first = subprocess.run(
        ["git", "-C", str(ROOT), "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.split()[0]  # fmt: skip
    found = run("stop", first)  # the first commit: never exported as a QA environment
    assert found.returncode == 1
    assert "qa-env: no environment" in found.stderr
    assert run("stop").returncode == 1  # no commit: usage


def test_the_demo_config_reads_the_sheet_kind_signal() -> None:
    """R1-1-2: without DECISIONS_KIND only camera EXIF makes an image a photo, so 27 of 30 real
    phone photos (EXIF stripped) went unrectified. The demo config turns the signal on."""
    found = run("config")
    assert found.returncode == 0, found.stderr
    config = found.stdout.split()
    assert "DECISIONS_KIND=true" in config
    assert "RECTIFIER=r3" in config and "DECISIONS_CONFIDENCE=true" in config
    assert not any(line.startswith("GEMINI_API_KEY") for line in config)  # never the key


def test_the_demo_config_estimates_raster_areas() -> None:
    """QA R1: every CubiCasa area question was refused (no printed scale). The demo config gives
    a raster sheet with detected doors an estimated scale and its rooms estimated areas (#81,
    calibrated in #82; a sheet without a detected door stays refused)."""
    found = run("config")
    assert found.returncode == 0, found.stderr
    assert "RASTER_SCALE=priors" in found.stdout.split()


def test_the_backend_starts_with_the_printed_config() -> None:
    script = SCRIPT.read_text()
    assert 'env "${DEMO_ENV[@]}" uv run --locked uvicorn' in script


def test_the_demo_config_ships_config_c() -> None:
    """integ Task 3 (2026-11-14): the Decisions S1536 swap over the C-yolo26l detector for elements
    and plans, rooms from regionrooms, beat the earlier demo (region C-yolo26s-1536) on val by
    +1.1 pp [+0.1, +2.0] with no family lower; the orchestrator shipped it (07:31)."""
    found = run("config")
    assert found.returncode == 0, found.stderr
    swap = "decisions-s1536:detector:C-yolo26l"
    shipped = f"RASTER_COMPONENTS=elements={swap},plans={swap},rooms=regionrooms"
    assert shipped in found.stdout.split()


def test_the_demo_config_marks_answers_sure_by_goldens_frozen_gate() -> None:
    """golden-19 (2026-11-14): config C's gate, chosen on val and certified once on test (of the
    plans marked sure, at least 96.2% have every sure answer exact). The demo reads a committed
    copy, so a refit of data/stoa/exp/gate.json can't change it without a commit and a fresh
    machine has it."""
    found = run("config")
    assert found.returncode == 0, found.stderr
    setting = "GATE_POLICY=../eval/results/gate/gate-C-L-swap.json"
    assert setting in found.stdout.split()
    frozen = json.loads((SCRIPT.parents[1] / "backend" / setting.split("=")[1]).read_text())
    assert (frozen["schema"], frozen["certified"]) == ("gate_policy_v1", True)
    assert frozen["test"]["certificate"]["lower_bound"] >= frozen["target"]


def test_the_demo_config_answers_kitchens_from_goldens_frozen_policy() -> None:
    """golden (2026-11-14, fail-2): with ANSWER_POLICY empty every family was answered by the
    readers, and config C's kitchens (91.7% on val) lost to the train prior (96.2%). The prior
    wins kitchens on both val halves; the backend runtime A/B gives +0.35 pp [+0.12, +0.60]. The
    demo reads a committed copy that sends exactly that family to the prior."""
    found = run("config")
    assert found.returncode == 0, found.stderr
    setting = "ANSWER_POLICY=../eval/results/policy/policy-C-L-swap.json"
    assert setting in found.stdout.split()
    frozen = json.loads((SCRIPT.parents[1] / "backend" / setting.split("=")[1]).read_text())
    assert (frozen["schema"], frozen["part"]) == ("answer_policy_v1", "val")
    to_prior = [family for family, pick in frozen["families"].items() if pick["source"] == "prior"]
    assert to_prior == ["room:kitchen"]

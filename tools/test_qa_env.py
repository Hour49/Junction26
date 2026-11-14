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


def test_the_demo_config_ships_config_c1_t1() -> None:
    """integ-11/12 (2026-11-14): C1 (the Decisions S1536 swap over eight views of C-yolo26l, rooms
    from regionrooms) with the local count arbiter T1's counts for door, window, sink, toilet,
    shower and bathtub: on val +0.2 pp [-0.1, +0.6] against C1 as shipped, within noise, so the
    local reader ships (D474); the double-check readers and golden's check policy with it."""
    found = run("config")
    assert found.returncode == 0, found.stderr
    swap = "decisions-s1536:detector-v8:C-yolo26l"
    t1 = "arbiter-t1:C-yolo26l:C-yolo26l-onnx-val"
    six = ",".join(f"{c}={t1}" for c in ("door", "window", "sink", "toilet", "shower", "bathtub"))
    shipped = f"RASTER_COMPONENTS=elements={swap},plans={swap},{six},rooms=regionrooms"
    config = found.stdout.split()
    assert shipped in config
    assert "DOUBLE_CHECK_READERS=l1=detector:C-yolo26l,m1=detector:C-yolo26m" in config
    check = "CHECK_POLICY=../eval/results/check/check-C1-T1-recall96-rt-full-small-medium20.json"
    assert check in config  # #215's certified policy + confidence levels (#233), same thresholds
    assert (SCRIPT.parents[1] / "backend" / check.split("=")[1]).is_file()
    assert any(line.startswith("LOCAL_GATES=") for line in config)


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


def test_the_backend_is_told_which_commit_it_runs() -> None:
    """GET /api/info `commit` (APP_COMMIT): tools/smoke.py prints which build it talks to."""
    script = SCRIPT.read_text()
    assert 'APP_COMMIT="$SHA" GEMINI_API_KEY="$KEY"' in script


def test_the_demo_config_reads_big_sheets_and_printed_scales_with_carbon() -> None:
    """demo/carbon (2026-11-14): CARBON_READER=large counts the drawn things on raster images over
    4,000 px with Carbon (flagged, never certified, #269) and RASTER_PRINTED_SCALE=carbon lets a
    scale measured from the sheet's own bar replace the door estimate (#256). Neither is the
    default of the backend, so the demo config has to name them."""
    found = run("config")
    assert found.returncode == 0, found.stderr
    config = found.stdout.split()
    assert "CARBON_READER=large" in config and "RASTER_PRINTED_SCALE=carbon" in config


def test_the_demo_config_warns_about_sheet_kinds_without_setting_sheets_aside() -> None:
    """demo/sheet-kind (2026-11-14, Bogdan D732): SHEET_KIND=carbon names what a sheet looks like
    and SHEET_KIND_SET_ASIDE=false reads and flags a doubtful sheet instead of setting it aside
    (#265). The backend defaults are off and true, so the demo config has to name both."""
    found = run("config")
    assert found.returncode == 0, found.stderr
    config = found.stdout.split()
    assert "SHEET_KIND=carbon" in config and "SHEET_KIND_SET_ASIDE=false" in config
    assert "CARBON_LEVELS=ladder" in config

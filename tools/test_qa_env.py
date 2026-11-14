"""tools/qa-env.sh refuses bad input before it exports or starts anything. (Starting a commit's
backend is checked by hand: it needs the models, uv and a port; see the script's header.)"""

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


def test_the_backend_starts_with_the_printed_config() -> None:
    script = SCRIPT.read_text()
    assert 'env "${DEMO_ENV[@]}" uv run --locked uvicorn' in script

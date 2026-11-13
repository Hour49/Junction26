"""Tests for tools/scrub.py on a throwaway repo; each "found" test has an "allowed" pair."""
import subprocess
import sys
from pathlib import Path

import pytest

SCRUB = Path(__file__).with_name("scrub.py")
# Built at runtime from pieces so this file passes the scrub itself.
HOME = "/ho" + "me/alice/project"
MAC = "/Us" + "ers/alice/project"
WINDOWS = "C:" + "\\Us" + "ers\\alice\\project"
TAILNET = "dev1.tail1a2b" + ".ts" + ".net"


@pytest.fixture
def scrub(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    def run(text, tracked=True):
        (repo / "notes.md").write_text(f"# notes\n{text}\n")
        if tracked:
            subprocess.run(["git", "-C", str(repo), "add", "notes.md"], check=True)
        return subprocess.run([sys.executable, str(SCRUB), str(repo)], capture_output=True,
                              text=True, check=False)

    return run


@pytest.mark.parametrize("text, kind", [
    (f"cd {HOME}", "home path"),
    (f"open {MAC}/a.txt", "home path"),
    (f"copy to {WINDOWS}", "Windows home path"),
    (f"ssh {TAILNET}", "Tailscale hostname"),
])
def test_personal_traces_are_found_without_printing_them(scrub, text, kind):
    out = scrub(text)
    assert out.returncode == 1
    assert out.stdout.strip() == f"notes.md:2: {kind}"
    assert "alice" not in out.stdout + out.stderr and "tail1a2b" not in out.stdout + out.stderr


@pytest.mark.parametrize("text", [
    "cd /home/<user>/project or ~/project",
    "open /Users/<name>/a.txt",
    "copy to C:\\Users\\<name>\\project",
    "ssh <machine>.ts.net; no `.ts.net` names here",
    "see https://example.com/home/about and /home/ itself",
])
def test_placeholders_and_look_alikes_are_allowed(scrub, text):
    out = scrub(text)
    assert out.returncode == 0, out.stdout
    assert "1 tracked files, no home paths" in out.stdout


def test_untracked_files_are_not_scanned(scrub):
    assert scrub(f"cd {HOME}", tracked=False).returncode == 0

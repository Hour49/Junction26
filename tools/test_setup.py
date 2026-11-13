"""Offline tests for tools/setup.sh in a throwaway HOME (no network: --offline, herdr hidden).

setup.sh runs from a copy at <HOME>/repo, so a test never changes the real clone's git config."""
import json
import os
import shutil
import subprocess
from pathlib import Path

SETUP = Path(__file__).with_name("setup.sh")
BEGIN, END = "<!-- hour49-team:begin -->", "<!-- hour49-team:end -->"
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"}


def run(home):
    repo = home / "repo"
    if not (repo / "tools").exists():
        (repo / "tools").mkdir(parents=True)
        shutil.copy2(SETUP, repo / "tools")
        shutil.copytree(SETUP.parent.parent / "templates", repo / "templates")
    out = subprocess.run(["bash", str(repo / "tools" / "setup.sh"), "--offline"],
                         env={**ENV, "HOME": str(home)}, capture_output=True, text=True, check=True)
    return out.stdout


def hooks_path(home):
    return subprocess.run(["git", "-C", str(home / "repo"), "config", "--get", "core.hooksPath"],
                          env={**ENV, "HOME": str(home)}, capture_output=True, text=True,
                          check=False).stdout.strip()


def test_fresh_home_gets_personal_and_team_block(tmp_path):
    out = run(tmp_path)
    md = (tmp_path / ".claude" / "CLAUDE.md").read_text()
    assert "## Who and where" in md and md.count(BEGIN) == 1 and md.count(END) == 1
    assert "## Team board (GitHub, tools/board)" in md
    assert "created" in out
    assert os.readlink(tmp_path / ".local" / "bin" / "board").endswith("tools/board")
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings["attribution"] == {"commit": "", "pr": "", "sessionUrl": False}


def test_rerun_is_a_no_op(tmp_path):
    run(tmp_path)
    md = (tmp_path / ".claude" / "CLAUDE.md").read_text()
    out = run(tmp_path)
    assert "already up to date" in out
    assert (tmp_path / ".claude" / "CLAUDE.md").read_text() == md
    assert not list((tmp_path / ".claude").glob("*.bak-*"))


def test_existing_instructions_are_kept_and_block_replaced_in_place(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "CLAUDE.md").write_text(f"# Mine\nkeep me\n\n{BEGIN}\nOLD RULES\n{END}\n\n## After\nme too\n")
    (claude / "settings.json").write_text(json.dumps({"model": "opus", "attribution": {"x": 1}}))
    run(tmp_path)
    md = (claude / "CLAUDE.md").read_text()
    assert md.startswith("# Mine\nkeep me\n") and md.rstrip().endswith("## After\nme too")
    assert "OLD RULES" not in md and md.count(BEGIN) == 1
    settings = json.loads((claude / "settings.json").read_text())
    assert settings["model"] == "opus" and settings["attribution"]["x"] == 1
    assert len(list(claude.glob("CLAUDE.md.bak-*"))) == 1


def test_file_without_markers_gets_block_appended(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "CLAUDE.md").write_text("# My own rules\n")
    out = run(tmp_path)
    md = (claude / "CLAUDE.md").read_text()
    assert md.startswith("# My own rules\n") and BEGIN in md and "appended" in out


def test_clone_gets_the_repo_hooks_once(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path / "repo")],
                   env={**ENV, "HOME": str(tmp_path)}, check=True)
    assert "core.hooksPath = .githooks" in run(tmp_path)
    assert hooks_path(tmp_path) == ".githooks"
    assert "core.hooksPath already .githooks" in run(tmp_path)


def test_copy_that_is_not_a_clone_is_skipped(tmp_path):
    assert "is not a git clone" in run(tmp_path)

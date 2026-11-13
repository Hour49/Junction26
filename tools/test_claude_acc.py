"""Offline tests for tools/claude-acc: a stub `claude` reports the CLAUDE_CONFIG_DIR it was started with."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).with_name("claude-acc")


def run(tmp_path, n, exported):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "claude"
    stub.write_text('#!/bin/sh\necho "${CLAUDE_CONFIG_DIR-unset}"\n')
    stub.chmod(0o755)
    env = {"HOME": str(home), "PATH": f"{stub_dir}:/usr/bin:/bin", "LANG": "C.UTF-8"}
    if exported:
        env["CLAUDE_CONFIG_DIR"] = exported
    out = subprocess.run(["bash", str(SCRIPT), str(n)], env=env, capture_output=True, text=True,
                         check=True)
    return out.stdout.strip(), home


def test_account_1_ignores_exported_config_dir(tmp_path):
    out, _ = run(tmp_path, 1, str(tmp_path / "home" / ".claude-2"))
    assert out == "unset"


def test_account_1_without_export_is_unset(tmp_path):
    out, _ = run(tmp_path, 1, None)
    assert out == "unset"


def test_account_2_uses_its_own_dir_despite_export(tmp_path):
    out, home = run(tmp_path, 2, "/somewhere/else")
    assert out == str(home / ".claude-2")
    assert os.path.isdir(home / ".claude-2")

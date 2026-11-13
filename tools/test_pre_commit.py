"""Tests for .githooks/pre-commit: a throwaway repo with the hook installed, real commits."""
import os
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / ".githooks"
LIMIT = 5 * 1024 * 1024

# Built at runtime from pieces so this file passes the hook and gitleaks itself.
FAKE_KEYS = {
    "google": "AIza" + "Sy" + "a1B2c3D4" * 4 + "x",
    "openai": "sk-" + "proj-" + "Ab1" * 16,
    "anthropic": "sk-" + "ant-api03-" + "Zz9_" * 24,
    "github": "ghp" + "_" + "A1b2C3d4E5f6" * 3,
    "github_pat": "github" + "_pat_" + "11ABCDEFG0" * 6,
    "cloudflare": "cfat" + "_" + "Q7w8E9r0T1y2U3i4O5p6",
    "aws": "AK" + "IA" + "QWERTYUIOPASDFGH",
    "private_key": "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
}


@pytest.fixture
def repo(tmp_path):
    env = {
        "HOME": str(tmp_path), "PATH": os.environ["PATH"], "LANG": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    path = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(path)], env=env, check=True)

    def git(*args):
        return subprocess.run(["git", "-C", str(path), *args], env=env, capture_output=True,
                              text=True, check=False)

    git("config", "core.hooksPath", str(HOOKS))
    git.path = path
    return git


def stage(git, files):
    for name, content in files.items():
        f = git.path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content if isinstance(content, bytes) else content.encode())
    assert git("add", "--", *files).returncode == 0


def commit(git, files):
    stage(git, files)
    return git("commit", "-q", "-m", "test")


@pytest.mark.parametrize("name", [".env", ".env.local", "app/.env.production"])
def test_env_files_are_refused(repo, name):
    out = commit(repo, {name: "KEY=value\n"})
    assert out.returncode != 0
    assert f"{name}: .env files" in out.stderr


def test_env_example_and_a_normal_file_pass(repo):
    out = commit(repo, {".env.example": "KEY=\n", "src/app.py": "print('hi')\n"})
    assert out.returncode == 0, out.stderr


@pytest.mark.parametrize("kind", sorted(FAKE_KEYS))
def test_key_shaped_strings_are_refused_without_printing_them(repo, kind):
    key = FAKE_KEYS[kind]
    out = commit(repo, {"config.py": f"# settings\nTOKEN = '{key}'\n"})
    assert out.returncode != 0
    assert "config.py line 2: " in out.stderr
    assert key not in out.stderr + out.stdout


def test_look_alikes_pass(repo):
    text = "ask-for-permission-before-running-any-commands-here\nAKIA is a prefix\nsk-short\n"
    out = commit(repo, {"notes.md": text})
    assert out.returncode == 0, out.stderr


def test_the_staged_version_is_checked_not_the_working_tree(repo):
    stage(repo, {"config.py": f"TOKEN = '{FAKE_KEYS['aws']}'\n"})
    (repo.path / "config.py").write_text("TOKEN = ''\n")  # cleaned on disk, but not re-staged
    out = repo("commit", "-q", "-m", "test")
    assert out.returncode != 0
    assert "AWS access key" in out.stderr


def test_files_over_5_mb_are_refused(repo):
    out = commit(repo, {"big.bin": b"a" * (LIMIT + 1)})
    assert out.returncode != 0
    assert "big.bin: 5.1 MB, over the 5 MB limit" in out.stderr


def test_a_file_of_exactly_5_mb_passes(repo):
    out = commit(repo, {"edge.bin": b"a" * LIMIT})
    assert out.returncode == 0, out.stderr

"""Starts `eval/ab_backend.py` in backend/'s own environment (uv), so experiment arms are answered
by the backend's parser and takeoff without eval importing the backend. Tests replace `run`."""

import os
import subprocess
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
BACKEND = EVAL.parent / "backend"
SCRIPT = EVAL / "ab_backend.py"


def run(*args: str) -> None:
    """`ab_backend.py <args>` from backend/; fails with ValueError when it fails."""
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    env["PYTHONPATH"] = str(BACKEND)
    command = ["uv", "run", "--locked", "--project", str(BACKEND), "python", str(SCRIPT), *args]
    try:
        subprocess.run(command, cwd=BACKEND, env=env, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"the backend answerer failed: {error}") from error

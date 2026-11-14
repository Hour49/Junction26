"""Starts `eval/ab_backend.py` in backend/'s own environment (uv), so experiment arms are answered
by the backend's parser and takeoff without eval importing the backend. Tests replace `run`."""

import os
import subprocess
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
BACKEND = EVAL.parent / "backend"
SCRIPT = EVAL / "ab_backend.py"
SERVICES_SCRIPT = EVAL / "services_backend.py"  # services-gen: an IFC model's services graph


def run(*args: str, script: Path = SCRIPT) -> None:
    """`<script> <args>` (ab_backend.py by default) from backend/; ValueError when it fails."""
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    env["PYTHONPATH"] = str(BACKEND)
    command = ["uv", "run", "--locked", "--project", str(BACKEND), "python", str(script), *args]
    try:
        subprocess.run(command, cwd=BACKEND, env=env, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"the backend answerer failed: {error}") from error

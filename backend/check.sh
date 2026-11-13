#!/usr/bin/env bash
# check.sh: every backend check CI runs (docs/ENGINEERING.md section 6). CI calls this same script.
#   ./check.sh          lint, format, types, tests, dependency audit
#   ./check.sh quick    lint, format and types only, for before a commit
# An accepted audit finding goes on the `uv audit` line as `--ignore <id>`, with a comment saying why.
set -euo pipefail
cd "$(dirname "$0")"

uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pyright
[ "${1:-}" = quick ] && exit 0
uv run --locked pytest -q
uv audit --locked

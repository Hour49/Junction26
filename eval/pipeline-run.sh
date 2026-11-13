#!/usr/bin/env bash
# pipeline-run.sh: one point of the `pipeline` series (docs/GOLDEN.md "Pipeline series").
# Runs the product end to end on golden v2 from a clean export (git archive) of <commit>, never the
# shared tree, and records both parts under the method name `pipeline`, scored by this tree's eval.
#
#   eval/pipeline-run.sh <commit> [NAME=VALUE ...]
#   eval/pipeline-run.sh 85d3470 EXTRACTOR_VECTOR=pdf QUESTION_PARSER=templates
#
# NAME=VALUE are the backend settings that turn on every real adapter of that commit. The record
# keeps the settings the export actually ran with (all of them, read back from its Settings).
# With ANSWER_PRIOR=dev the export builds its own dev prior from data/stoa/split/dev.jsonl first.
# Everything lands in data/stoa/runs/pipeline-<sha>-<time>/ (gitignored): export/ (the code and
# its venv; delete the folder when done) and out/ (what the backend wrote). Cap it like any
# heavy job: systemd-run --user --scope -p MemoryMax=6G nice -n 15 eval/pipeline-run.sh ...
set -euo pipefail

commit=${1:?usage: eval/pipeline-run.sh <commit> [NAME=VALUE ...]}
shift
for pair in "$@"; do
  [[ $pair =~ ^[A-Za-z_][A-Za-z0-9_]*=[^/]+$ ]] || { echo "not NAME=VALUE: $pair" >&2; exit 2; }
done
eval_dir=$(cd "$(dirname "$0")" && pwd)
repo=$(dirname "$eval_dir")
golden=$repo/data/stoa/golden/v2
dataset=$repo/data/stoa/full/junction-dataset
short=$(git -C "$repo" rev-parse --verify --short "$commit^{commit}")
work=$repo/data/stoa/runs/pipeline-$short-$(date +%Y%m%d-%H%M%S)
mkdir -p "$work/export"
git -C "$repo" archive "$short" backend | tar -x -C "$work/export"
echo "export of $short in $work/export"

cd "$work/export/backend"
# An export has no .env, so the backend sees only these settings and its own defaults.
backend() { env "$@" uv run --locked python "${backend_args[@]}"; }
if [[ " $* " == *" ANSWER_PRIOR=dev "* ]]; then
  backend_args=(-m app.adapters.answer_prior "$repo/data/stoa/split/dev.jsonl")
  backend "$@"
fi
backend_args=(-c 'from app.settings import Settings
for name, value in Settings().model_dump().items(): print(f"{name}={value}")')
mapfile -t effective < <(backend "$@")
[[ ${#effective[@]} -gt 0 ]] || { echo "could not read the export's settings" >&2; exit 1; }
echo "settings: ${effective[*]}"
backend_args=(-m app.cli golden --golden-dir "$golden" --dataset "$dataset" --drawings pipeline
  --out "$work/out")
backend "$@"

cd "$eval_dir"
record=(--name pipeline --commit "$short")
for setting in "${effective[@]}"; do record+=(--setting "$setting"); done
uv run --locked python -m stoa_eval score-extraction "$work/out/extraction" "${record[@]}"
uv run --locked python -m stoa_eval score "$work/out/answers.jsonl" --reads pipeline-extraction \
  "${record[@]}"
echo "recorded both parts of $short; the table: uv run python -m stoa_eval series"

#!/usr/bin/env bash
# pipeline-record.sh: records a finished pipeline-run.sh folder as one point of the `pipeline`
# series (pipeline-run.sh calls it; run it alone to record a kept run folder again, no rerun).
#
#   eval/pipeline-record.sh <run folder> <commit> [NAME=VALUE ...]
#
# <run folder>/settings.txt holds the settings the export ran with, one name=value a line. The
# record is public: a value the record's rule refuses (a path, a long RASTER_COMPONENTS) goes in as
# name=sha256:<first 12 hex of the value>, so runs with different values still differ. The
# NAME=VALUE pairs the run was given go verbatim into the note, then $PIPELINE_NOTE if set; a
# note with an absolute or home path is refused.
set -euo pipefail

work=${1:?usage: eval/pipeline-record.sh <run folder> <commit> [NAME=VALUE ...]}
short=${2:?usage: eval/pipeline-record.sh <run folder> <commit> [NAME=VALUE ...]}
shift 2
cd "$(dirname "$0")"

note="given: $*${PIPELINE_NOTE:+. $PIPELINE_NOTE}"
if [[ $note =~ (^|[[:space:]=,:])[/~] || $note == */home/* ]]; then
  echo "the note names an absolute or home path; the record is public: $note" >&2
  exit 2
fi
record=(--name pipeline --commit "$short" --note "$note")
while IFS= read -r setting; do
  name=${setting%%=*} value=${setting#*=}
  if [[ ! $value =~ ^[A-Za-z0-9_.:+-]{1,64}$ ]]; then  # stoa_eval's SETTING_VALUE
    value=sha256:$(printf %s "$value" | sha256sum | cut -c1-12)
  fi
  record+=(--setting "$name=$value")
done < "$work/settings.txt"
uv run --locked python -m stoa_eval score-extraction "$work/out/extraction" "${record[@]}"
uv run --locked python -m stoa_eval score "$work/out/answers.jsonl" --reads pipeline-extraction \
  "${record[@]}"
echo "recorded both parts of $short; the table: uv run python -m stoa_eval series"

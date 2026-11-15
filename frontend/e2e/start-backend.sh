#!/usr/bin/env bash
# The no-keys backend for the e2e run (docs/specs/frontend/golden-path.md "The e2e test"): the synthetic sample
# archive in a new temp dir, every setting that could call a key or a model forced off, port 8010.
set -euo pipefail
cd "$(dirname "$0")/../../backend"
# shortcut: the temp dir is not removed after the run; it holds one small sample project per run.
DATA=$(mktemp -d)
uv run --locked python scripts/make_sample_archive.py --out "$DATA/sample-project.zip"
# The environment beats a developer's backend/.env (pydantic-settings).
export PROJECTS_DIR="$DATA/projects" SAMPLE_ARCHIVE="$DATA/sample-project.zip" \
  CREDIT_DATASET="$DATA/none" CREDIT_PHOTOS="$DATA/none" DISCIPLINE_PICTURES_CACHE_DIR="$DATA/discipline-pictures"
if [[ "${E2E_DEMO:-}" == 1 ]]; then
  # E2E_DEMO=1: exactly the demo config (tools/qa-env.sh config, DEMO_ENV) with every key empty; nothing of its
  # own (review-494 M1: a setting the demo turns on goes into DEMO_ENV and this follows). The demo settings that
  # only work with a key refuse to start without one (composition, checked one by one), so they get the no-keys
  # values: the raster readers (Decisions swap, Carbon reader and levels, printed scale, double-check readers),
  # the sheet kind and triage describer, the wider evidence scope (it asks the sheet kind), and the Gemini chat
  # (every turn would need the key: the rules planner). Everything else is the demo's, including the r3 rectifier
  # and the check/gate policies and local gates (they need no key).
  # Needs the repo's data/models (a worktree: link it from the main clone, as tools/qa-env.sh does).
  [[ -d ../data/models ]] || { echo "E2E_DEMO=1 needs data/models (ln -s <main clone>/data/models data/)" >&2; exit 1; }
  while IFS= read -r setting; do export "${setting?}"; done < <(bash ../tools/qa-env.sh config)
  export GEMINI_API_KEY= EU_VLM_API_KEY= VERDA_INFERENCE_API_KEY= \
    EXTRACTOR_RASTER=hello RASTER_COMPONENTS= DECISIONS_KIND=false DECISIONS_CONFIDENCE=false \
    CARBON_READER=off CARBON_LEVELS=off RASTER_PRINTED_SCALE=off DOUBLE_CHECK_READERS= \
    SHEET_KIND=off TRIAGE_DESCRIBER=off EVIDENCE_SCOPE=set_aside CHAT_MODEL=rules
  exec uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port "${E2E_API_PORT:-8010}"
fi
# Triage stays off unless the caller sets TRIAGE_CLASSIFIER=rules (e2e/triage.spec.ts, file-triage.md FT-21); the
# services pictures and their follow-up stay off unless it sets DISCIPLINE_PICTURES=template SERVICES_FOLLOW=on
# (e2e/pics-follow.spec.ts).
export EXTRACTOR_RASTER=hello RASTER_COMPONENTS= RECTIFIER=none \
  DECISIONS_KIND=false DECISIONS_CONFIDENCE=false ANSWER_PRIOR=none ANSWER_POLICY= \
  TRIAGE_CLASSIFIER="${TRIAGE_CLASSIFIER:-off}" TRIAGE_DESCRIBER=off TRIAGE_JUDGE=off \
  DISCIPLINE_PICTURES="${DISCIPLINE_PICTURES:-off}" \
  SERVICES_FOLLOW="${SERVICES_FOLLOW:-off}" MODEL_3D=1
exec uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port "${E2E_API_PORT:-8010}"

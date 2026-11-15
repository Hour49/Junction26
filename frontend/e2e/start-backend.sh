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
  CREDIT_DATASET="$DATA/none" CREDIT_PHOTOS="$DATA/none"
if [[ "${E2E_DEMO:-}" == 1 ]]; then
  # E2E_DEMO=1: the demo config (tools/qa-env.sh config) plus what the all-on demo turns on (USER_SCALE, triage
  # rules), with every key empty. The demo's settings that only work with a key do not start without one
  # (composition refuses them), so they get the no-keys run's values: the raster readers (Decisions, Carbon,
  # the double-check and the policies scored on them), the sheet kind and triage describer, the wider evidence
  # scope (it asks the sheet kind) and the Gemini chat (the rules planner instead). The rest stays as the demo
  # has it: IFC facts, 3D, services, triage judge, set-aside off, scale priors, user scale, answer prior/policy.
  # Needs the repo's data/models (a worktree: link it from the main clone, as tools/qa-env.sh does).
  [[ -d ../data/models ]] || { echo "E2E_DEMO=1 needs data/models (ln -s <main clone>/data/models data/)" >&2; exit 1; }
  while IFS= read -r setting; do export "${setting?}"; done < <(bash ../tools/qa-env.sh config)
  export USER_SCALE=true TRIAGE_CLASSIFIER=rules GEMINI_API_KEY= EU_VLM_API_KEY= VERDA_INFERENCE_API_KEY= \
    EXTRACTOR_RASTER=hello RASTER_COMPONENTS= RECTIFIER=none DECISIONS_KIND=false DECISIONS_CONFIDENCE=false \
    CARBON_READER=off CARBON_LEVELS=off RASTER_PRINTED_SCALE=off DOUBLE_CHECK_READERS= CHECK_POLICY= \
    LOCAL_GATES= GATE_POLICY= SHEET_KIND=off TRIAGE_DESCRIBER=off EVIDENCE_SCOPE=set_aside CHAT_MODEL=rules
  exec uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port "${E2E_API_PORT:-8010}"
fi
# Triage stays off unless the caller sets TRIAGE_CLASSIFIER=rules (e2e/triage.spec.ts, file-triage.md FT-21).
export EXTRACTOR_RASTER=hello RASTER_COMPONENTS= RECTIFIER=none \
  DECISIONS_KIND=false DECISIONS_CONFIDENCE=false ANSWER_PRIOR=none ANSWER_POLICY= \
  TRIAGE_CLASSIFIER="${TRIAGE_CLASSIFIER:-off}" TRIAGE_DESCRIBER=off TRIAGE_JUDGE=off \
  MODEL_3D=1
exec uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port "${E2E_API_PORT:-8010}"

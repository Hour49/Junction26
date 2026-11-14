#!/usr/bin/env bash
# The no-keys backend for the e2e run (docs/specs/frontend/golden-path.md "The e2e test"): the synthetic sample
# archive in a new temp dir, every setting that could call a key or a model forced off, port 8010.
set -euo pipefail
cd "$(dirname "$0")/../../backend"
# shortcut: the temp dir is not removed after the run; it holds one small sample project per run.
DATA=$(mktemp -d)
uv run --locked python scripts/make_sample_archive.py --out "$DATA/sample-project.zip"
# The environment beats a developer's backend/.env (pydantic-settings). Triage stays off unless the caller sets
# TRIAGE_CLASSIFIER=rules (e2e/triage.spec.ts, file-triage.md FT-21).
export PROJECTS_DIR="$DATA/projects" SAMPLE_ARCHIVE="$DATA/sample-project.zip" \
  CREDIT_DATASET="$DATA/none" CREDIT_PHOTOS="$DATA/none" \
  EXTRACTOR_RASTER=hello RASTER_COMPONENTS= RECTIFIER=none \
  DECISIONS_KIND=false DECISIONS_CONFIDENCE=false ANSWER_PRIOR=none ANSWER_POLICY= \
  TRIAGE_CLASSIFIER="${TRIAGE_CLASSIFIER:-off}" TRIAGE_DESCRIBER=off TRIAGE_JUDGE=off
exec uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port "${E2E_API_PORT:-8010}"

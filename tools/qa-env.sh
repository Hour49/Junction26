#!/usr/bin/env bash
# A frozen QA environment: one commit, exported, run with the demo config, so a QA round tests a
# fixed build while work goes on in the tree.
#
#   tools/qa-env.sh <commit> [port] [--frontend]   export <commit>, start its backend on port (8780)
#   tools/qa-env.sh stop <commit>                  stop what this script started for <commit>
#   tools/qa-env.sh config                         print the demo config the backend starts with
#
# The export goes to data/qa/env-<sha>/ (gitignored; made once, reused after). The backend runs
# from it with the shippable config (config C1-T1, picked on val 2026-11-14): the C-yolo26l
# detector read in eight views (detector-v8) behind the Decisions S1536 swap for elements and
# plans, except door, window, sink, toilet, shower and bathtub, whose counts the local count
# arbiter T1 picks (arbiter-t1, data/models/arbiter/T1: the eight views, one view and the L1
# page-count model; it keeps what it read on the drawing), Gemini rooms through the
# region room filter (REGION_MODEL_DIR, the settings default), the r3 photo rectifier, the dev
# prior, the Decisions confidence and the Decisions sheet-kind signal (a photo of a plan without
# camera EXIF is still rectified), and golden's gate (eval/results/gate/gate-C-L-swap.json, frozen in
# the repo: which answers are marked sure, refit on config C's val output, certified once on test),
# and golden's answer policy (eval/results/policy/policy-C-L-swap.json, frozen in the repo: CubiCasa
# kitchens are answered from the prior, which beats config C's readers on both val halves). The
# double-check: the readers l1 (C-yolo26l, one view) and m1 (C-yolo26m, one view) are kept on
# each drawing, and golden's check policy (golden-22 rt-full-small, a frozen, committed copy in
# eval/results/check/, scored by local-dec's local gates in data/models/arbiter/T1) certifies an
# answer or asks for a double-check.
# It reads
# the repo's data/models, data/stoa, data/cache, data/demo and data/external through symlinks and
# keeps its own data/projects. GEMINI_API_KEY comes from the repo-root .env, into this process's
# environment only: never printed, never written to a file.
#
# --frontend also builds frontend/ from the same export (npm ci && npm run build) and serves its
# dist/ on port+1 with /api passed to the backend (tools/qa_serve.py: one origin, as the Vite proxy
# gives in development; the server is this checkout's, not the commit's). Without frontend/ in the
# commit it says so and serves the backend only.
#
# Each process gets a pid file in the env folder; `stop` signals only those process groups.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QA="$ROOT/data/qa"
SWAP='decisions-s1536:detector-v8:C-yolo26l'
T1='arbiter-t1:C-yolo26l:C-yolo26l-onnx-val'
RASTER="elements=$SWAP,plans=$SWAP,door=$T1,window=$T1,sink=$T1,toilet=$T1,shower=$T1,bathtub=$T1,rooms=regionrooms"
DEMO_ENV=(EXTRACTOR_RASTER=composite RECTIFIER=r3 ANSWER_PRIOR=dev DECISIONS_CONFIDENCE=true
  DECISIONS_KIND=true RASTER_SCALE=priors GATE_POLICY=../eval/results/gate/gate-C-L-swap.json
  ANSWER_POLICY=../eval/results/policy/policy-C-L-swap.json
  DOUBLE_CHECK_READERS=l1=detector:C-yolo26l,m1=detector:C-yolo26m
  CHECK_POLICY=../eval/results/check/check-C1-T1-recall96-rt-full-small-medium20.json
  LOCAL_GATES=../data/models/arbiter/T1/lgate2-rt-C1T1.json,../data/models/arbiter/T1/lgate-rt-noL1-C1T1.json
  CARBON_READER=large  # demo/carbon: images over 4,000 px counted by Carbon, flagged, never certified (#269)
  RASTER_PRINTED_SCALE=carbon  # a measured printed scale replaces the estimate; > 2x from the door estimate holds areas Low (#256)
  SHEET_KIND=carbon  # demo/sheet-kind: Carbon names what each sheet looks like (warn only, #265)
  SHEET_KIND_SET_ASIDE=false  # a sheet that may not be a floor plan is read and flagged, never set aside
  CARBON_LEVELS=ladder  # Carbon reads every raster drawing; Medium it disagrees with -> Low, Medium it agrees with -> High (Bogdan, "Make them High", 2026-11-14)
  CHAT_MODEL=gemini  # the Chat tab answers with Gemini: chat-eval 14/18 right vs 11/18 for rules, follow-ups 26/42 vs 5/42
  IFC_FACTS=true  # all-on: an IFC model's fact sheet answers what the takeoff does not (#327; golden PASS, no differences)
  MODEL_3D=true  # all-on: the 3D view of IFC files (#356/#366/#374/#375); precompute: uv run python -m app.cli glb <ifc>
  TRIAGE_DESCRIBER=carbon  # all-on: an image set aside is described by Carbon for the evidence index (about 0.005 USD an image)
  TRIAGE_JUDGE=rules  # all-on: the judge's rules say whether a set-aside file relates to the project
  EVIDENCE_SCOPE=all_non_plan  # all-on: the evidence index also holds every other non-plan file and PDF page (decision 0012)
  SERVICES_FOLLOW=on  # services-on: an IFC project's plumbing/ventilation/heating files are followed and the chat gets the services tools (#397); the deploy builds the DigitalHub cache first
  INGEST_GROUPS_IN_FLIGHT=10  # ingest-60s: 10 cold files 273 s -> 88 s, cgroup peak 7.3 GB
  INGEST_LOCAL_IN_FLIGHT=1  # 2 is about 20% faster on cached replies but peaked at 9.4 GB once, over MEMORY
  CARBON_CALLS_IN_FLIGHT=48  # the process cap: 107 calls waited 5.4 s in all at 48 (1489 s at 8), 0 429s; up to 48 may run past GEMINI_BUDGET_USD
  CARBON_READ_WORKERS=12  # one read's tile calls at once (at most 20); at 2 local slots 24 peaked at 9.4 GB, 12 at 7.3 (review-422)
  MALLOC_ARENA_MAX=2)  # glibc arenas: peak 9.6 -> 6.7 GB on the same replay, and no slower (33.1 vs 36.5 s)
SHARED=(models stoa cache demo external)  # data/ folders the export reads from the repo
MEMORY=8G
WAIT_S=180

die() { echo "qa-env: $*" >&2; exit 1; }

sha_of() {
  git -C "$ROOT" rev-parse --verify --quiet "$1^{commit}" >/dev/null || die "no commit $1"
  git -C "$ROOT" rev-parse --short=12 "$1^{commit}"
}

stop_pid() {  # the process group in a pid file, then the file
  local file="$1" pid
  [[ -f "$file" ]] || return 0
  pid="$(cat "$file")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$pid" 2>/dev/null && kill -KILL -- "-$pid" 2>/dev/null || true
    echo "qa-env: stopped $(basename "$file" .pid) (pid $pid)"
  fi
  rm -f "$file"
}

start() {  # name, log, command...: in its own session (so `stop` gets its children), capped
  local name="$1" log="$2"
  shift 2
  local cap=()
  if command -v systemd-run >/dev/null && systemd-run --user --scope -q true 2>/dev/null; then
    cap=(systemd-run --user --scope -q -p "MemoryMax=$MEMORY")
  fi
  setsid "${cap[@]}" nice -n 15 "$@" >"$log" 2>&1 </dev/null &
  echo $! >"$ENV/$name.pid"
}

port_free() {
  ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

wait_for() {  # url, pid file, log
  local url="$1" pidfile="$2" log="$3"
  for _ in $(seq 1 "$WAIT_S"); do
    curl -sf -o /dev/null "$url" && return 0
    kill -0 "$(cat "$pidfile")" 2>/dev/null || { tail -20 "$log" >&2; die "it exited; log: $log"; }
    sleep 1
  done
  tail -20 "$log" >&2
  die "no answer from $url after ${WAIT_S}s; log: $log"
}

if [[ "${1:-}" == "config" && $# -eq 1 ]]; then
  printf '%s\n' "RASTER_COMPONENTS=$RASTER" "${DEMO_ENV[@]}"
  exit 0
fi

if [[ "${1:-}" == "stop" ]]; then
  [[ $# -eq 2 ]] || die "usage: tools/qa-env.sh stop <commit>"
  ENV="$QA/env-$(sha_of "$2")"
  [[ -d "$ENV" ]] || die "no environment $ENV"
  stop_pid "$ENV/frontend.pid"
  stop_pid "$ENV/backend.pid"
  exit 0
fi

[[ $# -ge 1 && $# -le 3 ]] || die "usage: tools/qa-env.sh <commit> [port] [--frontend] | stop <commit> | config"
COMMIT="$1"
PORT=8780
FRONTEND=0
for arg in "${@:2}"; do
  case "$arg" in
    --frontend) FRONTEND=1 ;;
    *) [[ "$arg" =~ ^[0-9]+$ ]] || die "port must be a number: $arg"; PORT="$arg" ;;
  esac
done
SHA="$(sha_of "$COMMIT")"
ENV="$QA/env-$SHA"

if [[ -f "$ENV/backend.pid" ]] && kill -0 "$(cat "$ENV/backend.pid")" 2>/dev/null; then
  die "env-$SHA is already running (tools/qa-env.sh stop $SHA)"
fi
port_free "$PORT" || die "port $PORT is in use"
[[ $FRONTEND -eq 0 ]] || port_free "$((PORT + 1))" || die "port $((PORT + 1)) is in use"

if [[ ! -d "$ENV/backend" ]]; then
  echo "qa-env: exporting $SHA to $ENV"
  mkdir -p "$QA"
  tmp="$(mktemp -d "$QA/.export-XXXXXX")"
  git -C "$ROOT" archive "$SHA" | tar -x -C "$tmp"
  mv "$tmp" "$ENV"
fi
mkdir -p "$ENV/data/projects"
for name in "${SHARED[@]}"; do
  if [[ -e "$ROOT/data/$name" && ! -e "$ENV/data/$name" ]]; then
    ln -s "$ROOT/data/$name" "$ENV/data/$name"
  fi
done
(cd "$ENV/backend" && uv sync --locked --quiet)

KEY="$(grep -m1 '^GEMINI_API_KEY=' "$ROOT/.env" 2>/dev/null | cut -d= -f2- | tr -d "\"'")" || true
[[ -n "$KEY" ]] || echo "qa-env: no GEMINI_API_KEY in $ROOT/.env: rooms and the confidence report no reply"

cd "$ENV/backend"
APP_COMMIT="$SHA" GEMINI_API_KEY="$KEY" PROJECTS_DIR="$ENV/data/projects" RASTER_COMPONENTS="$RASTER" \
  start backend "$ENV/backend.log" \
  env "${DEMO_ENV[@]}" uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port "$PORT"
unset KEY
wait_for "http://127.0.0.1:$PORT/api/info" "$ENV/backend.pid" "$ENV/backend.log"
echo "qa-env: backend of $SHA on http://127.0.0.1:$PORT (log $ENV/backend.log)"

if [[ $FRONTEND -eq 1 ]]; then
  if [[ ! -f "$ENV/frontend/package.json" ]]; then
    echo "qa-env: $SHA has no frontend/: serving the backend only"
  else
    (cd "$ENV/frontend" && npm ci --no-audit --no-fund && npm run build) >"$ENV/frontend-build.log" 2>&1 \
      || die "frontend build failed; log: $ENV/frontend-build.log"
    [[ -f "$ENV/frontend/dist/index.html" ]] || die "the build made no frontend/dist/index.html"
    start frontend "$ENV/frontend.log" \
      python3 "$ROOT/tools/qa_serve.py" "$ENV/frontend/dist" "$((PORT + 1))" "http://127.0.0.1:$PORT"
    wait_for "http://127.0.0.1:$((PORT + 1))/" "$ENV/frontend.pid" "$ENV/frontend.log"
    echo "qa-env: frontend of $SHA on http://127.0.0.1:$((PORT + 1))"
  fi
fi
echo "qa-env: stop with tools/qa-env.sh stop $SHA"

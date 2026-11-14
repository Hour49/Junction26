#!/usr/bin/env bash
# The app the README media is recorded from: this checkout's backend with the demo config
# (tools/qa-env.sh config) and its built frontend, each on a port you give.
#
#   tools/readme-media/env.sh start <backend port> <frontend port> [NAME=VALUE ...]
#   tools/readme-media/env.sh stop
#
# Build the frontend first (cd frontend && npm ci && npm run build). The checkout needs data/models
# and data/cache as tools/qa-env.sh does. Every start gets an empty project store, so an upload is
# read and not reused. Pid files, logs and the stores are in data/readme-media/ (gitignored).
# GEMINI_API_KEY comes from the environment, else from $ENV_FILE (default: the repo-root .env),
# into the backend's environment only: never printed, never written. GEMINI_BUDGET_USD (default 1)
# caps the spend, MEMORY (default 4G) the backend. NAME=VALUE arguments override the demo config.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE="$ROOT/data/readme-media"
WAIT_S=180

die() { echo "readme-media: $*" >&2; exit 1; }

stop_pid() {  # the process group in a pid file, then the file
  local file="$1" pid
  [[ -f "$file" ]] || return 0
  pid="$(cat "$file")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$pid" 2>/dev/null && kill -KILL -- "-$pid" 2>/dev/null || true
    echo "readme-media: stopped $(basename "$file" .pid) (pid $pid)"
  fi
  rm -f "$file"
}

port_free() { ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

case "${1:-}" in
  stop)
    stop_pid "$STATE/frontend.pid"
    stop_pid "$STATE/backend.pid"
    ;;
  start)
    [[ $# -ge 3 && "$2" =~ ^[0-9]+$ && "$3" =~ ^[0-9]+$ ]] \
      || die "usage: env.sh start <backend port> <frontend port> [NAME=VALUE ...]"
    api="$2" web="$3"
    shift 3
    [[ -f "$ROOT/frontend/dist/index.html" ]] || die "no frontend/dist: cd frontend && npm ci && npm run build"
    [[ ! -f "$STATE/backend.pid" ]] || die "already started (env.sh stop)"
    port_free "$api" || die "port $api is in use"
    port_free "$web" || die "port $web is in use"
    mkdir -p "$STATE"
    store="$(mktemp -d "$STATE/projects-XXXXXX")"
    mapfile -t config < <("$ROOT/tools/qa-env.sh" config)
    key="${GEMINI_API_KEY:-}"
    env_file="${ENV_FILE:-$ROOT/.env}"
    if [[ -z "$key" && -f "$env_file" ]]; then
      key="$(grep -m1 '^GEMINI_API_KEY=' "$env_file" | cut -d= -f2- | tr -d "\"'")" || true
    fi
    [[ -n "$key" ]] || echo "readme-media: no GEMINI_API_KEY: rooms and the confidence report no reply"
    cap=()
    if command -v systemd-run >/dev/null && systemd-run --user --scope -q true 2>/dev/null; then
      cap=(systemd-run --user --scope -q -p "MemoryMax=${MEMORY:-4G}")
    fi
    (cd "$ROOT/backend" && uv sync --locked --quiet)
    cd "$ROOT/backend"
    APP_COMMIT="$(git -C "$ROOT" rev-parse --short=12 HEAD)" GEMINI_API_KEY="$key" \
      GEMINI_BUDGET_USD="${GEMINI_BUDGET_USD:-1}" PROJECTS_DIR="$store" \
      setsid "${cap[@]}" nice -n 15 env "${config[@]}" "$@" \
      uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port "$api" \
      >"$STATE/backend.log" 2>&1 </dev/null &
    echo $! >"$STATE/backend.pid"
    unset key
    setsid nice -n 15 python3 "$ROOT/tools/qa_serve.py" "$ROOT/frontend/dist" "$web" "http://127.0.0.1:$api" \
      >"$STATE/frontend.log" 2>&1 </dev/null &
    echo $! >"$STATE/frontend.pid"
    for _ in $(seq 1 "$WAIT_S"); do
      curl -sf -o /dev/null "http://127.0.0.1:$web/api/info" && break
      kill -0 "$(cat "$STATE/backend.pid")" 2>/dev/null || { tail -20 "$STATE/backend.log" >&2; die "the backend exited"; }
      sleep 1
    done
    curl -sf -o /dev/null "http://127.0.0.1:$web/api/info" || die "no answer after ${WAIT_S}s; log: $STATE/backend.log"
    echo "readme-media: app on http://127.0.0.1:$web (backend $api); stop with env.sh stop"
    ;;
  *)
    die "usage: env.sh start <backend port> <frontend port> [NAME=VALUE ...] | stop"
    ;;
esac

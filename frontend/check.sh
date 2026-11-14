#!/usr/bin/env bash
# Every frontend check (docs/ENGINEERING.md section 6). CI's generic node job runs the same npm scripts.
# ./check.sh        lint + format, types, tests, build, API types fresh, dependency audit
# ./check.sh quick  lint + format, types (before a commit)
# e2e is separate: npm run e2e
set -euo pipefail
cd "$(dirname "$0")"

[ -d node_modules ] || npm ci
npm run --silent lint
npm run --silent typecheck
[ "${1:-}" = quick ] && exit 0

npm test
npx --no-install vite build
npm run --silent api:check
npm audit --audit-level=high

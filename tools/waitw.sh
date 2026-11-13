#!/bin/bash
# waitw.sh PANE: report when a herdr worker finishes its turn. Arm it BEFORE `herdr agent prompt`.
# 1) wait up to 60 s for the worker to start working; if it never does (it already finished, or
#    the prompt didn't land), go straight to 2), which then returns at once for an idle worker;
# 2) wait up to 2 h for it to stop (idle, done or blocked).
# Prints "<pane> finished <time> (<status>)", or "<pane> WAIT FAILED ..." and exits 1.
export PATH=$HOME/.local/bin:$PATH
pane="${1:?usage: waitw.sh PANE_ID}"
herdr agent wait "$pane" --until working --timeout 60000 >/dev/null 2>&1
if ! out=$(herdr agent wait "$pane" --until idle --until done --until blocked --timeout 7200000 2>&1); then
  echo "$pane WAIT FAILED $(date +%T): ${out:0:300}"
  exit 1
fi
status=$(printf '%s' "$out" | python3 -c "import json,sys
try: print(json.load(sys.stdin)['result']['agent']['agent_status'])
except Exception: print('?')")
echo "$pane finished $(date +%T) ($status)"

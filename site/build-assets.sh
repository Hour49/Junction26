#!/usr/bin/env bash
# Builds site/assets, what the Worker shows with no access code: the Vellum HTML demo at / and the older mock at /mock,
# from files git tracks, plus the one Swiss Dwellings floor in demo/vellum/stoa (CC BY 4.0, credit in its footer).
# Partner data never goes in: a stoa/archive folder (the Stoa scans) stops the build. The floor's answer key comes
# from Stoa's questions file (partner data, non-commercial), so the floor goes in only with INCLUDE_STOA_FLOOR=1,
# which is Bogdan's call; without it the demo's start page is empty.
set -euo pipefail
cd "$(dirname "$0")"
root="$(git rev-parse --show-toplevel)"
out="assets"
rm -rf -- "${out:?}"
mkdir -p "$out/mock"
vellum="$root/demo/vellum"
for file in app.html app.js ask.js chat.js data.js files.js index.html issues.js plan.js stoa.js style.css triage.js vellum-logo.png; do
  git -C "$root" ls-files --error-unmatch "demo/vellum/$file" > /dev/null
  cp "$vellum/$file" "$out/$file"
done
for file in index.html app.js style.css; do
  git -C "$root" ls-files --error-unmatch "demo/$file" > /dev/null
  cp "$root/demo/$file" "$out/mock/$file"
done
stoa="${STOA_DIR:-$vellum/stoa}"  # the locally built folder (gitignored), e.g. another checkout
if [ -e "$stoa/archive" ]; then
  echo "build-assets: $stoa/archive holds partner data (the Stoa scans); remove it first" >&2
  exit 1
fi
if [ "${INCLUDE_STOA_FLOOR:-}" = 1 ] && [ -d "$stoa" ]; then
  mkdir -p "$out/stoa"
  for file in "$stoa"/*; do
    case "$file" in
      *.html|*.js|*.png|*.json) cp "$file" "$out/stoa/" ;;
      *) echo "build-assets: unexpected file $file in $stoa" >&2; exit 1 ;;
    esac
  done
else
  echo "build-assets: no Stoa floor in the assets (INCLUDE_STOA_FLOOR=1 adds demo/vellum/stoa); the demo's start page will be empty" >&2
fi
cp public/favicon.ico "$out/favicon.ico"
echo "built $(find "$out" -type f | wc -l) files, $(du -sk "$out" | cut -f1) KB, in site/$out"

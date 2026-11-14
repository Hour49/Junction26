#!/usr/bin/env bash
# Builds site/assets, what the Worker shows with no access code: the synthetic mock in demo/ (Bogdan, 2026-11-14:
# "visitors without the code should see the html mock demo"). Only files git tracks go in. Nothing from demo/vellum:
# its start page is built from the Stoa dataset (partner data), which never goes to a public address.
set -euo pipefail
cd "$(dirname "$0")"
root="$(git rev-parse --show-toplevel)"
out="assets"
rm -rf -- "${out:?}"
mkdir -p "$out"
for file in index.html app.js style.css; do
  git -C "$root" ls-files --error-unmatch "demo/$file" > /dev/null
  cp "$root/demo/$file" "$out/$file"
done
cp public/favicon.ico "$out/favicon.ico"
echo "built $(find "$out" -type f | wc -l) files, $(du -sk "$out" | cut -f1) KB, in site/$out"

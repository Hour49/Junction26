#!/usr/bin/env bash
# Builds site/assets, what the Worker serves: the clickable Vellum demo in demo/vellum (Bogdan,
# 2026-11-14: "deploy the clicky demo from tudor, it's the new one"). Its start page is made from real files of
# the Stoa dataset by demo/vellum/make_stoa_demo.py, so the build needs the dataset on this machine:
#
#   STOA_DATASET=<path to junction-dataset> [PYTHON=<a python with Pillow and pypdfium2>] ./build-assets.sh
#
# What that puts on a public address: one Swiss Dwellings floor (CC BY 4.0) with its questions and answers (the
# dataset's README: "Questions inherit the licence of the drawing they ask about"), sheets of one OpeningDesign
# house (CC BY-SA 4.0), and, with a picks file, archive scans whose licence allows it (the generator refuses
# NonCommercial files). Nothing else from the dataset, and nothing of it is committed. The recorded examples of the
# full app (demo/vellum/examples.js and examples/) are committed: their drawings are not from the dataset.
set -euo pipefail
cd "$(dirname "$0")"
root="$(git rev-parse --show-toplevel)"
dataset="${STOA_DATASET:-}"
if [ ! -f "$dataset/questions.jsonl" ]; then
  echo "build-assets: set STOA_DATASET to the junction-dataset folder (python3 tools/fetch_stoa_data.py full)" >&2
  exit 1
fi
out="assets"
rm -rf -- "${out:?}"
mkdir -p "$out/examples"
for file in index.html style.css data.js plan.js triage.js issues.js files.js ask.js chat.js examples.js app.js stoa.js vellum-logo.png \
  examples/franklin.webp examples/flat.webp examples/h101.webp examples/h102.webp; do
  git -C "$root" ls-files --error-unmatch "demo/vellum/$file" > /dev/null
  cp "$root/demo/vellum/$file" "$out/$file"
done
"${PYTHON:-python3}" -I "$root/demo/vellum/make_stoa_demo.py" --dataset "$dataset" --out "$PWD/$out/stoa"
# index.html only sends the visitor on to stoa/index.html: without it the address shows nothing
for file in stoa/index.html stoa/data.js; do
  [ -s "$out/$file" ] || { echo "build-assets: $out/$file is missing" >&2; exit 1; }
done
# the credits the licences ask for; the Worker's strip links to this page from every demo page
swiss="$(grep -m1 '^All files:' "$dataset/data/swiss_dwellings/LICENSE.md" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')"
[ -n "$swiss" ] || { echo "build-assets: no 'All files:' credit line for swiss_dwellings in the dataset" >&2; exit 1; }
cat > "$out/credits.html" <<CREDITS
<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Credits</title><body style="font:16px/1.5 system-ui,sans-serif;max-width:40em;margin:0 auto;color:#111">
<div style="padding:1em">
<h1>Credits</h1>
<p>The sample's drawings and questions are real files from the Junction construction drawings dataset, shown for
non-commercial use in the Junction 2026 challenge.</p>
<p><strong>The Swiss apartment floor and its questions.</strong> $swiss
<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. The page images are web copies of the
dataset's PDF and PNG.</p>
<p><strong>The house with a new second floor.</strong> Sheets from the public repositories of
<a href="https://github.com/OpeningDesign">OpeningDesign</a>, Madison, Wisconsin, and the project team named in each
sheet's title block, <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. The sheets are shown
as images of the unchanged PDF pages.</p>
<p>The examples of the full app's answers are not from the dataset:</p>
<p><strong>The scan from 1973.</strong> Isaac Franklin House, U.S. Route 25 East, White Pine, Jefferson County,
Tennessee: sheet 2 of 6 of survey HABS TN-197, drawn by Stephen Fildes for the Survey's East Tennessee Project of 1973.
Historic American Buildings Survey, National Park Service; Library of Congress, Prints and Photographs Division,
<a href="https://www.loc.gov/pictures/item/tn0085.sheet.00002a/">record of the sheet</a>. A work of the U.S. federal
government, in the public domain; the credit is a courtesy. The picture is the Library's master scan, scaled down.</p>
<p><strong>The drawn PDF.</strong> Our own sample flat, drawn by code
(<a href="https://github.com/Hour49/Junction26/blob/main/tools/readme-media/make_plan.py">make_plan.py</a>), MIT
licence.</p>
<p><strong>The heating sheets and their model.</strong> DigitalHub v2, copyright (c) 2020 RWTH Aachen University, E3D
Institute of Energy Efficiency and Sustainable Building, <a href="https://github.com/RWTH-E3D/DigitalHub">MIT
licence</a>. The two heating sheets were rendered by team Hour49 from its models.</p>
<p><a href="/">Back to the demo</a></p>
</div></body></html>
CREDITS
cp public/favicon.ico "$out/favicon.ico"
# the pipeline explainer the app shows at #/stats; the demo's start page links to it
git -C "$root" ls-files --error-unmatch frontend/public/stats.html > /dev/null
cp "$root/frontend/public/stats.html" "$out/how-it-works.html"
echo "built $(find "$out" -type f | wc -l) files, $(du -sk "$out" | cut -f1) KB, in site/$out"

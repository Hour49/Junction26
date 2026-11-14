# README media

How the GIFs and screenshots in `docs/media/` are recorded: Playwright drives the real app, run from this checkout
with the demo settings. Use only drawings we may publish, look at every picture before committing it, and keep the
credit line under it in the README.

```bash
cd frontend && npm ci && npm run build && cd ..
export NODE_PATH=$PWD/frontend/node_modules OUT=$(mktemp -d)
(cd backend && uv run python ../tools/readme-media/make_plan.py $OUT/flat.pdf)   # our own drawn plan
tools/readme-media/env.sh start 8900 8901          # backend and frontend ports; needs free RAM (4 GB cap)
MARK="Mark 19" node tools/readme-media/hero.cjs http://127.0.0.1:8901 <scan of a plan> $OUT/hero
python3 tools/readme-media/togif.py $OUT/hero docs/media/hero.gif
node tools/readme-media/edit.cjs http://127.0.0.1:8901 $OUT/flat.pdf $OUT/edit
python3 tools/readme-media/togif.py $OUT/edit docs/media/agent-edit.gif --cap 5
node tools/readme-media/stills.cjs http://127.0.0.1:8901 $OUT <scan> $OUT/flat.pdf <unread sheets>
tools/readme-media/env.sh stop
```

The drawings behind the pictures (README, "Credits and licences"): the scan is HABS sheet 2 of the Isaac Franklin
House, the Library of Congress master TIFF scaled to a 3000 px wide JPEG; the drawn plan is `make_plan.py`'s flat;
the unread sheets are three PDFs from OpeningDesign's New_2nd_Story repository, zipped. Nothing comes from Stoa's
dataset.

`env.sh` gives every start an empty project store, so the hero shows a real read; run it again before a second
hero take. The questions, the dragged box and the plan's place on its sheet are settings at the top of each
script, and they fit those drawings. With `CHAT_MODEL=gemini` in the demo settings every chat turn is a model call
(about 0.02 to 0.04 USD), and its wording changes from take to take. `sheet.sh <gif> <out.png>` makes a contact sheet
for checking a GIF frame by frame. Record on a quiet machine: frames are taken in real time, so a busy one shows
as stalls in the GIF (`uptime` first). Test: `uv run --no-project --with pytest pytest -q tools/readme-media`.

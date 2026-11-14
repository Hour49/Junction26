# README media

How the GIFs and screenshots in `docs/media/` are recorded: Playwright drives the real app, run from this checkout
with the demo settings. Use only drawings we may publish, look at every picture before committing it, and keep the
credit line under it in the README.

```bash
cd frontend && npm ci && npm run build && cd ..
tools/readme-media/env.sh start 8900 8901          # backend and frontend ports; needs free RAM (4 GB cap)
export NODE_PATH=$PWD/frontend/node_modules OUT=$(mktemp -d)
node tools/readme-media/hero.cjs http://127.0.0.1:8901 <image of a plan> $OUT/hero
python3 tools/readme-media/togif.py $OUT/hero docs/media/hero.gif
node tools/readme-media/edit.cjs http://127.0.0.1:8901 <drawn PDF> $OUT/edit
python3 tools/readme-media/togif.py $OUT/edit docs/media/agent-edit.gif --cap 5
node tools/readme-media/stills.cjs http://127.0.0.1:8901 $OUT <image> <drawn PDF> <unread sheets>
tools/readme-media/env.sh stop
```

`env.sh` gives every start an empty project store, so the hero shows a real read; run it again before a second
hero take. The questions, the dragged box and the plan's place on its sheet are settings at the top of each
script, and they fit the Swiss Dwellings floor the README shows. `sheet.sh <gif> <out.png>` makes a contact sheet
for checking a GIF frame by frame. Test: `uv run --no-project --with pytest pytest -q tools/readme-media`.

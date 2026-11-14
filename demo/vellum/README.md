# demo/vellum/: clickable demo of the Vellum redesign

Static HTML, CSS and JS, no dependencies. **Every drawing, picture and number is real** (Tudor: "just take data from
the real dataset"): a Swiss Dwellings floor with its answer key (`questions.jsonl`), plus real archive scans (floor
plans, an elevation, a section, a site plan, a title sheet, a photo, an artwork) whose register row and description
are what a person saw on each image. Nothing is drawn or made up. The Stoa data is partner data, so the demo is built
on your machine and never committed:

    python3 -I demo/vellum/make_stoa_demo.py --dataset <path to junction-dataset>
    cd demo/vellum && python3 -m http.server 8765    # then open http://localhost:8765/ (it goes to stoa/index.html)

`app.html` is the page template the generator copies into the gitignored `stoa/`; `index.html` only points there.
The archive scans come from a local picks file (`--picks`, default `data/stoa/demo-triage.json`, gitignored).

File triage is a preview (decision 0010): set-aside files with their kind, description, the relevance rule, a
person's call and "Read it as a floor plan" (`triage.js`); the project's Drawings and Files lists; the issues list
(`issues.js`); the project chat with follow-ups and an elevation answer from its description (a preview).

Spec and click map: `../../docs/specs/frontend/clicky-demo.md`.

It shows only what the backend has: no country picker, login or user name (a sign-off takes a typed name), no ETA,
no answer grade.

Routes: `#/` drop, `#/ingest` reading (`/unpack`, `/identify`, `/normalise`, `/extract`, `/check` for the advanced panels),
`#/conflicts` (its "Start a new chat" unlocks once every conflict is settled), `#/chat` (the empty project chat with 3 suggested questions;
each answer's "Show it on <file>" opens `#/ask` on that drawing), `#/ask` (no header tab), `#/issues` (the issues list, filters, CSV), `#/file/<n>` (a file's trace; on a file triage set aside, the triage card with its call, undo and "Read it as a floor plan"), `#/workspaces`. Opening a later route directly starts the sample already read.

For the presenter: everything lives in the page's memory, so a reload starts the sample again
(calls, conflicts, chat and sign-offs are gone). Use the in-page links, not reload, during a walk-through.

Check: `node --test demo/vellum/*.test.cjs` (the counts derived from the data).

Stoa mode, local only: `python3 -I demo/vellum/make_stoa_demo.py --dataset <path to junction-dataset>` copies one
real Swiss Dwellings floor (CC BY 4.0; `--floor`, default `site980_bldg2055_floor9178`) and its answer key into `demo/vellum/stoa/` (gitignored, never commit it).
Serve this folder (`python3 -m http.server 8765` in `demo/vellum/`) and open `http://localhost:8765/stoa/index.html`.
It shows the real drawing, the real questions and the answer key's values, with no marks (the data has no positions)
and the dataset's credit in the footer.

# demo/vellum/: clickable demo of the Vellum redesign

Static HTML, CSS and JS. No build step, no network, no dependencies. Open `index.html` in a browser.

v2 adds file triage as a preview (decision 0010: four synthetic images set aside as not floor plans, with their
register kind, description, the relevance rule, a person's call and "Read it as a floor plan"; all in `triage.js`),
the project's Drawings and Files lists, the issues list (`issues.js`), and a multi-page PDF split into page files.

The whole product story in the Vellum look (Tudor's canvas, boards 1-5 and 9-12): drop files, watch them being read
(simple and advanced views), settle the conflicts, start a new chat over all the drawings, ask with proof and double-check
uncertain answers, see the workspace history. Spec and click map: `../../docs/specs/frontend/clicky-demo.md`.

Everything in it is synthetic. The plans are drawn as SVG by `plan.js` from the one data structure in `data.js`, and
every count, area, conflict value, cross-check and mark on screen is derived from it, so they always agree. File
names, sizes and timings are illustrative, not measured. Nothing from the Stoa dataset is committed in this folder. The
double-check items use the backend's `answer.check` shape (`reason`, `disputed[]` with `mark_id`, `why`, `readers`).

It shows only what the backend has: no country picker, login or user name (a sign-off takes a typed name), no ETA,
no answer grade.

Routes: `#/` drop, `#/ingest` reading (`/unpack`, `/identify`, `/normalise`, `/extract`, `/check` for the advanced panels),
`#/conflicts` (its "Start a new chat" unlocks once every conflict is settled), `#/chat` (the empty project chat with 3 suggested questions;
each answer's "Show it on <file>" opens `#/ask` on that drawing), `#/ask` (no header tab), `#/issues` (the issues list, filters, CSV), `#/file/<n>` (a file's trace; on a file triage set aside, the triage card with its call, undo and "Read it as a floor plan"), `#/workspaces`. Opening a later route directly starts the sample already read.

Check: `node --test demo/vellum/*.test.cjs` (the counts derived from the data).

Stoa mode, local only: `python3 -I demo/vellum/make_stoa_demo.py --dataset <path to junction-dataset>` copies one
real Swiss Dwellings floor (CC BY 4.0; `--floor`, default `site980_bldg2055_floor9178`) and its answer key into `demo/vellum/stoa/` (gitignored, never commit it).
Serve this folder (`python3 -m http.server 8765` in `demo/vellum/`) and open `http://localhost:8765/stoa/index.html`.
It shows the real drawing, the real questions and the answer key's values, with no marks (the data has no positions)
and the dataset's credit in the footer.

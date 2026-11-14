# demo/vellum/: clickable demo of the Vellum redesign

Static HTML, CSS and JS. No build step, no network, no dependencies. Open `index.html` in a browser.

The whole product story in the Vellum look (Tudor's canvas, boards 1-5 and 9-12): drop files, watch them being read
(simple and advanced views), settle the conflicts, ask with proof and double-check uncertain answers, see the
workspace history. Spec and click map: `../../docs/specs/frontend/clicky-demo.md`.

Everything in it is synthetic. The plans are drawn as SVG by `plan.js` from the one data structure in `data.js`, and
every count, area, conflict value, cross-check and mark on screen is derived from it, so they always agree. File
names, sizes and timings are illustrative, not measured. Nothing from the Stoa dataset is in this folder. The
double-check items use the backend's `answer.check` shape (`reason`, `disputed[]` with `mark_id`, `why`, `readers`).

It shows only what the backend has: no country picker, login or user name (a sign-off takes a typed name), no ETA,
no answer grade.

Routes: `#/` drop, `#/ingest` reading (`/unpack`, `/identify`, `/extract`, `/check` for the advanced panels),
`#/conflicts`, `#/ask`, `#/workspaces`. Opening a later route directly starts the sample already read.

Check: `node --test demo/vellum/*.test.cjs` (the counts derived from the data).

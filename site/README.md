# site/: junction.hour49.com, the click-through demo

A Cloudflare Worker (`src/index.js`) that serves the clickable Vellum demo from `assets/` (built by
`build-assets.sh` from `demo/vellum`). The full app is offline for good, so since 2026-11-17 there is no access code
and nothing is proxied (Bogdan: "I only want the clicky html demo to work, I won't keep the main app live", "also
remove the access code"). The access gate that was here from 2026-11-14 is in the git history.

- Every page gets a strip at the top with a "Credits" link (`/credits.html`), which the drawings' licences ask for.
  The strip sits in the page's flow, not in a fixed box over the demo's buttons.
- Only GET and HEAD are served (405 otherwise). `/api/*` answers 410 with a JSON error saying the app is offline.
- The old access code links, `/__unlock` and `/__lock`, redirect to `/`.
- The Worker has no secrets and calls nothing but its own assets.

Back to an earlier version of the Worker: `npx wrangler@4.161.0 versions list`, then
`npx wrangler@4.161.0 versions deploy <version id>@100% -y`.

Tests: `cd site && npm test` (Node's test runner, no dependencies). Locally: `npx wrangler@4.161.0 dev --env preview`.

Build and deploy: `./build-assets.sh`, then `npx wrangler@4.161.0 versions upload` and
`npx wrangler@4.161.0 versions deploy <version id>@100% -y`; the steps are in `.agents/deploy/RUNBOOK.md` (local,
gitignored). `build-assets.sh` needs the Stoa dataset on the machine (`STOA_DATASET=<path to junction-dataset>
./build-assets.sh`, with `PYTHON` set to a Python that has Pillow and pypdfium2 for the house sheets): the demo's
sample is made by `demo/vellum/make_stoa_demo.py` from one Swiss Dwellings floor (CC BY 4.0) with its questions,
which carry the drawing's licence, and sheets of one OpeningDesign house (CC BY-SA 4.0). The recorded examples of
the full app (`demo/vellum/examples.js` and `demo/vellum/examples/`) are committed, since their drawings are not from
the dataset: a public-domain HABS scan, our own drawn flat and two heating sheets rendered from MIT-licensed models.
The credits page is written by `build-assets.sh`. The built `assets/` folder is gitignored.

`public/` is the earlier static placeholder page, kept for reference; the Worker does not serve it.

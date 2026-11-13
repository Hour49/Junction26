# Literature campaign: reading raster floor plans into extraction_v1

Status: ready to start, 2026-11-14 00:05 (Europe/Helsinki). This file is the brief for the research orchestrators.
Workers read [worker-brief.md](worker-brief.md) and one section of [scopes.md](scopes.md).

## Goal

Bogdan, 2026-11-13 about 23:50, verbatim: "I want to launch a very big research campaign for research papers etc
everything. FRom this last message, think for each agents,what the things they should search for. Also look too
look for some of the cutting edge sota things" and "also for all of these, make sure the agents will look for
similar concepts which might traslate well to our use case."

On who runs it, 2026-11-14 00:00, verbatim: "THE RESEARCH ORFHESTRATOR WILL BE A DIFFERENT ONE, WHERE THE
ORCHESTATOR WILL BE A FABLE AGNETS WHICH WILL COLLECT THE FINDINGS AND TRIAGE THEM. MY FABLE ORCHESTRATOR WILL
MANAGE 6/12 AND TUROR'S ORCHESTARTOR THE OHTER 6."

The result is one ranked shortlist of methods for turning a CubiCasa PNG into our JSON: what to train tonight, what
to try on Saturday, what to drop, each with its source.

## Who runs what

Two research orchestrators, separate from the orchestrators that run the build. Each one starts six workers,
reviews their reports and triages them.

| Orchestrator | Scopes | Why these |
| --- | --- | --- |
| Bogdan's research orchestrator (Fable) | L1 field, L4 rooms, L6 scale and areas, L7 vision-language models, L10 confidence, L12 products | rooms, scale and trust feed the answer and proof side that Bogdan's fleet builds |
| Tudor's orchestrator | L2 detection, L3 counting, L5 text, L8 data, L9 sheets, L11 raster to vector | they continue Tudor's CubiCasa, data, hard-image and extraction research, whose reports are on his machine |

Swap scopes if it suits you better; say so on the board first so no scope runs twice. Bogdan's research
orchestrator also merges both triage files into the shortlist.

## Tools on the machine

Check what the machine has before starting workers, and tell them in the prompt if something is missing.

- arXiv MCP server (`arxiv-mcp-server` 0.8.2, user scope): search, download, full text, read by section, citation
  graph. On Bogdan's main machine it is installed for both accounts since 2026-11-13 23:57. Claude Code loads MCP
  servers at session start, so a session older than the install does not have it and a newly started worker does.
  It is not in `tools/setup.sh` yet, so other machines need it installed by hand or use web search.
- Playwright MCP headless browser for public pages that refuse a plain fetch. Owner decision, Bogdan, 2026-11-13:
  "you can use masked headers". At 23:57 its setup on Bogdan's machine was still being tested; confirm it works
  before telling workers to rely on it. The limits are in the worker brief: public pages only, no logins, captchas
  or paywalls.
- Web search and fetch as the fallback everywhere.

## Run it

1. `git pull --ff-only`, the setup check from the root CLAUDE.md, and the tool check above.
2. Post on the board that the campaign has started and which six scopes you run (orchestrators only; Tudor's
   orchestrator learns about its six there).
3. Workers are herdr panes in a workers tab, one scope each, on Sonnet (read-only work). Prompt each one:
   "You are lit-<name>. Read docs/research/lit-campaign/worker-brief.md and section L<n> of
   docs/research/lit-campaign/scopes.md and do it. Never the board." If Tudor's earlier reports cover part of a
   scope (data, hard images, extraction), give that worker the report path so it extends them.
4. Register the run (`orch run start`) and keep one `orch wait`.
5. Publish on your own branch (`research/lit-<login>`) and open one PR per round. Two people's orchestrators never
   commit to the same branch.

## Review each report

A finished report is a claim, not a finding. Before accepting it:

- Open the sources of its top 5 yourself and check that the numbers, licences and training data are what the report
  says. Reject anything cited from memory.
- Check the leakage flag on every pretrained checkpoint (CubiCasa5K in its training data).
- Check that the transfer notes say what would break on our images. "Should work" with no reason goes back.
- One follow-up round per worker at most. After that, take what holds and note what was left unchecked.

Accepted reports go to `reports/<name>.md` in this folder. They are public: no partner data, no file names from the
dataset, no personal data.

## Triage

Score every candidate on the same five questions:

1. Evidence: measured on raster floor plans, measured in an adjacent field, or only claimed?
2. Allowed: code licence, weights licence, no CubiCasa5K leakage?
3. Fits: one 12 to 16 GB GPU, a first number by Saturday 12:00, running by Saturday 22:00?
4. What it moves. Points of the total score still open on CubiCasa, from the dev split (English questions,
   2026-11-13): windows and doors about 11, sinks, toilets and showers about 8, room types from labels about 9,
   plans per sheet about 1.5. Scale and areas move no score; they serve the product and the demo.
5. Cost: hours of a person or an agent, and GPU hours.

Then sort into four groups: train or try tonight; try on Saturday; idea or pitch material only; drop, with the
reason. Merge duplicates across workers, and where two reports disagree, read both sources and say which holds.

## What comes out

| File | Who writes it | When |
| --- | --- | --- |
| `reports/<name>.md`, 12 files | the worker, published by its orchestrator after review | start + 75 min |
| `triage-<login>.md`, one per orchestrator | each research orchestrator | start + 105 min |
| `SHORTLIST.md` | Bogdan's research orchestrator, from both triage files; Tudor's orchestrator reviews it in the PR | start + 135 min |

The shortlist is what the build orchestrators act on. It names, per JSON field, the first method to try, the
fallback, the experiment that would settle the choice, and the source of every claim.

## Limits

- The campaign reads and ranks. It does not train, download datasets or weights, call paid APIs or send any drawing
  to a model endpoint. Experiments are proposed in the shortlist and run by the build fleets under records 0003 and
  0006.
- It does not block the build. A detector trained on the dev boxes, scored on a held-out part of dev, is the
  obvious first experiment and can start before the shortlist exists.
- The sealed eval split stays sealed: nothing here needs it.

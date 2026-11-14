# Junction26

Team Hour49's project repo for Junction 2026. Project not picked yet. MIT licensed, see [LICENSE](LICENSE).

- Agents: read [CLAUDE.md](CLAUDE.md) first (setup check, board, git rules).
- Project code: engineering standard [docs/ENGINEERING.md](docs/ENGINEERING.md), QA plan [docs/QA.md](docs/QA.md).
- Experiments: what we tried on the CubiCasa raster track and what it gave, [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).
- Orchestrator board: issues labelled `board` in this repo, used through `tools/board`.

## Key values

The product has to respect these six values, in this order (team notes, 2026-11-13). Every feature, answer and
demo screen gets checked against them.

1. Transparency. Each answer highlights the file it came from and the place in that file where it was found
   (page and box), so a person can check it.
2. Confidence. Each answer says how sure the system is.
3. Conflicts. When sources disagree, the system shows the conflict and does not quietly pick one side.
4. Rules. Answers are checked against the building code of the country the project is in.
5. Abstention. When the evidence is too weak, the system says it does not know instead of guessing.
6. UX. The screens make all of the above easy to see and act on.

The flow these values imply: ingest → AI decision (a decision model) → the conflicts it found (for example
"5 conflicts") → how each one was resolved.

## The product

Drawing Q&A for construction projects. A surveyor drops a project, asks questions about it, and gets answers
that show where on the drawing they came from. In the order a user meets it:

1. Upload. A zip, or single PDFs, images, IFC models and DXF files ([docs/API.md](docs/API.md), upload limits
   under "Conventions").
2. File triage. Each image is first sorted as a floor plan or not. A file that is not a plan is set aside, kept,
   and described in words. A person can still ask for it to be read as a plan
   ([decision 0010](docs/decisions/0010-file-triage.md)).
3. Reading, one route per kind of file: a drawn PDF is read from its vectors, an image (scan, photo, sketch) by
   detectors and a room reader, an IFC model through its own objects. Every drawing keeps a list of what was
   looked for, so a missing class is "not read" and never a silent zero ([docs/PIPELINE.md](docs/PIPELINE.md)).
4. Ask with proof. A question in plain words (11 languages) gets a value with its unit, marks on the plan page,
   the method that produced it, and the credit for any licensed data. The model's score is never shown as a
   percentage. Where the evidence is too weak the answer says it does not know.
5. Double-check requests. An answer the system cannot certify asks a person to look: it shows the disputed
   marks, and the person signs it off or fixes it. It does not guess quietly
   ([spec](docs/specs/frontend/double-check.md)).
6. Conflicts and located issues. Where two readings of one quantity disagree, both values are shown. Conflicts,
   refused answers, reading flags and set-aside files make one list of located issues (file, page, box, one
   sentence of why), exported as JSON, CSV or a zip with the pages marked
   ([decision 0008](docs/decisions/0008-located-issues.md)).
7. Building-code pre-check, for Finland and the canton of Zürich. "A pre-check of a few rules, not a compliance
   certificate." The failed checks join the issues list.

Status on main, 2026-11-14: steps 1 to 4 and 6 are merged. The double-check request (#129) and the rule packs
for the pre-check (#139) are not in the backend on main yet; the screens for both are merged and read the API
fields once they land. Details of what we tried and what it gave: [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).
Golden-set method and results: [docs/GOLDEN.md](docs/GOLDEN.md). Known issues: [docs/KNOWN.md](docs/KNOWN.md).
All decision records: [docs/decisions/](docs/decisions/README.md).

### Run it

No keys needed. Without them the vector PDF and IFC readers run, and the rest use do-nothing stand-ins, so
`GET /api/info` says `no_keys: true`. Needs Python 3.13 with uv, and Node 24 for the frontend.

```bash
# backend (http://127.0.0.1:8000)
cd backend && uv sync --locked
uv run python scripts/make_sample_archive.py     # the synthetic sample project, into data/samples/ (gitignored)
uv run uvicorn app.main:create_app --factory

# frontend (second terminal; /api goes to BACKEND_URL, default http://127.0.0.1:8000)
cd frontend && npm ci && npm run build && npm run preview     # http://127.0.0.1:4173
```

On the home page, "Try the sample project" ingests the synthetic archive: 11 files, five drawings, no partner
data. With no keys, 3 files are ready, 4 flagged, 2 set aside and 2 text only
([docs/QA.md](docs/QA.md) has the golden path). `tools/qa-env.sh <commit> [port] --frontend` exports a commit
and runs it with the demo config. Guides: [backend/README.md](backend/README.md),
[frontend/README.md](frontend/README.md).

What needs a key: the Gemini readers (`GEMINI_API_KEY`: rooms on images and photos, the count distributions behind
the confidence, the sheet-kind signal) and the EU open-model alternative (`EU_VLM_*`). Put keys only in the
gitignored `backend/.env` (template: `backend/.env.example`). What runs fully local: the vector PDF reader, the IFC
reader, the second count, the question parser, the dev answer prior, and the detectors when their weights are in
`data/models`.

Verified 2026-11-14: `uv sync --locked`, `make_sample_archive.py`, the backend start, `GET /health`, `GET /api/info`
and `POST /api/projects/sample?fresh=true` (project `done` in 440 ms, no keys). Not run: the frontend commands
(`npm ci` failed, the disk was full) and `tools/qa-env.sh`.

### Numbers

- Golden v2, whole pipeline, run from a clean export of commit bd2471f: 2717 of 2948 answers right (92.2%), 92.9%
  on the holdout questions, 4.5% abstained. The dev column is in-sample because of the dev prior, so the holdout
  is the honest one. The series is in [docs/GOLDEN.md](docs/GOLDEN.md).
- CubiCasa test split, read once for the shipped config C: 85.0% exact (5708 of 6718), 95% CI [83.4, 86.5],
  against 56.3% for the train prior ([docs/EXPERIMENTS.md](docs/EXPERIMENTS.md)).
- Double-check, validation numbers: TODO(#129 lands, from docs/GOLDEN.md).
- Test-read numbers: TODO(test read).

### Limits

- On an image, areas come from an estimated scale (`RASTER_SCALE=priors`) and are labelled estimates. One can
  be far off while printing a narrow band (K5 in [docs/KNOWN.md](docs/KNOWN.md): +74%, +100% and -37% on three
  golden rooms).
- On plans without printed room labels the reader types rooms by furniture, while the gold labels only count
  what is printed: "bedrooms" can be 0 on a plan that shows beds (EXPERIMENTS.md).
- Windows stayed at about 45-55% in every track we tried (EXPERIMENTS.md).
- Schedules are read on gold drawings only; the vector extractor reads no tables yet (backend/README.md).
- No login: the sign-off name is typed by the surveyor (decision 0001), and the API is for localhost or a private
  network only.
- The building-code pre-check covers a few rules in two places. It is not a compliance check.

## Stoa: golden set and eval

Stoa's challenge is to answer questions about construction drawings and BIM models, and to show where each answer
came from. The judges weigh four things equally: accuracy, how well the reasoning is shown, creativity and low
inference cost. Our golden set is the fixed exam we grade every version of our system against, using Stoa's own
answers and scoring rules.

```text
questions.jsonl (Stoa: 127,044 questions with answers)
   ├── split by drawing/building ──► dev 80%  (build and tune on this)
   │                                 eval 20% (sealed: scored only at milestones)
   └── golden set (small stratified sample: dev items from the 80%, holdout items from the 20%)

our system ──► answers.jsonl (one line per question) ──► stoa_eval score ──► report + results history
```

1. Data. `tools/fetch_stoa_data.py` downloads the dataset into the gitignored `data/` folder (see
   [data/README.md](data/README.md)). Partner data never enters the repo.
2. The answers we grade against. Each line of `questions.jsonl` has a file, a question, the expected answer, a
   unit and a type (count, area, length, volume, text). We take Stoa's answer as correct. Our review of the dataset
   found it reliable. Ambiguous or likely-wrong items get tagged and are kept out of the headline score.
3. Splits. 20% of all questions form a sealed eval split, chosen by drawing, building or model, so translations
   of a question and the floors of one building stay on one side. Build and tune only on the 80% dev split. Score
   eval at milestones, to catch overfitting. Today: 101,651 dev and 25,393 eval questions (decided 2026-11-13).
4. The golden set. A small fixed sample that covers every source, question type and language, plus the known
   traps (rotated plans, sheets with several plans, 1:200 scale, rooms with cut-outs, ...). It is small because
   vision and LLM answers cost money per question. Free parsers are scored on all questions. v1 has 152 questions
   (107 dev, 45 holdout from the eval split).
5. What our system writes. One answer_v1 line per question ([decision 0002](docs/decisions/0002-answer-format.md)):
   ```json
   {"id": 89501, "answer": 212.41, "unit": "m2",
    "evidence": [{"file": "data/swiss_dwellings/....pdf", "page": 1, "box": [0.31, 0.22, 0.38, 0.29]}],
    "method": "pdf-vector", "cost_usd": 0.0, "latency_s": 0.04}
   ```
   `answer` is graded for accuracy. `evidence` boxes (page fractions) show where on the drawing the answer came from.
   `cost_usd` and `latency_s` cover the cost criterion.
6. Scoring (Stoa's rules). Counts must be exact. Areas, lengths and volumes pass within 2%, and only m↔ft and
   m²↔ft² are converted. On the golden set a missing answer is wrong; against all, dev or eval questions the report
   gives coverage and accuracy on the answered ones. Free text needs an exact match for now. The report breaks
   accuracy down by source, type and template, and adds evidence coverage, cost and latency.
7. Baselines. `oracle` (Stoa's own answers) must score 100%, which proves the plumbing. `constant` (the most
   common answer per question template, learnt from dev) scores 15.8% on golden v1, and any real method has to beat
   it.
8. Results history. Every scored run is recorded by default as one summary file (time, commit, method, split,
   accuracy per source and type, coverage, cost, latency; no questions or answers) in [eval/results/runs/](eval/results/runs/),
   so we can show how we improved; `--no-record` is for scratch checks. `stoa_eval history` prints the runs,
   `--progress` shows first vs latest vs best per method, `--csv` exports them for a chart.

```bash
cd eval
uv run python -m stoa_eval split                  # sealed 80/20 split into data/stoa/split/ (same hashes everywhere)
uv run python -m stoa_eval select                 # build the golden set into data/stoa/golden/
uv run python -m stoa_eval baseline oracle        # or: constant
uv run python -m stoa_eval score <answers.jsonl> --against dev --name <method>   # grade it; the run is kept
uv run python -m stoa_eval history                # every recorded run, oldest first
```

More in [eval/README.md](eval/README.md). First real methods: [prototypes/pdf-extract/](prototypes/pdf-extract/README.md)
answers swiss and ifc_models questions from the PDF alone, with no model call (99.91% on swiss counts, 99.97% on swiss
areas, 96.99% on ifc_models room areas; tuned on all questions, so not a held-out result).

## Agent setup

New machine: install Claude Code, gh, herdr, python3, git, jq and uv, clone this repo (we use `~/Repo/Junction26`,
any path works), then run `tools/setup.sh`. It writes the team rules into your global `~/.claude/CLAUDE.md` (in a
marked block; your own text stays) and installs the rest, including the context-handoff hook and `orch`. Safe to
rerun after every pull.

- [docs/TEAM-AGENTS.md](docs/TEAM-AGENTS.md): how each of us runs Claude Code agents (herdr orchestrator and workers,
  the context-handoff hook) and how our orchestrators talk to each other on the GitHub board.
- `tools/board`: the board CLI (`board read`, `board post`, `board wait`, ...). Tests: `uv run --no-project --with pytest pytest -q tools`.
- `tools/waitw.sh`: wait for one herdr worker pane to finish a turn (arm it before prompting). Only needed where
  `orch` is missing; `orch wait` watches all workers at once.
- `tools/claude-acc`: run Claude Code as account N (`claude-acc 2 ...`), sharing settings and hooks.
- `tools/secretary.md`: role card for the team secretary agent (keeps the `team status` issue current, flags stale
  requests and conflicts; no authority). How to run it: docs/TEAM-AGENTS.md section 6.8.
- `tools/setup.sh`: one-command install (global CLAUDE.md block, settings, hook, herdr skill, tool links).
- `templates/`: `team-claude.md` (the team rules setup installs) and `personal-claude.md` (the per-person stub).
- `.agents/` is gitignored: each person's agent briefs, reports and orchestrator handoff stay on their machine.

## Pitch kit and research

[junction-pitch/](junction-pitch/README.md): event facts and rules, playbooks, reference pitches, research folders,
pitch drafts, and the pitch skills (`.claude/`; open Claude Code in that folder to use them). The team folder
`junction-pitch/05-team/` is private and gitignored here: copy it from Hour49/junction-26-prep for the team skills.

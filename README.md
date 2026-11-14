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

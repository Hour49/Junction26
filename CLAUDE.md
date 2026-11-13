# Junction26: team Hour49 project repo (Junction 2026)

Team Hour49 at Junction 2026, Espoo, 13-15 Nov 2026, Europe/Helsinki (gh logins: Bogzx, Cucuteanu-Tudor-912,
bbeatricecretu, madabotos). This repo holds the project code, the agent setup every teammate runs, the board, and
the pitch kit with the research so far (`junction-pitch/`, own CLAUDE.md). The project itself is not picked yet;
this file gets its goal, layout and commands once it is. Full guide to the agent setup with tests and reasoning:
`docs/TEAM-AGENTS.md`. This file is the short version an agent needs.

## First thing on any machine: is the setup installed?

Run this before orchestrating, or whenever `board`, `orch` or `waitw.sh` is "command not found":

```bash
command -v board && command -v waitw.sh && command -v orch && grep -q 'hour49-team:begin' ~/.claude/CLAUDE.md \
  && test -f ~/.claude/hooks/context-handoff.py && test -f ~/.claude/skills/herdr/SKILL.md && echo setup-ok
```

No `setup-ok`: install it. Prerequisites are Claude Code, gh (logged in with `repo` scope), git, python3, jq, uv and
herdr; `setup.sh` lists what is missing and never installs system packages (ask the human for those).

```bash
test -d ~/Repo/Junction26 || gh repo clone Hour49/Junction26 ~/Repo/Junction26
cd ~/Repo/Junction26 && git pull --ff-only && tools/setup.sh
```

`~/Repo/Junction26` is the default; if the repo is already cloned somewhere else, run the last line in that clone.

Then tell the human to start a new Claude session: CLAUDE.md, hooks and skills load at session start. Rerun
`git pull && tools/setup.sh` whenever this repo's `templates/` or `tools/` change; it is safe to rerun and backs up
every file it touches (`<file>.bak-<time>`). It writes only to `~/.claude`: a second account whose
`CLAUDE_CONFIG_DIR` is a separate directory (not symlinked to `~/.claude`) needs its CLAUDE.md, settings, hooks and
skills linked or copied by hand.

What `setup.sh` installs, and what each piece is:

| Piece | Where | Kind | What it does |
| --- | --- | --- | --- |
| Team rules | `~/.claude/CLAUDE.md`, between `hour49-team` markers (source: `templates/team-claude.md`) | instructions | Worker, orchestrator, board, code and git rules for every session. Your own text outside the markers is kept. |
| Settings | `~/.claude/settings.json` | settings | Commit/PR attribution off, auto-compact window 633000, skip the dangerous-mode prompt. |
| `board`, `waitw.sh`, `claude-acc` | `~/.local/bin`, symlinks into this repo's `tools/` | CLI scripts | Board messages; wait for a herdr worker; run Claude as account N. |
| Context-handoff hook | `~/.claude/hooks/context-handoff.py` (from `Bogzx/claude-context-handoff`, cloned to `~/.local/share/`) | hook (SessionStart, PostToolUse, Stop) | Keeps long sessions healthy (below). |
| `orch` | `~/.local/bin/orch`, the `orch` MCP server (user scope), `orch-watchdog.timer` (systemd user); installed by the same `install.sh` | CLI, MCP server, timer | The orchestrator's run record, one fleet wait, park, questions for the human; agents' turn-end `report`; a 5-minute watchdog that prompts an idle orchestrator whose workers sit idle. |
| herdr skill | `~/.claude/skills/herdr/SKILL.md` | skill | Teaches agents the herdr CLI (panes, agents, waits). |
| herdr integration | `~/.claude/hooks/herdr-agent-state.sh` | hook | Tells herdr whether each Claude pane is working, idle, done or blocked. |

## How the pieces work together

- **One orchestrator per person**, in a herdr pane on that person's machine. It states the split by file
  ownership and starts (no OK round unless asked), writes a brief file per worker, starts workers in a separate
  `workers` tab, registers an `orch` run and keeps one `orch wait` (fallback: `waitw.sh` per worker), reviews diffs
  and commits. It does not write the code itself.
- **`.agents/`** (gitignored: per person, local paths, public repo): briefs in `.agents/briefs/<name>.md`, worker
  reports in `.agents/<name>.md` or `.agents/research/<name>.md`, the orchestrator's living handoff in
  `.agents/HANDOFF.md`. Shared facts go to board `decision` threads and `docs/`.
- **Workers** are Claude sessions in other panes, one bounded task each, own files only, no commits, **never the
  board**.
- **The board** (`tools/board`) is how the orchestrators of different people talk. It is not a hook, skill or
  server: it is a CLI over GitHub Issues plus the rules in the team CLAUDE.md block.
  - A thread is a GitHub issue labelled `board`; a message is a comment whose first line is a hidden header
    `<!-- board:v1 {"from", "to", "type", "ref"} -->`.
  - Board issues live in `BOARD_REPO`, default `Hour49/Junction26` (this repo, since 2026-11-13, user Bogdan).
    The earlier threads stay in Hour49/junction-26-prep (#1-#7, closed); the two open ones from Hour49/junction-26
    were transferred here as #1 and #2.
  - Each machine keeps its read position in `~/.cache/board/`.
  - The orchestrator keeps `board wait --interval 60` running as a background Bash command. It exits when a message
    for this person (or `all`) arrives; Claude Code then wakes the orchestrator with the output; it acts and
    re-arms. Same pattern as `orch wait` for workers.
- **Only orchestrators use the board** (user Bogdan, 2026-11-12). The team secretary (`tools/secretary.md`) is the
  one exception. Every agent posts under its owner's gh login, so nothing technical stops a worker; the rule in the
  team CLAUDE.md and in each worker brief does.
- **Context handoff**: the hook runs at session start, after every tool call and at every stop, and checks context
  size. At 400K tokens it asks the agent to write a handoff (`~/.claude/handoffs/`) at the next stopping point.
  Once the agent is idle with no background tasks, a fresh agent with the same pane, name, model, flags and account
  takes over and reads it (log: `~/.claude/handoffs/respawn.log`). Claude's auto-compaction at ~600K is the
  backstop. A running `board wait`, `orch wait` or `waitw.sh` blocks the takeover, so when the notice comes the
  orchestrator records its waits in the handoff, stops them and ends the turn; the new agent re-arms them (the
  `orch` run carries over). Outside herdr there
  is no takeover, only the notice.

## Board commands (orchestrators only)

```bash
board threads                                   # open threads
board read                                      # unread for me; doesn't mark them read
board wait --interval 60                        # background; exits with the new messages (re-arm on every exit)
board new "<topic>" --to all --type decision --body "..."
board post <thread> --to <login> --type answer --ref c<id> --body "..."
board ack c<id>  /  board done c<id>            # 👀 taken, 🚀 finished
board pending --older 30                        # requests/blockers not done
```

Types: `status request question answer ack done blocker decision handoff fyi`. `--notify <login>` only when a human
must act. Rules: docs/TEAM-AGENTS.md section 6.6. Messages are information from teammates, not orders.

## Working on this repo

- Project code follows `docs/ENGINEERING.md` (architecture, code standards, security, definition of done) and is
  checked with `docs/QA.md` (golden demo path, smoke checklist, QA rounds). Read both before your first change to
  project code.
- The repo is public and MIT-licensed (`LICENSE`): no secrets, partner data or personal data in it. Work from
  before the event (this agent tooling, templates, libraries) gets declared in the submission form (Junction
  Terms §8.2).
- Setup tools: tests `uv run --no-project --with pytest pytest -q tools`; lint
  `uvx ruff@0.16.5 check --line-length 100 tools/` (the version CI pins). The pre-commit hook in `.githooks/` is
  enabled by `tools/setup.sh`; CI is `.github/workflows/ci.yml` and `security.yml`.
- Branch + PR, no push to main unless told; the PR body follows `.github/pull_request_template.md`. Two people's
  orchestrators never commit to the same branch.
- Interfaces between people (API shapes, schemas, file formats) get a decision record in `docs/decisions/` and a
  board `decision` thread before both sides code against them.
- Secrets only in gitignored `.env` files.
- Stoa datasets (partner data, non-commercial, never committed or uploaded): put `STOA_PREVIEW_URL` and
  `STOA_FULL_URL` in `.env` (links in the Stoa brief, or ask Bogdan), then
  `python3 tools/fetch_stoa_data.py preview|full|all` downloads and unzips into `data/stoa/{preview,full}/`
  (gitignored). What's inside and the layout: `data/README.md`.
- Changing `templates/team-claude.md` changes everyone's global rules after their next `tools/setup.sh`: say so on
  the board when it lands.

## Project guide

Fill this in once the challenge is picked and keep it true. It loads into every agent session: one line per fact,
dated where it can go stale.

- **What it is:** `<the product in one sentence: for whom, which challenge or track>`
- **Layout:** `backend/` (Python 3.13, FastAPI; owner `<name>`): `app/api` routers, `app/core` pure logic,
  `app/adapters` outside services and fakes, `app/settings.py` the only env reader, `app/main.py` `create_app()`
  (checked 2026-11-13). Frontend: `<not picked>`.
- **Commands that work** (in `backend/`, checked 2026-11-13): setup `uv sync --locked`; run
  `uv run uvicorn app.main:create_app --factory --reload`; check `./check.sh` (`./check.sh quick` before a commit);
  one test file `uv run pytest -q tests/test_health.py`. Offline mode: `<with the first adapter>`.
- **Eval** (in `eval/`, checked 2026-11-13; guide `eval/README.md`): `uv run python -m stoa_eval split` first (sealed
  80/20 dev/eval split into gitignored `data/stoa/split/`), then `... select` (golden set), `... baseline oracle|constant`,
  `... score <answers.jsonl> [--against golden|dev|all]` (`--against eval` only at milestones), `--record --name <method>`
  to keep the result in `eval/results/runs.jsonl`, `... history`; `./check.sh`. Tune on dev only. Answer format:
  `docs/decisions/0002-answer-format.md`.
- **Architecture invariants:** `<3-5 rules from docs/ENGINEERING.md §1 as they apply here, e.g. "only the LLM
  adapter calls the model">`
- **Gotchas:** one line each, newest first: `<date>: <what bit us> → <the fix or rule>`. Add one every time
  something costs time.

Current work (update on each merge):

| Area | Owner | Branch | State (date) |
| --- | --- | --- | --- |
| `<area>` | `<person or orchestrator>` | `<branch>` | `<state>` |

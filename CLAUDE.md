# Junction26: team Hour49 project repo (Junction 2026)

Team Hour49 at Junction 2026, Espoo, 13-15 Nov 2026, Europe/Helsinki (gh logins: Bogzx, Cucuteanu-Tudor-912,
bbeatricecretu, madabotos). This repo holds the project code, the agent setup every teammate runs, the board, and
the pitch kit with the research so far (`junction-pitch/`, own CLAUDE.md). The project itself is not picked yet;
this file gets its goal, layout and commands once it is. Full guide to the agent setup with tests and reasoning:
`docs/TEAM-AGENTS.md`. This file is the short version an agent needs.

## First thing on any machine: is the setup installed?

Run this before orchestrating, or whenever `board` or `waitw.sh` is "command not found":

```bash
command -v board && command -v waitw.sh && grep -q 'hour49-team:begin' ~/.claude/CLAUDE.md \
  && test -f ~/.claude/hooks/context-handoff.py && test -f ~/.claude/skills/herdr/SKILL.md && echo setup-ok
```

No `setup-ok`: install it. Prerequisites are Claude Code, gh (logged in with `repo` scope), git, python3, jq, uv and
herdr; `setup.sh` lists what is missing and never installs system packages (ask the human for those).

```bash
test -d ~/Repo/Junction26 || gh repo clone Hour49/Junction26 ~/Repo/Junction26
cd ~/Repo/Junction26 && git pull --ff-only && tools/setup.sh
```

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
| herdr skill | `~/.claude/skills/herdr/SKILL.md` | skill | Teaches agents the herdr CLI (panes, agents, waits). |
| herdr integration | `~/.claude/hooks/herdr-agent-state.sh` | hook | Tells herdr whether each Claude pane is working, idle, done or blocked. |

## How the pieces work together

- **One orchestrator per person**, in a herdr pane on that person's machine. It splits work by file ownership,
  writes a brief file per worker, starts workers in sibling panes, waits on them with `waitw.sh`, reviews diffs and
  commits. It does not write the code itself.
- **Workers** are Claude sessions in other panes, one bounded task each, own files only, no commits, **never the
  board**.
- **The board** (`tools/board`) is how the orchestrators of different people talk. It is not a hook, skill or
  server: it is a CLI over GitHub Issues plus the rules in the team CLAUDE.md block.
  - A thread is a GitHub issue labelled `board`; a message is a comment whose first line is a hidden header
    `<!-- board:v1 {"from", "to", "type", "ref"} -->`.
  - Board issues live in `BOARD_REPO`, default `Hour49/Junction26` (this repo, since 2026-11-13, user Bogdan).
    The earlier threads stay in Hour49/junction-26-prep (#1-#7, closed).
  - Each machine keeps its read position in `~/.cache/board/`.
  - The orchestrator keeps `board wait --interval 60` running as a background Bash command. It exits when a message
    for this person (or `all`) arrives; Claude Code then wakes the orchestrator with the output; it acts and
    re-arms. Same pattern as `waitw.sh` for workers.
- **Only orchestrators use the board** (user Bogdan, 2026-11-12). The team secretary (`tools/secretary.md`) is the
  one exception. Every agent posts under its owner's gh login, so nothing technical stops a worker; the rule in the
  team CLAUDE.md and in each worker brief does.
- **Context handoff**: the hook runs at session start, after every tool call and at every stop, and checks context
  size. At 400K tokens it asks the agent to write a handoff (`~/.claude/handoffs/`) at the next stopping point.
  Once the agent is idle with no background tasks, a fresh agent with the same pane, name, model, flags and account
  takes over and reads it (log: `~/.claude/handoffs/respawn.log`). Claude's auto-compaction at ~600K is the
  backstop. A running `board wait` or `waitw.sh` blocks the takeover, so when the notice comes the orchestrator
  records its waits in the handoff, stops them and ends the turn; the new agent re-arms them. Outside herdr there
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

- Setup tools: tests `uv run --no-project --with pytest pytest -q tools`; lint
  `ruff check --line-length 100 tools/`.
- Branch + PR, no push to main unless told. Two people's orchestrators never commit to the same branch.
- Interfaces between people (API shapes, schemas, file formats) go in a board `decision` thread and in a doc here
  before both sides code against them.
- Secrets only in gitignored `.env` files.
- Changing `templates/team-claude.md` changes everyone's global rules after their next `tools/setup.sh`: say so on
  the board when it lands.

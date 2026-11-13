# Junction26

Team Hour49's project repo for Junction 2026. Project not picked yet.

- Agents: read [CLAUDE.md](CLAUDE.md) first (setup check, board, git rules).
- Orchestrator board: issues labelled `board` in this repo, used through `tools/board`.

## Agent setup

New machine: install Claude Code, gh, herdr, python3, git, jq and uv, clone this repo to `~/Repo/Junction26`, then
run `tools/setup.sh`. It writes the team rules into your global `~/.claude/CLAUDE.md` (in a marked block; your own
text stays) and installs the rest. Safe to rerun after every pull.

- [docs/TEAM-AGENTS.md](docs/TEAM-AGENTS.md): how each of us runs Claude Code agents (herdr orchestrator and workers,
  the context-handoff hook) and how our orchestrators talk to each other on the GitHub board.
- `tools/board`: the board CLI (`board read`, `board post`, `board wait`, ...). Tests: `uv run --no-project --with pytest pytest -q tools`.
- `tools/waitw.sh`: wait for a herdr worker pane to finish a turn (arm it before prompting).
- `tools/claude-acc`: run Claude Code as account N (`claude-acc 2 ...`), sharing settings and hooks.
- `tools/secretary.md`: role card for the team secretary agent (keeps the `team status` issue current, flags stale
  requests and conflicts; no authority). How to run it: docs/TEAM-AGENTS.md section 6.8.
- `tools/setup.sh`: one-command install (global CLAUDE.md block, settings, hook, herdr skill, tool links).
- `templates/`: `team-claude.md` (the team rules setup installs) and `personal-claude.md` (the per-person stub).

## Pitch kit and research

[junction-pitch/](junction-pitch/README.md): event facts and rules, playbooks, reference pitches, research folders,
pitch drafts, team profiles, and the pitch skills (`.claude/`; open Claude Code in that folder to use them).

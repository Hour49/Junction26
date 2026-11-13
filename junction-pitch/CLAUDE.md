# Junction 2026 pitch kit (team Hour49) — research, marketing, pitching. No app code here.

Owner: Madalina, team lead and presenter. Event: Junction 2026, Espoo, Fri 13 – Sun 15 Nov 2026 (Europe/Helsinki).
Start with README.md. Event facts: 00-event/junction-info.md. Methods: 01-playbooks/.

## Single source of truth
- `04-pitch/core.md` holds the current idea: one-liner, user, problem + number, solution, why now, differentiation, demo moment, ask.
  Every pitch, slide and text is drafted FROM core.md. When the idea changes, update core.md first, then regenerate.
- `03-research/sources.md`: one line per fact used anywhere (format in 03-research/README.md).
- `03-research/feedback/log.md`: every piece of mentor/peer/jury feedback (use /feedback).

## Rules for every skill and agent
- Real data only. Every claim has a URL + access date, or is a clearly labelled estimate built from real cited numbers.
  Label numbers measured / reported / assumed. Single-source or inferred = UNVERIFIED. Never invent quotes, users, numbers or companies.
- Plain, common English (Madalina's audience includes non-native speakers). Short sentences. No buzzwords.
- Write results to files in this folder (kebab-case names, template in 03-research/README.md); reply in chat with a short summary + file paths.
- Parallel research: launch subagents in ONE message so they run concurrently; each writes its own file; then synthesise.
- At most 5 agents per skill run (Madalina, 2026-11-10: save usage for the builders). Need more coverage? Give each
  agent more items, never a 6th agent.
- Never overwrite a human-edited file without asking; write a new version (`-v2`) instead.
- Partner raw data and secrets never go in this folder. Never post kit content outside the repo.

## Skills (slash commands)
/challenge-pick · /pain-points · /market-scan · /feedback · /fact-check · /deck · /pitch · /easy-pitch · /pro-pitch · /jury-drill · /team-intro · /video-idea
See .claude/skills/<name>/SKILL.md. Held items and later work: TODO.md.

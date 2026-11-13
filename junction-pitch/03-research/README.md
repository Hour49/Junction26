# 03-research: weekend research

Empty until the challenge is chosen (Fri 13 Nov, evening). The method is in [../01-playbooks/market-research.md](../01-playbooks/market-research.md); this folder holds the output.

| Folder | What goes there | Playbook section |
|---|---|---|
| [challenges/](challenges/) | One file per candidate challenge: brief, rubric, data given, partner contacts, our fit | §0 "Read the rubric first", §7 |
| [competitors/](competitors/) | Existing products and past Junction projects that solve the same thing | §1 |
| [users/](users/) | Proto-personas, jobs to be done, interview log (`interviews.md`) | §2 |
| [market/](market/) | Market size (bottom-up and top-down) and problem size, the "one number" | §3, §4 |
| `sources.md` | Create it on Friday. One line per fact used anywhere in the pitch (format below) | §0 |

## Rules for every file here

- **Sources required.** Every claim has a URL and an access date. No source, no claim.
- **Label every number** as one of:
  - **measured**: we measured it ourselves (demo run, our test, the partner's data);
  - **reported**: someone else published it (cite them);
  - **assumed**: our assumption (state the reasoning).
- Mark single-source or inferred items **UNVERIFIED**.
- Partner raw data never goes in this folder or any public repo. Write down where it lives instead.
- File names are kebab-case: `<topic>.md`, e.g. `competitors/valio-aimo-order-picking.md`.

## `sources.md` line format

```
claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence
```

Every number on a slide must trace back to a line in `sources.md`.

## File template (copy for each new research file)

```markdown
# <Topic>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: <name or agent>
- Question: <the one question this file answers>
- Answer in one line: <answer>

## Findings
- <finding> — <number> (<measured|reported|assumed>) — [source](URL), accessed YYYY-MM-DD

## What this means for the pitch
- <one or two bullets: which slide or answer this feeds>

## Open questions / UNVERIFIED
- <item>
```

## Folders written by the skills
| Folder / file | Skill |
|---|---|
| `challenges/` | /challenge-pick |
| `pain-points/<problem-slug>/` | /pain-points |
| `competitors/`, `users/`, `market/`, `market-scan-summary.md` | /market-scan |
| `feedback/log.md`, `feedback/followups/`, `feedback/summary-*.md` | /feedback |
| `fact-check/<timestamp>/` (working files; report is `04-pitch/fact-check-report.md`) | /fact-check |
| `sources.md` | created by the first skill that needs it; append-only |

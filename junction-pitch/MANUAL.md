# Skills manual (short)

Open Claude Code in this folder first: `cd <your clone>/junction-pitch && claude`. Type a command, then words after it.
Messy words are fine ("partner valio", "tech for the verda guy"). Every skill reads `04-pitch/core.md` (the idea).
Most skills never overwrite: you get `-v2`, `-v3` files. Max 5 agents per run.

## Friday night, in this order

| # | When | Type this |
|---|---|---|
| 1 | Briefs are out (18:00) | `/challenge-pick <names or pasted briefs>` |
| 2 | Idea chosen | fill `04-pitch/core.md`, then `/market-scan` and `/pain-points` |
| 3 | Night | `/deck`, `/pitch stage`, `/easy-pitch` |
| 4 | Before showing anything | `/fact-check --quick` |
| Sat–Sun | After every talk | `/feedback <who>: <notes>` |

## The 12 skills

### Research

**/challenge-pick**: which challenge to take. Ranks them and gives questions for the partner reps.
- `/challenge-pick valio, espoo, s-pankki` (names, pasted briefs, or a file path)
- More than 3 challenges: it makes a shortlist of 3 and stops. Reply `go` (or `swap X for Y`) for the deep pass.
- `/challenge-pick shortlist`: deep pass on the saved shortlist.
- Add `quick` for half the searching. Add `weights: fit 30 ...` to change what counts most.

**/market-scan**: competitors, similar ideas, target user, market size, problem size. Suggests core.md changes, never edits it.
- `/market-scan` (idea from core.md) · `/market-scan smart grocery substitutions` · `/market-scan --quick` (3 agents, ~15 min)

**/pain-points**: real people with this problem: research and statistics, news, app and review sites, open forums (Hacker News, Suomi24…), complaint data. No logins; Reddit, X and LinkedIn are not used. Quotes with links + a STRONG / MEDIUM / WEAK verdict (~5–10 min).
- `/pain-points` (problem from core.md) · `/pain-points missing items in grocery orders`

**/fact-check**: checks every number and claim before you present.
- `/fact-check` (whole pitch) · `/fact-check --quick` (numbers only, deck and stage scripts) · `/fact-check 04-pitch/deck`

**/feedback**: turns messy notes after a talk into a log entry, next actions and quick background checks.
- `/feedback valio mentor: they said pickers hate the scanner, ask about the 2% number`
- `/feedback summary` (patterns across all talks) · `/feedback close F-012 applied to slide 3`

### Pitches

**/deck**: slide outline + HTML slideshow mock-up with a timer: the 3-min stage deck, plus backup slides for the 3-min Q&A.
- `/deck` · `/deck new number from Valio mentor` (say what changed)
- `/deck slides`: makes the real Google Slides deck; the link is in `04-pitch/deck/slides-link.md`. Teammates' edits are kept on re-runs.
  Until the Google Slides connector works in Claude Code, each update is a new deck with a new link (it asks you first).
- `/deck export`: PDF + .pptx in `04-pitch/deck/export/` (offline backup) · `/deck canva`: optional concept images

**/pitch**: timed scripts for the stage and the partner judges, with a too-long warning (140 words/min).
- `/pitch stage` (3 min: the 2026 stage rule, mic cut at 3:00, then 3 min Q&A) · `/pitch partner valio` · `/pitch elevator` (30 s) · `/pitch all`
- `/pitch rehearse stage-3min`: cue cards and a self-check list.

**/easy-pitch**: plain English for peers: hooks, 10 s, 30 s and the 2-min table demo, jargon check.
- `/easy-pitch` · `/easy-pitch test` (3 hooks to try on different peers)

**/pro-pitch**: the walk-up pitch for anyone you meet on the floor: 60–90 s talk, 3-min guide, 5 questions to ask them.
Pick the variant by what the listener cares about; no names needed.
- `/pro-pitch technical`: engineers, AI or tech mentors, a technical judge (how it works, models, where it fails)
- `/pro-pitch business`: VCs, managers, a business judge or mentor (money saved, who pays, pilot)
- `/pro-pitch partner valio`: someone from the company that sponsors the challenge (their goal, their rubric, their data)
- `/pro-pitch`: all three

**/jury-drill**: judges your idea like the stage jury and lists the questions most likely in the 3-min Q&A, ranked, with why (real 2025 jury questions + the 2026 jurors' criteria + your weak spots). Questions only, no quiz → `04-pitch/scripts/qa-prep.md`
- `/jury-drill` (idea from core.md) · `/jury-drill <idea in one line>` · add `with answers` for short model answers
- Practice only when you ask: `/jury-drill live raghuvanshi` (a judge asks, your answers get scored) · `/jury-drill live mixed` · `/jury-drill rapid` (10 fast questions)

**/team-intro**: who we are, built on how the four of us complement each other (not past wins).
- `/team-intro`: 10-s team line for the stage pitch, team slide text, "who did what this weekend?" answer, 30-s intro for mentors/partners
- `/team-intro Bogdan built the agent, Bea the app`: fills in who did what · `/team-intro description`: written texts (one line, short, medium) for forms, submission, website, LinkedIn

**/video-idea**: video concepts and storyboards, ideas only. `/video-idea we have a voice demo, make it funny`

## Same name, different skill

| You type | You get | Use it when |
|---|---|---|
| `/pro-pitch technical` | What **you say** to them + questions **you ask them** | You are about to walk up to someone |
| `/jury-drill live raghuvanshi` | **A judge asks you** questions; your answers get scored | Practising Q&A |
| `/pitch partner valio` | The formal **judging** pitch on Valio's rubric (3 min, on stage or at the table) | Partner judging slot |
| `/pro-pitch partner valio` | A **conversation** with a Valio person, plus questions to ask them | Meeting a Valio rep on the floor |
| `/pitch elevator` | 30 s, formal, for judges and partners | Anyone important, very short |
| `/easy-pitch` | 10 s / 30 s / 2 min in everyday words | Peers, non-tech people, the Sunday table review |

## Judge names (only for /jury-drill live)

| Judge | Type (any of these) | Lens |
|---|---|---|
| Kia Kanninen | `kanninen`, `kia` | Is the problem real and worth solving? |
| Daksh Raghuvanshi | `raghuvanshi`, `daksh` | Why does the AI fail? How do you measure it? |
| Otto Söderlund | `soderlund`, `otto` | Real user, why they come back |
| Timo Ahopelto | `ahopelto`, `timo`, `vc` | Who pays, is this a company? |
| Umar Noor | `noor`, `umar`, `deepmind` | Which model and why, path to production |
| Partner judge | `partner` | The challenge rubric |
| Peer | `peer` | "Is this just ChatGPT with a prompt?" |

Only `/jury-drill live` uses these names. `/pro-pitch` takes only `technical`, `business` or `partner <company>`.

## Where results go

`03-research/` (challenges, pain-points, market, users, competitors, feedback, fact-check) · `04-pitch/` (core.md, deck, scripts) · `04-pitch/fact-check-report.md`

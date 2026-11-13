# Feedback log

- Created: 2026-11-10 19:30 (Helsinki) · Written by /feedback
- Based on core.md: each entry records the core.md "Last updated" value it was logged against.
- Who = role + company only. No personal names or contact details.
- Status: OPEN → RESEARCHING → RESEARCHED → APPLIED / REJECTED (with why) / DONE
- Commands: `/feedback <who>: <notes>` · `/feedback summary` · `/feedback close F-012 <outcome>`
- Entry template: `.claude/skills/feedback/templates.md` ("Log entry"). Follow-up files go in `followups/`.

<!-- entries: newest first -->

## F-004 · 2026-11-13 19:30 · Partner team, Stoa · OPEN
- Based on core.md: template, not filled yet
- Setting: booth chat (Madalina)
- Notes: translated from Madalina's notes in Romanian; a personal description of one Stoa person left out.
  - Judging: the final presentation on Sunday counts most, but coming to them with small questions and progress
    updates during the event may also count. They don't know when the Saturday check-in is or how judging runs after
    Sun 10:00; they only want to see what we built.
  - How to present: no market slides, and no web research proving the problem exists and that we are the solution:
    they already know the problem. Present what we built and how, technically. Their CTO is very technical and will
    ask about it.
  - Their app, as shown on their screen: a building shown floor by floor. On the right, the main issues that could
    come up, in writing; clicking one opens that floor's plan and shows where. At the bottom, a short list of issues,
    each drawn as a bar on a timeline for when it is scheduled (day x to day y); the bar is meant to be a progress
    bar (% done).
- Signal: useful: judging criteria and the shape of their current app

**Liked** — · **Concerns** — · **Similar products named** — their own app (above) · **Questions they asked** —

**Research requests** —

**Suggested idea changes**
- Pitch: a technical walkthrough (data in, pipeline, data out, measured accuracy, what fails, architecture), no
  market framing.
- Output: every finding gets a floor, a sheet and a region on the plan, so it can drop into a floor-by-floor issue
  view like theirs; findings tied to dates (a drawing an activity waits on) fit their timeline.

**Actions**
- [ ] F-004.1 Ask Stoa: is the floor / issue / timeline screen their product today, or a mock of what they want from
  the challenge? What sits behind a located issue (floor, plan coordinates, schedule ids)?
- [ ] F-004.2 A short progress check-in with the Stoa team on Saturday: what works, plus our open questions.
- [ ] F-004.3 Pitch prep: a list of technical questions their CTO may ask (how extraction works, models, accuracy
  and how it was measured, failure cases, EU data handling, cost per page), each with our answer.

**Status log**
- 2026-11-13 19:30 OPEN

## F-003 · 2026-11-13 17:50 · Partner rep, Stoa · OPEN
- Based on core.md: template, not filled yet
- Setting: booth chat (Bogdan)
- Notes as typed: "You get architectural files, multimodal etc., written legacy, and you standardise these to make sure they are up to date, make them in a standard format, then to be able to be fed into an AI for easier access, with potential 3D drawings"
- Signal: compliments only (no data offered yet)

**Liked** — · **Concerns** — · **Similar products named** — · **Questions they asked** —

**Research requests**
- Who Stoa is; existing tools (Make a BIM found): [../challenges/stand-notes-2026-11-13.md](../challenges/stand-notes-2026-11-13.md) §2

**Suggested idea changes** —

**Actions**
- [ ] F-003.1 Ask the Stoa rep: "Can we get a sample folder of your files tonight?" and the other §2 questions (Bogdan or Madalina)
- [ ] F-003.2 `/challenge-pick` on the official brief after 18:00
- [ ] F-003.3 Round-2 questions (measurable before/after, data source, handoff format): [../challenges/stoa-legacy-files/partner.md](../challenges/stoa-legacy-files/partner.md) "Follow-up questions"

**Status log**
- 2026-11-13 17:50 OPEN

## F-002 · 2026-11-13 17:45 · Partner rep, Hostinger · OPEN
- Based on core.md: template, not filled yet
- Setting: booth chat (Bogdan)
- Notes as typed: "Hostinger want an app built on their setup which detects propaganda"
- Signal: compliments only

**Liked** — · **Concerns** — · **Similar products named** — · **Questions they asked** —

**Research requests**
- What "their setup" is (Horizons, API/MCP, hosting): [../challenges/stand-notes-2026-11-13.md](../challenges/stand-notes-2026-11-13.md) §4

**Suggested idea changes** —

**Actions**
- [ ] F-002.1 Ask the Hostinger rep: "Built with Horizons, or hosted on Hostinger with our own backend?" and the other §4 questions
- [ ] F-002.2 `/challenge-pick` on the official brief after 18:00

**Status log**
- 2026-11-13 17:45 OPEN

## F-001 · 2026-11-13 17:45 · Partner rep, Cala · OPEN
- Based on core.md: template, not filled yet
- Setting: booth chat (Bogdan)
- Notes as typed: "Cala wants a way to find unicorn companies, like an algorithm"
- Signal: compliments only

**Liked** — · **Concerns** — · **Similar products named** — · **Questions they asked** —

**Research requests**
- Does Cala's data carry dates for a backtest: [../challenges/stand-notes-2026-11-13.md](../challenges/stand-notes-2026-11-13.md) §3

**Suggested idea changes** —

**Actions**
- [ ] F-001.1 Ask the Cala rep: "Do your facts carry dates, so we can backtest which companies became unicorns?" and the other §3 questions
- [ ] F-001.2 `/challenge-pick` on the official brief after 18:00

**Status log**
- 2026-11-13 17:45 OPEN

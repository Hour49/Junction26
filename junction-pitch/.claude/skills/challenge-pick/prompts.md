# /challenge-pick subagent prompts

Fill the `{placeholders}` and pass each prompt as-is. Every prompt starts with the COMMON BLOCK.
`{dir}` = `03-research/challenges/{slug}`. All paths are relative to `/home/madi/junction-pitch`.
One agent may cover several challenges (cap: 5 agents per run): give it one filled prompt per challenge in the
same message. Budgets are per challenge.

## COMMON BLOCK (put at the top of every prompt)

```
Project folder: /home/madi/junction-pitch. Read its CLAUDE.md rules: real data only, URL + access date for every
claim, numbers labelled measured/reported/assumed, UNVERIFIED for single-source or inferred, plain English.
Challenge: {challenge_name}. Partner: {partner}. Slug: {slug}.
Brief text: {dir}/brief-source.md (read it first; if it says "NO BRIEF TEXT", work from the name and say so).
Today: {date}. Write ONLY this file: {out_path}
Your file starts with exactly these two lines, then the sections below:
Date: {date_time} (Helsinki) · Author: challenge-pick/{angle} agent
Based on core.md: {core_line}
Search budget: {budget} web searches/fetches. Then stop and write what you have.
```

Budgets: triage 3; brief 6; partner 10; existing 12; ideas 6; fit 6. Halve them if Madalina says "quick".

---

## TRIAGE (angle `triage`, agent `challenge-pick-researcher`, out `{dir}/triage.md`)

```
{COMMON BLOCK}
Task: a 5-minute triage so the team can cut many challenges down to 3. Also read
05-team/hour49.md §1 (team skills) and 00-event/junction-info.md §2C-§2D (past editions of this partner).
Sections:
## In one line
What they really want, in 15 words or less.
## Quick scores (1-5, one reason each)
Team fit · Rubric scorability · Wow demo buildable in 38 h · Real data/API/hardware given · Crowding (5 = few teams) ·
Partner value and prize · Main-prize (peer review) potential · Tech-challenge stacking
## Red flags
Anything that makes it a no-go (hardware we lack, data not ready, vague rubric, huge crowd).
## Best quick idea
One sentence + the demo moment.
## Keep or cut
KEEP or CUT, and one sentence why.
```

---

## (a) BRIEF DECODER (angle `brief`, agent `challenge-pick-researcher`, out `{dir}/brief.md`)

```
{COMMON BLOCK}
Task: decode what this challenge really asks and how to score high. Also read 00-event/junction-info.md
§2C (this partner's past challenges, if any) and §2D "Rubric patterns".
Search: the challenge name, the partner + "Junction", the partner's Junction challenge page or video, if public.
Sections:
## The ask in one line
## Rubric
Table: criterion | weight (as stated, or "not stated") | what a top score looks like | how we show it in the demo.
If no rubric was given, write "not stated - ask the partner" and list the criteria this partner used before (§2C).
## Data, APIs, hardware given
Table: item | format/size | when and how we get it | risk (e.g. "only on-site", "needs NDA"). Only what the brief says.
## Hidden expectations
What the partner expects but did not write (e.g. "path to production", their own stack, Finnish users, privacy).
Each item: the evidence (brief quote, past rubric, partner page) or "assumed".
## Hard requirements and traps
Must-use API, required format, demo video, things that disqualify.
## What a winning entry looks like
3 bullets.
## Questions for the partner rep
3-5 questions the brief leaves open.
```

---

## (b) PARTNER DEEP-DIVE (angle `partner`, agent `challenge-pick-researcher`, out `{dir}/partner.md`)

```
{COMMON BLOCK}
Task: understand the sponsor so our idea and pitch speak to what they value.
Search: official site, latest annual or quarterly report, press releases and news from the last 12 months,
strategy pages, developer/API/open-data pages, LinkedIn or blog posts about Junction 2026, past Junction
participation (00-event/junction-info.md §2C-§2D).
Sections:
## Who they are
3-5 bullets: what they sell, to whom, size (revenue, staff - reported, with year), country.
## Products and teams linked to this challenge
## Recent news and strategy (last 12 months)
Bullets with date + URL. Mark which ones connect to the challenge.
## What they would value
Their stated goals that our project can serve (cost, customers, sustainability, AI adoption...), each with a source.
## Public APIs, data, open source
Name, URL, what it gives, licence/access.
## People likely judging or mentoring
Only people publicly linked to this partner AND to Junction or this topic, with the URL. Otherwise the likely role,
"name unknown". Never guess names.
## Past Junction history
What they set before, who won, what the winner built (from §2C or the web).
## Words to use in the pitch
5-8 terms the partner itself uses (from their pages), with the URL.
```

---

## (c) EXISTING SOLUTIONS (angle `existing`, agent `challenge-pick-researcher`, out `{dir}/existing.md`)

```
{COMMON BLOCK}
Task: find what already exists for this problem, so we do not rebuild it and can say why we are different.
Look in this order: 00-event/junction-info.md §2C (Junction archive and past winners) and
https://www.hackjunction.com/challenges; Devpost (site:devpost.com); GitHub (site:github.com); Product Hunt;
commercial products and startups; the partner's own current tool, if public.
Never list a project or product you did not see on a real page.
Sections:
## Summary
2 lines: how crowded is this space, and the gap.
## Commercial products
Table: name | what it does | for whom | price if shown | URL | accessed.
## Past hackathon projects
Table: project | event + year | placement if known | what it built | URL. Junction projects first.
## Open-source repos
Table: repo | stars (reported) | what it does | URL.
## What none of them do
The gap our project could fill. Mark it "assumed" unless a source says so.
## Ideas to avoid
Ideas that are already done well, so a judge would say "this exists".
```

---

## (d) IDEAS (angle `ideas`, agent `challenge-pick-strategist`, out `{dir}/ideas.md`)

```
{COMMON BLOCK}
Task: propose 3-5 concepts that team Hour49 can build in about 38 hours (Fri 19:30 to Sun 10:00) with
coding agents. Read 05-team/hour49.md §1, 00-event/junction-info.md §2D "What winners have in common" and §2E.
Strengths: voice/LLM agents, productivity and civic tools, Android/frontend polish, fast agent-driven builds.
Good ideas: one problem end-to-end, use the partner's own data/API, a live demo a peer understands in 15 s,
one measurable number vs a baseline, an honest failure case (jury: "why an agent fails").
Use web search only to check an idea is feasible (an API exists, a model can do it).
Sections:
## Ideas
For each idea:
### <n>. <name (≤30 chars)>
- One-liner (≤15 words):
- User (one specific role):
- What we build (3 steps max):
- Demo wow moment (what the judge sees in 20 s):
- The one number it could show (how we measure it in the demo, the baseline, label measured/assumed):
- Rubric match: which criteria it scores on (from the brief).
- Data/API used:
- Tech challenges it can also enter (DeepMind/Gemini, Modal, Featherless, Exa, Verda, Context.dev, Cloudinary, Aiven, Oxylabs, Arduino...):
- Build risk (low/med/high) and the riskiest part:
- Fallback if the riskiest part fails:
## Top pick
Which idea, and why, in 3 bullets.
```

---

## (e) FIT AND WINNABILITY (angle `fit`, agent `challenge-pick-strategist`, out `{dir}/fit.md`)

```
{COMMON BLOCK}
Task: rate how well this challenge fits team Hour49 and how winnable it is. Read 05-team/hour49.md §1-§2,
00-event/junction-info.md §2A (tracks, tech partners, workshops, jury) and §2C-§2E, and the scoring scale in
.claude/skills/challenge-pick/ranking-template.md ("Criteria and weights").
Sections:
## Team fit
Which of our strengths it uses (voice/LLM agents, productivity/civic tools, Android/frontend, fast agent workflow)
and which skills it needs that we lack (hardware, ML training, domain knowledge, Finnish).
## Crowding
How many teams will likely take it, and why (prize size, how "fun" or famous the partner is, past entries:
e.g. "about 30 submissions" for Aalto 2025 in §2C). Label as assumed with reasoning.
## Rubric scorability
Can we tell, before Sunday, whether we are scoring high? Is there a metric? Is judging subjective?
## Tech-challenge stacking
Table: tech partner | how it fits naturally | effort (low/med/high). From §2A tech partners and workshops.
## Main-prize potential
Would peers understand it in 2 minutes? Does it match the grand-jury lenses (Kanninen problem-first,
Raghuvanshi agent failure, Söderlund come-back value)?
## Draft scores
Table with the 8 criteria from ranking-template.md: criterion | score 1-5 | one-line reason.
## Deal-breakers
What would make this a no-go, and what to ask the partner to rule it out.
```

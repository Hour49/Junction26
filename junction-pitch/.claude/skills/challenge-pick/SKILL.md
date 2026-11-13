---
name: challenge-pick
description: Help team Hour49 choose which Junction 2026 challenge to take (Friday evening, after the briefs appear). At most 5 agents per run. With more than 3 challenges, a triage run first (agents share the challenges) that stops at a shortlist; then a deep-pass run with 5 angle agents (brief decoder, partner deep-dive, existing solutions, ideas, fit and winnability) covering the top 3, then writes a weighted ranking with a recommendation, the top idea per challenge and 5 questions for each partner rep. Writes to 03-research/challenges/.
when_to_use: Use when Madalina pastes challenge briefs or names, gives a file of briefs, or says "which challenge", "compare challenges", "pick a challenge", "shortlist", "rank the challenges", "should we take X or Y", "help us decide the track".
argument-hint: "[challenge names | pasted briefs | path to briefs file | shortlist] [quick] [weights: fit 30 ...]"
---

# /challenge-pick

Input: $ARGUMENTS

Goal: by Fri ~21:00 the team knows which challenge to take, with which idea, and what to ask the partner reps.
Speed matters: briefs appear Fri 18:00, hacking starts 19:30. Produce usable output fast.

Before starting, read (only these parts):
- `00-event/junction-info.md` §0, §2A-§2E (event facts, tracks, tech partners, past editions, patterns, tips).
- `01-playbooks/market-research.md` §0 (ground rules) and §7 (Friday schedule).
- `04-pitch/core.md` first 3 lines: copy its `Status:` / `Last updated:` text as the **core line**
  (e.g. "TEMPLATE, not filled yet").
- Get the time: `TZ=Europe/Helsinki date '+%Y-%m-%d %H:%M'`.

Supporting files: [prompts.md](prompts.md) (exact subagent prompts and search budgets),
[ranking-template.md](ranking-template.md) (scoring scale, weights, ranking.md template).

## Step 1. Understand the input (no more than 1-2 questions, only if blocked)

Accept messy input. Cases:
- **Pasted briefs or a file of briefs** (from the platform "Challenges" tab or notes from the opening videos):
  split into one challenge per brief. Find partner, title, rubric, data, prize where present.
- **Names only** ("valio, espoo, s-pankki"): look for brief text in `03-research/challenges/*/brief-source.md`
  and any file path Madalina gave. If there is none, ask ONCE: "Paste the briefs or give me the file path, or
  say 'go' and I'll work from names only." On "go", continue and mark each brief "NO BRIEF TEXT".
- **"shortlist"**: read `03-research/challenges/shortlist.md` and run Step 3 on its KEEP list. If it does not
  exist, use every `03-research/challenges/*/brief-source.md` folder (triage first if there are more than 3).
- **"quick"**: halve every search budget in prompts.md.
- **"weights: ..."**: use those weights in Step 4 (they must total 100; rescale the others if not, and say so).
- **One challenge only**: still run the 5 agents; the ranking then says go/no-go instead of comparing.

For each challenge make a slug `<partner>-<short-challenge>` (kebab-case, lower case, e.g.
`valio-aimo-zero-fail-logistics`). Create `03-research/challenges/<slug>/` and save the brief text exactly as
given to `<slug>/brief-source.md`, with a first line `Source: <platform Challenges tab | opening video notes |
file path> · captured <date time>`. If `brief-source.md` already exists and differs, write `brief-source-v2.md`
and point the agents to it. Never put partner raw data (datasets, credentials) in this folder.

Tell Madalina in one line what you are about to do: "N challenges → triage first (K agents)" or "N challenges → deep pass,
5 agents".

## Step 2. Triage (only if there are more than 3 challenges)

Launch at most 5 `challenge-pick-researcher` agents, **all in ONE message** so they run in parallel, using the
TRIAGE prompt in prompts.md. Split the challenges evenly (e.g. 12 challenges → 5 agents with 2-3 each); each
agent triages its challenges one after another and writes one `triage.md` per challenge. With 5 or fewer
challenges, one agent per challenge.

When they finish, write `03-research/challenges/shortlist.md`:
- the date line and core line (see "Output rules");
- a table: challenge | quick weighted score (weights from ranking-template.md) | KEEP/CUT | one-line reason;
- the 3 KEEP challenges. Prefer variety, e.g. do not keep 3 hardware challenges.

Show Madalina the table and the KEEP list, then stop: this run has used its agents (cap: 5 per run). Say:
"Reply go (or swap X for Y) and I'll run the deep pass on the KEEP list." Her reply starts Step 3 as a new run,
the same as `/challenge-pick shortlist`.

## Step 3. Deep pass (5 agents, one per angle, up to 3 challenges)

Launch the 5 angle agents **in ONE message**, so they run concurrently. Each agent does its angle for every
shortlisted challenge in turn: give it one filled prompt per challenge in the same message, with "Do these in
order; write each file before starting the next." More than 3 challenges on the list: ask which 3 to keep.

| Angle | Agent type | Output |
|---|---|---|
| (a) Brief decoder | `challenge-pick-researcher` | `<slug>/brief.md` |
| (b) Partner deep-dive | `challenge-pick-researcher` | `<slug>/partner.md` |
| (c) Existing solutions | `challenge-pick-researcher` | `<slug>/existing.md` |
| (d) Ideas (3-5, 38 h buildable) | `challenge-pick-strategist` | `<slug>/ideas.md` |
| (e) Fit and winnability | `challenge-pick-strategist` | `<slug>/fit.md` |

Use the exact prompt for each angle from prompts.md, with the COMMON BLOCK filled in. If the custom agent types
are not available in this session, use `general-purpose` with the same prompt, and say `model: sonnet` for
(a)-(c) and `model: opus` for (d)-(e).

If an output file already exists (a re-run), do not overwrite it: give the agent `<name>-v2.md` (or the next free
`-vN`) as its output path.

While the agents run, tell Madalina: "5 agents running (about 10-15 min per challenge on the list). Meanwhile, go find the partner reps;
the first questions are in each brief once it lands." Do not wait in silence.

## Step 4. Synthesise: `03-research/challenges/ranking.md`

When all agents are back, read every `brief.md`, `partner.md`, `existing.md`, `ideas.md` and `fit.md`. Then:

1. **Check the sources first.** Spot-check the 3-5 facts the recommendation depends on (open the URL with
   WebFetch; a search summary is not a check). If a
   key fact is wrong or unsourced, fix the wording in ranking.md and mark it UNVERIFIED. Drop any invented-looking
   company, repo or person.
2. **Score.** Start from each `fit.md` "Draft scores". Adjust using the other files: crowding from `existing.md`,
   scorability from `brief.md`, wow from `ideas.md`, partner value from `partner.md`. Use the scale and weights in
   ranking-template.md. Show the weights in the table and the arithmetic for the winner.
3. **Recommend** one challenge + one idea, with 3 reasons that link to the files, the main risk, a runner-up and
   the condition to switch.
4. **Top idea per challenge**: the "Top pick" from each `ideas.md`, possibly improved by what you read.
5. **5 questions per partner rep**: specific to that partner, built from `brief.md` "Questions for the partner
   rep" and `fit.md` "Deal-breakers". Mom-Test style (past facts, numbers, data, who judges), idea test last.
6. List UNVERIFIED items and how to check each.

Follow the template in ranking-template.md exactly. If `ranking.md` already exists, never overwrite it: write
the next free `ranking-vN.md` and say which is newest. With one challenge only, write GO / NO-GO instead of
"Take", and "Runner-up: none".

If a key fact is still missing (no rubric, unclear data), the recommendation says what to ask and that the
score may change after the floor talks. Do not invent a rubric.

## Output rules (every file)

- Line 1 after the title: `Date: YYYY-MM-DD HH:MM (Helsinki) · Author: <agent or /challenge-pick>`.
- Line 2: `Based on core.md: <core line>`.
- Every claim: URL + access date, or local file + section. Numbers labelled measured / reported / assumed.
  Single-source or inferred = UNVERIFIED. Never invent people, quotes, numbers, companies or repos.
- Plain, common English. Short sentences. No buzzwords.
- Do not add facts to `03-research/sources.md` yet: that is for facts that go into the pitch, after the decision.
  But do say in the summary which numbers look pitch-worthy.

## Step 5. Chat summary (short)

Reply with at most ~12 lines:
- The pick: "<challenge> with idea <name>, score x.xx/5 (runner-up <y>, x.xx)."
- 2-3 reasons and the main risk.
- The first question to ask each partner rep right now.
- File paths: `03-research/challenges/ranking.md`, plus each `<slug>/` folder (and `shortlist.md` if made).
- Next: talk to the reps, then re-run `/challenge-pick shortlist` or edit ranking weights if the answers change
  things. After the team decides: fill `04-pitch/core.md`, then `/pain-points`, `/market-scan`, and log rep
  talks with `/feedback`.

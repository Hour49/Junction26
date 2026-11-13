---
name: market-scan
description: Deep research pass on our chosen idea. Runs 5 parallel research agents (competitors and status quo, similar hackathon and startup ideas, target user, market size, problem size), writes sourced files to 03-research/competitors, users and market, then a summary with the "Unlike X, we Y" line, 3 one-liners and proposed core.md changes. Use when Madalina says "market scan", "research the idea", "who else does this", "competitors", "how big is the market", "TAM", "market size", "problem size", "who is the user", "persona", or right after the idea is picked. Add --quick for a 3-agent, about 15-minute version.
when_to_use: after /challenge-pick or when core.md has a new idea; "deep research", "do the research", "check competitors", "is this already done", "size the market", "find the one number"
argument-hint: "[--quick] [idea or problem in a few words; default = 04-pitch/core.md]"
---

# /market-scan: deep research on the chosen idea

Input: `$ARGUMENTS`. Answer five questions with real, sourced data:
1. Who else does this (competitors, similar ideas, the status quo)?
2. Who exactly is the user?
3. How big is the market?
4. How big is the problem (one headline number)?
5. What is our solution, in short?

Method: `01-playbooks/market-research.md` §0–§6. Project rules: `CLAUDE.md` (real data only, label every
number measured / reported / assumed, single-source = UNVERIFIED, plain English).

Supporting files (read them when you get to the step that needs them):
- Agent prompt templates: [agent-prompts.md](agent-prompts.md)
- Output templates (5 research files + summary): [templates.md](templates.md)
- Subagent definition: `.claude/agents/market-scan-researcher.md`

## Step 1. Read the input (2 min, no web)

1. Mode: if `$ARGUMENTS` contains `--quick`, use QUICK mode (3 agents). Otherwise FULL mode (5 agents).
2. The idea:
   - If `$ARGUMENTS` has idea text (after removing `--quick`), use it. Treat short, messy notes as fine.
     Note "Based on: idea text from chat, <date>".
   - Else read `04-pitch/core.md`. Use its fields. Note "Based on: 04-pitch/core.md, Last updated: <value>".
   - If there is no idea text AND core.md still says `Status: TEMPLATE` (or the one-liner is `—`), ask ONE
     question: "What is the idea in one sentence, and which challenge/partner is it for?" Then stop and wait.
3. Context (read only what exists; skip missing files silently):
   - `04-pitch/core.md`: even when idea text is given, read it for partner, user and open questions.
   - `03-research/challenges/*.md`: the brief and the **rubric** for our challenge. The rubric decides which
     numbers matter most (e.g. "FTE savings" → problem size in hours and FTE).
   - `03-research/feedback/log.md`: similar products people named, "research next" items. Pass them on.
   - `03-research/pain-points/*.md`: real complaints already found. Pass the path to agents 3 and 5.
   - `00-event/junction-info.md` §2C and §2D: past Junction challenges and winners (agent 2 needs this).
   - Existing files in `03-research/competitors/`, `users/`, `market/`: if an earlier scan exists, tell the
     agents to build on it, not repeat it.
4. Make a short kebab-case **slug** for the idea, 2–4 words, e.g. `valio-missing-items`.
5. Do not ask anything else. Assumptions go in the summary under "Open questions".

## Step 2. Pick the output paths

FULL mode (one file per agent):

| # | Agent angle | Output file |
|---|---|---|
| 1 | Competitors + status quo | `03-research/competitors/<slug>-competitors.md` |
| 2 | Similar ideas (hackathons, startups) | `03-research/competitors/<slug>-similar-ideas.md` |
| 3 | Target user | `03-research/users/<slug>-persona.md` |
| 4 | Market size | `03-research/market/<slug>-market-size.md` |
| 5 | Problem size | `03-research/market/<slug>-problem-size.md` |

QUICK mode (3 agents): Q1 writes the competitors file (with a short "Similar ideas" section), Q2 the persona
file, Q3 writes BOTH the market-size and the problem-size file (short versions).

**Never overwrite.** If a target file already exists, use the next free version: `<name>-v2.md`, `-v3.md`, …
Same for the summary. Create a folder only if it is missing.

## Step 3. Launch the agents IN ONE MESSAGE

**Before launching (logins for private sources):** the agents' Playwright browser loads saved logins from
`.playwright/auth.json` (git-ignored, never commit it). If the file is missing, create it with
`{"cookies":[],"origins":[]}` so the browser starts. To add logins, Madalina runs once from the project root
`npx -y playwright codegen --save-storage=.playwright/auth.json https://www.reddit.com/login`, logs in to the
sites she wants (Reddit, LinkedIn, X, paid report sites) in that window, then closes it. Never ask her for a
password. When agents report `needs login: <site>`, list those sites in the reply so she can add them.


Send all Agent calls (5 in FULL, 3 in QUICK) in a **single message** so they run at the same time.
- `subagent_type: market-scan-researcher` (haiku). If that type is not available in this session, use
  `general-purpose` with `model: haiku` and paste the "Sources and tools", "Hard rules" and "Report to your
  orchestrator" blocks from `.claude/agents/market-scan-researcher.md` at the top of each prompt.
  Each agent runs on **Haiku** with its own arxiv MCP (papers) and Playwright browser (web pages; sites that
  block agents). Their final message carries all their findings: read it, check it against the file, and
  synthesise from both.
- Each prompt = the **shared context block** + that agent's **angle block** from
  [agent-prompts.md](agent-prompts.md), with the placeholders filled in, plus the matching template from
  [templates.md](templates.md) pasted in full.
- Search budget per agent: FULL about 15–20 searches/fetches; QUICK about 8.
- While they run, do not do their work. You may tell Madalina in one line: "5 research agents running, about
  25–40 min" (QUICK: "3 agents, about 15 min").

## Step 4. Check each file when its agent finishes

For each returned file:
- Open it. Check it has the date line, the "Based on" line, links on claims, labels on numbers.
- Spot-check: open the 2–3 most important URLs (the headline problem number, the top competitor, the market
  unit count). If a URL is dead or does not say what the file claims, mark that claim **UNVERIFIED** in the
  file and say so in the summary. Do not silently fix numbers.
- If one agent failed or produced nothing usable, do NOT re-run the whole scan. Write the summary with what
  you have and list the gap under "Not done / next".

## Step 5. Append sources (append only)

- If `03-research/sources.md` does not exist, create it with the header line from `03-research/README.md`:
  `claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence`
- Copy every line from each file's `## Source lines` section to the END of `03-research/sources.md`
  (drop a leading "- " if an agent added one).
  Before them add one line: `# market-scan <slug>, <YYYY-MM-DD HH:MM>`.
- Append only. Never edit or delete existing lines. Skip a line only if the exact same line is already there.

## Step 6. Write the summary

Write `03-research/market-scan-summary.md` (or the next free `-vN`) with the template "Summary" in
[templates.md](templates.md). Rules:
- **5-line answer**: one line per question, each with its key number and label. Plain words.
- **"Unlike X, we Y"**: X is the strongest real alternative (often the status quo). Y must be something our
  demo can actually show. No overclaims.
- **3 one-liner options**, at most 15 words each, using the playbook §5 templates (Moore, before/after,
  problem→solution). Mark which one you recommend and why, in one line.
- **Proposed core.md changes**: a table `field | now in core.md | proposed | why + source file`. Only fields
  where the research gives a better, sourced answer. **Do NOT edit core.md.** Madalina approves first.
- Also: the positioning 2x2 (copied from the competitors file), top 3 risks or weak spots a judge could
  attack, open questions, and 5 questions to ask mentors/partner (from the persona file).
- Keep the summary to about one screen plus tables. Details stay in the 5 files.

## Step 7. Reply in chat (short)

At most about 12 lines:
- The headline problem number (with label) and the "Unlike X, we Y" line.
- The recommended one-liner.
- What is UNVERIFIED or missing.
- File paths (summary first, then the research files, then `03-research/sources.md`).
- Next skills: `/fact-check` on the headline numbers; approve the core.md changes, then `/deck` or `/pitch`;
  take the 5 interview questions on a walk and log answers with `/feedback`.

## Quality bar (check before Step 7)
- No invented companies, people, quotes or numbers. Every competitor has a working URL or is UNVERIFIED.
- Market size: bottom-up first, arithmetic visible, top-down only as a cross-check; both within about 10×
  of each other, or the gap explained.
- Problem number: primary or partner source, ≤5 years old, right geography (or labelled EU/global), in the
  user's unit (minutes, euros, items), ONE number.
- The status quo ("do nothing", Excel, phone calls) is in the competitor table.
- No raw partner data copied into any file. Aggregates only, and say where the raw data lives.

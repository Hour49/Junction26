---
name: pain-points
description: Prove that real people have the problem our idea solves. Finds real complaints in public and private sources - research papers (arxiv) and statistics, news, app store reviews, review sites, forums (Hacker News, Stack Exchange, GitHub, Suomi24, and Reddit, LinkedIn and X through a logged-in Playwright browser) and domain complaint data - with 5 parallel searchers, then writes sourced quotes, the words people use, the strongest statistic and a strong/medium/weak validation verdict to 03-research/pain-points/. Use when Madalina asks "do people actually have this problem", "find complaints", "find quotes", "validate the problem", "user pain", "real people saying", "evidence for the problem slide".
when_to_use: pain points, complaints, validate problem, real quotes, reviews, app store reviews, "is this a real problem", "who complains about", problem slide proof
argument-hint: "[problem or idea in a few words] (default: problem + user from 04-pitch/core.md)"
---

# /pain-points

Input: `$ARGUMENTS` (a problem or an idea in a few words, maybe messy). Goal: real people, in their own words,
with links, saying they have this problem. Then a clear verdict: is the problem validated?

Project rules (CLAUDE.md) apply: real data only, no link = no quote, numbers labelled
measured/reported/assumed, single-source = UNVERIFIED, plain English, results go to files.

**Public and private sources.** Searchers open web pages in their own Playwright browser (many sites block
plain agent fetches), use the arxiv MCP for research papers, and may quote login-walled sites such as Reddit,
X/Twitter and LinkedIn when the saved logins let them in. A page that still shows a login wall is logged as
`needs login: <site>`; anything else that stays blocked is logged as `blocked: <url>`. Tested URL patterns: the table in [source-prompts.md](source-prompts.md).

## Step 0. Read (2 minutes)
- `04-pitch/core.md`: target user, problem, idea, and its "Last updated" line.
- `03-research/pain-points/README.md` (what goes in the folder).
- If they exist: `03-research/feedback/log.md` (problem words people used at the event),
  `03-research/users/*.md`, `03-research/competitors/*.md` (real competitor names for the review search).
- Method background: `01-playbooks/market-research.md` §2.3 item 5 (online traces) and §4 (the one number).

## Step 1. Pin the problem
- If `$ARGUMENTS` is given, use it. If empty, use "Problem" and "Target user" from core.md.
- If both are empty or core.md is still the template: ask ONE question, "Which problem should I look for,
  and who has it?", then stop until she answers.
- If the input is an idea ("an AI that…"), turn it into the problem it solves. Search for the problem,
  never for the solution: people complain about pain, not about missing products.
- Slug: 2–5 kebab-case words for the problem (e.g. `missing-grocery-items`). If
  `03-research/pain-points/<slug>/` already exists, ask: "Add a new run (`<slug>-v2`) or skip?" Never overwrite.

## Step 2. Search plan (write it before any search)
Write `03-research/pain-points/<slug>/search-plan.md` using the "Search plan" template in
[templates.md](templates.md). It must have:
- 3–6 user roles (end user and payer if different; workers and managers for B2B problems).
- 5–10 phrasings real people would type or say: complaint language, first person, angry or tired
  ("my order came with half the stuff missing", "why do they never tell you before"),
  not marketing words ("fulfilment accuracy optimisation").
- Finnish phrasings (and Swedish if relevant) when the problem exists in Finland, e.g. "puuttuvat tuotteet",
  with the English meaning.
- Synonyms, real competitor/brand names, and a "Not this" list of off-topic meanings.
You may run 1–2 quick WebSearches to check the words people really use. Do not ask Madalina to approve the plan.

## Step 3. Launch 5 searchers IN ONE MESSAGE
Send five Agent calls in the same reply so they run at the same time. Use `subagent_type: pain-points-searcher`
(defined in `.claude/agents/pain-points-searcher.md`, Haiku). Build each prompt from
[source-prompts.md](source-prompts.md): the common block + that searcher's family block(s).
**Before launching (logins for private sources):** the agents' Playwright browser loads saved logins from
`.playwright/auth.json` (git-ignored, never commit it). If the file is missing, create it with
`{"cookies":[],"origins":[]}` so the browser starts. To add logins, Madalina runs once from the project root
`npx -y playwright codegen --save-storage=.playwright/auth.json https://www.reddit.com/login`, logs in to the
sites she wants (Reddit, LinkedIn, X, paid report sites) in that window, then closes it. Never ask her for a
password. When agents report `needs login: <site>`, list those sites in the reply so she can add them.

Each agent runs on **Haiku** with its own arxiv MCP (papers) and Playwright browser (web pages; sites that
block agents). Their final message carries all their findings: read it, check it against the file, and
synthesise from both.

Six source families, five searchers (CLAUDE.md caps a skill run at 5 agents): searcher 3 takes two families.

| # | Source family | Output file |
|---|---|---|
| 1 | Research and surveys (arxiv MCP, OpenAlex, Crossref, PubMed, Eurostat, Statistics Finland, OECD, consumer bodies, regulators): the strongest statistic | `research.md` |
| 2 | News (Yle, HS, Reuters, trade press; GDELT optional): real people quoted in articles | `news.md` |
| 3 | App store reviews (App Store RSS, Google Play best-effort) + review sites (Trustpilot, G2, Capterra, best-effort) | `reviews.md` |
| 4 | Open forums with public APIs (Hacker News, Stack Exchange, GitHub issues, Suomi24) | `forums.md` |
| 5 | Domain complaint data for the challenge track (openFDA, CFPB, EU/Finnish consumer complaint statistics, partner or industry reports): counts and trends | `complaints.md` |

All files go to `03-research/pain-points/<slug>/`. Finnish phrasings go to every searcher (Suomi24, Yle, App
Store `fi`, Kuluttajaliitto/KKV). For a big or two-sided problem (e.g. pickers AND customers), do not add
searchers; tell each searcher to split its budget between the two sides.
While they run, tell Madalina in one line: "5 searchers running, about 5–10 minutes."

## Step 4. Check the evidence (before writing the summary)
When all five are back, read every source file and check:
- Each quote has a link to the original page (not a mirror or SEO copy). Remove any without one.
- Numbers come from the source page, not from a search summary. Open 3–5 of the top quotes yourself to confirm
  the exact words are on the page: `python3 .claude/skills/pain-points/fetch_public.py page "<url>" --grep "<word>"`
  (WebFetch copies at most about 125 characters verbatim, so use it for short quotes only); mark any you could
  not confirm `snippet-only` or `UNVERIFIED`.
- Quotes from private (logged-in) pages: short, role only, marked `private`.
- No usernames or real names of private people. Role only.
- Duplicates across files: count once (keep it in the first file, note it in the other).
- Match levels are honest: "exact" = our user, our problem, our setting. Downgrade if in doubt.
If a searcher failed or returned nothing, say so in the summary. Do not rerun more than once.

## Step 5. Write `summary.md`
Use the "Summary" template in [templates.md](templates.md). It contains:
1. Counts per platform and per match level (a table).
2. Top 5 quotes for slides: short, emotional, exact or close match, recent, ideally one Finnish. Each with
   role, platform, date, link. Write the quote in English (our translation for non-English ones): slides show
   English only. The original stays in the source file. No `snippet-only` quotes. If fewer than
   5 qualify, list only those and say so.
3. Words people actually use: phrases that repeat across sources (reuse them in the pitch), and our jargon
   that nobody uses (avoid it).
4. The strongest statistic, checked against the playbook §4.4 bar (primary, ≤5 years, our geography or
   labelled, user's unit, one number), plus a suggested slide line.
5. Verdict with reasons and what would change it:

| Verdict | Rule of thumb (use judgement, explain it) |
|---|---|
| **STRONG** | ≥8 exact quotes from ≥3 platforms, several with intensity 2–3, most from the last 3 years, AND at least one reported statistic that sizes the problem |
| **MEDIUM** | 3–7 exact quotes, or many close quotes but few exact, or no good statistic, or evidence only from one platform |
| **WEAK** | ≤2 exact quotes; mostly adjacent; old; or people mention it but do not seem to care (intensity 1) |

Always add: "Online quotes show the problem exists; a talk with the partner or a real user at the event is
still the strongest proof" (playbook §2.3), and which person to ask.

## Step 6. Append statistics to `03-research/sources.md`
- If the file is missing, create it with a title, a one-line note, and the header line from the format in
  `03-research/README.md`:
  `claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence`
- Append one line per statistic found (from research.md and the others). Append only: never edit or delete
  existing lines. Skip a stat that is already there (same URL and claim).
- Quotes do not go in sources.md; they stay in the pain-points files.

## Step 7. Reply in chat (short)
```
Pain points: <problem> — verdict <STRONG/MEDIUM/WEAK>
- <n> quotes (<x> exact, <y> close, <z> adjacent) from <k> platforms
- Best quote: "<quote>" — <role>, <platform> (<link>)
- Strongest number: <claim, number, source>
- Their words: "<phrase>", "<phrase>", "<phrase>"
- Gaps: <one line>
- Blocked sources: <list, or "none">
- Needs login (add to .playwright/auth.json): <sites, or "none">
Files: 03-research/pain-points/<slug>/summary.md (+ search-plan.md, research.md, news.md, reviews.md,
forums.md, complaints.md); <k> lines added to 03-research/sources.md
Next: /market-scan (competitors and size), /fact-check (before slides), then update 04-pitch/core.md
"Problem (their words)" and "Proof" (or /deck, /pitch).
```
Do not edit core.md yourself; suggest the exact text for Madalina to paste or approve.

## Every file starts with
- `Date: YYYY-MM-DD HH:MM (Helsinki) · Author: …`
- `Based on core.md: <its "Last updated" value>` (or "core.md not filled; input was: …").

## Additional resources
- Subagent prompts per source and the tested source table: [source-prompts.md](source-prompts.md)
- JSON/HTML helper (no prompts, stdlib only): `python3 .claude/skills/pain-points/fetch_public.py -h`
- Templates (search plan, source file, summary, sources.md line): [templates.md](templates.md)
- Searcher agent: `.claude/agents/pain-points-searcher.md`

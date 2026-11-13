---
name: fact-check
description: Check every factual claim and number in the pitch before it is shown or submitted. Extracts numbers, market sizes, statistics, competitor statements, "first/only/best" claims, quotes and partner facts; checks them against 03-research/sources.md, then verifies the rest on the web with 3+ parallel subagents. Writes a dated verdict table with fixes to 04-pitch/fact-check-report.md and appends newly verified facts to sources.md. Never edits pitch files.
when_to_use: fact check, check the numbers, check my claims, verify the deck, is this true, source check, before we present, before we submit, before the stage pitch, "can we say this", "is this number right", overclaim check, citation check.
argument-hint: "[file-or-folder] [--quick]"
---

# /fact-check

Input: `$ARGUMENTS`. Today's date and time (Helsinki): take them from the environment.

Goal: before anything is shown or submitted, every claim in the pitch is either backed by a real source or
flagged with a safer wording. You **propose** fixes; you **never edit** files in `04-pitch/`.

## 0. Parse the input (no questions unless blocked)

- **Nothing given** → scope = every text file under `04-pitch/` (`.md`, `.txt`, `.html`), including `core.md`.
- **A file or folder** → scope = that file, or every text file in that folder.
- **`--quick`** (with or without a path) → only **numbers** in `04-pitch/deck/**` and `04-pitch/scripts/stage-*.md`, `04-pitch/scripts/easy-pitch*.md` (the 2-min table demo said many times on Sunday)
  (if no `stage-*` file exists, all of `04-pitch/scripts/`). Skip words-only claims.
- Always skip: `README.md` files, `fact-check-report*.md`, and binary files (`.pdf`, `.pptx`, images, video).
  List skipped binaries in the report under "Not checked" so Madalina knows to check them by hand.
- If the scope has no text at all (e.g. `core.md` is still the empty template), say so in one line, suggest
  `/pitch` or filling `core.md` first, and stop. Do not write a report.
- Ask a question only if the path does not exist and you cannot guess it (e.g. "deck" → `04-pitch/deck/`).

Set `RUN = YYYY-MM-DD-HHMM` (Helsinki) and `WORK = 03-research/fact-check/<RUN>/`.

## 1. Read the rules (once, fast)

- `03-research/README.md`: labels (measured / reported / assumed), UNVERIFIED, `sources.md` line format.
- `01-playbooks/market-research.md` §3.4 "Citation hygiene" and §3.5 "without overclaiming": your checklist.
- `04-pitch/core.md`: note its "Last updated" value for the report header.

## 2. Extract every claim

Read each file in scope with the Read tool (it shows line numbers). Use Grep to catch numbers you might miss:
pattern `[0-9]|%|€|\$|\bfirst\b|\bonly\b|\bbest\b|\bleading\b|\bunique\b|\bno one\b|\bnobody\b|\bmillion\b|\bbillion\b`.

A claim is anything a judge could ask "where is that from?" about:

| Kind | Examples |
|---|---|
| `number` | percentages, counts, time, money, error rates, FTE savings |
| `market` | TAM/SAM/SOM, market size, growth, number of firms |
| `stat` | survey results, adoption rates, "X% of people…" |
| `competitor` | what a competitor does or does not do, its price, its users |
| `superlative` | "first", "only", "best", "leading", "unique", "no one does this" |
| `quote` | words put in a person's mouth (mentor, user, jury, partner) |
| `partner` | facts about the partner: volumes, staff, costs, their problem, their data |
| `event` | Junction facts: prizes, criteria, dates, past winners |
| `measured` | results from our own demo or test |

For each claim record: id (C1, C2…), exact text (short), `file:line`, kind, the number with its unit, year and
geography if given, and the label used near it (measured / reported / assumed / none).

**Same claim in several files** → one row, list every `file:line`. If the files give **different values** for the
same thing, flag `inconsistent`.

Write the list to `<WORK>/claims.md` (format: [templates.md](templates.md) "Claims file").
In `--quick` mode keep only `number`, `market`, `stat` and `measured` kinds.

## 3. Check against our own records first (no web)

For each claim, look in this order:
1. `03-research/sources.md`. A line **matches** when value, unit, year and geography agree with the claim.
   A match with a URL, an access date and confidence not marked low/UNVERIFIED → verdict `verified`
   (source = that line's URL and date). Note "from sources.md".
2. Other files in `03-research/**` and `00-event/junction-info.md`. A matching finding with a URL is a
   **lead**, not a verdict: send it to a web agent with the URL as the starting point.
3. `03-research/feedback/log.md`. Partner or mentor statements logged there can back a `partner` or `quote`
   claim as "partner estimate" / "said by <role> on <date>". Verdict `verified` only if the pitch wording matches
   the log and calls it a partner estimate; else `overclaim` with the safer wording.
4. `measured` claims: these cannot be checked on the web. Look for where the measurement is written down
   (`03-research/**`, a demo log the team keeps). Found and it matches → `verified (measured, <where>)`.
   Not found → `needs source` with the fix "write down how it was measured: metric (e.g. recall), n, date,
   data used". Also flag `partner data` if it comes from the partner's data.

Everything not settled here goes to step 4. If `sources.md` does not exist, create it now (step 6 header) and
send every claim to step 4.

## 4. Verify the rest on the web: parallel subagents

If **3 or fewer** claims are left, check them yourself (WebSearch / WebFetch, same rules as the agent file) and
skip to step 5. Otherwise:

Split the open claims into batches by angle. **Always at least 3 agents.** If an angle has more than 12 claims,
split it into two agents. Maximum 5 agents (cap per run). If an angle is empty, move claims so every agent has some.

| Agent | Angle | Claim kinds |
|---|---|---|
| A | Market and statistics: trace each number to the primary source (Eurostat, StatFin, OECD, annual report) | `market`, `stat`, `number` |
| B | Competitors and superlatives: does anyone already do this? is "first/only/best" true? | `competitor`, `superlative` |
| C | People, partner and event: quotes, partner facts, Junction facts | `quote`, `partner`, `event`, leftovers |

**Launch all agents in ONE message** (several Agent tool calls in the same reply) so they run at the same time.
Use `subagent_type: fact-check-verifier`. Fill the prompt from [templates.md](templates.md) "Verifier prompt":
the claims of that batch (copied from `claims.md`), any leads from step 3, the output path
`<WORK>/batch-<A|B|C…>.md`, today's date, and a budget of about 4 searches/fetches per claim (25 max per agent).

Wait for all agents. Read every batch file. Do not trust a verdict whose URL is missing: make it `unverifiable`.
A `snippet-only` source can never make a claim `verified`, but it can show a claim is doubtful (`overclaim`,
`wrong` only if the snippet states the value clearly; otherwise `needs source`).

## 5. Decide the verdict and flags for each claim

**Verdicts** (exactly one per claim):

| Verdict | Meaning |
|---|---|
| `verified` | A real source says the same value, unit, year and geography. Primary or official preferred |
| `needs source` | Probably true or plausible, but no source is cited in the pitch or in `sources.md` yet. Give the source found, or say what to find |
| `wrong` | The source gives a different value or says the opposite. Give the correct value |
| `outdated` | Was true, but a newer figure exists, or the figure is more than 5 years old (market-research §4.4) |
| `unverifiable` | No source found after the budget, page blocked, or only a paid/marketing report. Suggest dropping it or labelling it "assumed" with the reasoning |
| `overclaim` | A source exists, but the pitch wording goes further than it: rounds up, drops "up to", turns EU into Finland, a pilot into "proven", "one of the first" into "first", a partner guess into a fact, one partner's judging criteria into "the jury" |

**Flags** (zero or more per claim, in their own column):
- `no label`: a number with no measured / reported / assumed label nearby (the label may be in a footnote).
- `superlative`: "first", "only", "best", "leading", "unique", "no one". Always flag, even when verified;
  the fix is a narrower wording ("the only tool we found that…, searched <date>").
- `unit/year mismatch`: unit, year or geography differs from the source (EUR vs USD, 2019 vs "today", EU vs FI),
  or two numbers on one slide use different years or units without saying so.
- `inconsistent`: the same thing has different values in different files.
- `fake precision`: "41.37%" where the source is a rough estimate (§3.4: round honestly).
- `single source`: only one source found → also write UNVERIFIED in the fix.
- `secondary`: cited from a blog, news or Statista, not the primary source.
- `partner data`: may be confidential partner data; check with the partner rep before showing it.

## 6. Append newly verified facts to `03-research/sources.md`

- **Append only.** Never change or delete an existing line. Add lines at the end with the Edit tool (match the
  current last line and add below it).
- Append only claims that are `verified` from the web in this run, plus corrected values from `wrong` or
  `outdated` rows that a source confirms. Skip anything already in the file (same URL and same number).
- One line per fact, exact format from `03-research/README.md`:
  `claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence`
  Confidence: `high` (primary, 2+ sources agree), `medium` (primary, one source), `low – UNVERIFIED` (secondary only).
- If the file is missing, create it with the header block in [templates.md](templates.md) "sources.md header".

## 7. Write the report

Path: `04-pitch/fact-check-report.md` (for `--quick`: same file, marked "QUICK" in the title).
Format: [templates.md](templates.md) "Report". It starts with the date line and the "based on core.md" line.

Before writing, if `04-pitch/fact-check-report.md` already exists:
- if it is identical to the `report.md` copy in the run folder its header names (a previous run's own output),
  overwrite it;
- otherwise (a person edited it, or no copy exists) write `04-pitch/fact-check-report-v2.md` (or the next free
  `-vN`) and say so in chat.
Then save the same text as `<WORK>/report.md`.

**"Must fix before presenting"** (top of the report) lists, worst first:
1. every `wrong` claim;
2. every `overclaim` and `superlative` on a slide, a stage script or the submission text;
3. `inconsistent` numbers;
4. `outdated` and `unverifiable` claims that are on a slide or in a stage script;
5. numbers on slides with `no label` or with no line in `sources.md` (every slide number must trace to one).
Each item: claim id, `file:line`, the one-line fix. If nothing qualifies, write "Nothing blocking." and keep it.

Write fixes in plain, common English, as text Madalina can paste: the exact replacement sentence, not advice.
Keep the safer wording honest and short, e.g. "about 1 in 10 orders (reported, Valio Aimo, 2025)".

## 8. Chat summary (short)

- Counts: N claims; verified / needs source / wrong / outdated / unverifiable / overclaim.
- The top 3 "must fix" items, one line each.
- Paths: the report, `<WORK>/`, and how many lines were appended to `03-research/sources.md`.
- Next: fix the pitch files by hand (or ask for it), then re-run `/fact-check --quick` before the stage;
  `/jury-drill` to practise questions on the weak numbers; `/market-scan` if a key number is `unverifiable`.

## Rules (from CLAUDE.md, repeated because they matter here)

- Never edit files in `04-pitch/` other than the report. Never edit existing lines in `sources.md`.
- Never invent a source, URL, number or quote. If you could not open a page, say so; snippets are marked
  `snippet-only` and cannot make a claim `verified` on their own.
- Partner raw data never goes into the report or `sources.md`: aggregates and "partner estimate" only.
- Plain, common English. Short sentences.

## Files
- Templates (claims file, verifier prompt, report, sources.md header): [templates.md](templates.md)
- Verifier subagent: `.claude/agents/fact-check-verifier.md`

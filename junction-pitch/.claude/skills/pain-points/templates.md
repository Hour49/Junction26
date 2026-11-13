# /pain-points templates

## Search plan (`search-plan.md`, written by the main agent before launching subagents)

```markdown
# Search plan: <problem in a few words>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: /pain-points
- Based on core.md: <"Last updated" value of 04-pitch/core.md, or "core.md not filled; input was: <user's words>">
- Problem (one sentence, plain words): <...>
- Our idea (one sentence, or "none yet"): <...>

## Who has this problem (user roles)
- <role 1>, <role 2>, <role 3> (3–6 roles, include the payer and the end user if different)

## How real people would say it (5–10 phrasings, complaint language)
1. "<phrasing>"   (e.g. "my order came with missing items again")
...
Finnish / Nordic (when the problem exists locally):
- "<suomeksi>" (= <English>)

## Synonyms and keywords
- <word> / <word> / <word>
- Competing products or brands people would complain about: <names, only real ones>

## Not this (to avoid noise)
- <meanings of the same words that are off-topic>
```

## Source file (`<source>.md`, one per subagent)

```markdown
# Pain points: <problem> — <source family>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: pain-points-searcher (<source family>)
- Based on core.md: <same line as search-plan.md>
- Question: Do real people on <source family> complain about <problem>?
- Answer in one line: <yes/some/no — n quotes (x exact, y close, z adjacent)>

## Quotes
| # | Quote (exact, ≤40 words) | Platform | Date | Role | Match | Emotion (1–3) | Link |
|---|---|---|---|---|---|---|---|
| 1 | "…" | App Store FI, <app>, 1★ | 2025-03-02 | online grocery customer | exact | angry, 3 | [link](URL) |

Non-English quotes: original in the table; translation as a note under the table: `#n (our translation): "…"`.
Mark `snippet-only` in the Link cell when the page itself could not be opened.
How each quote was copied: helper output (`fetch_public.py <source>`) or WebFetch (short quotes only).

## Statistics found (if any)
- <claim> — <number> (reported) — [source title](URL), accessed YYYY-MM-DD — primary/secondary — UNVERIFIED if single-source

## Words people use
- "<word or phrase they repeat>", "<...>"

## Searched but empty or blocked
- <query> — nothing relevant
- blocked: <url> (<401 / 403 / 429 / login wall / paywall>)

## Pointers, unverified (links seen in search that you could not open, even in Playwright; never quoted)
- <url> — <what the search result suggested>

## Notes
- <patterns, best forum or app for follow-up, which sources worked, anything surprising>
```

## Summary (`summary.md`, written by the main agent)

```markdown
# Pain points summary: <problem>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: /pain-points
- Based on core.md: <same line as search-plan.md>
- Question: Do real people have the exact problem our idea solves?
- Answer in one line: <verdict> — <n> quotes across <k> platforms, <x> exact matches.

## Verdict: STRONG / MEDIUM / WEAK
- Why: <2–4 bullets, with counts>
- What would make it stronger: <e.g. 3 exact quotes from Finnish users; a partner number>
- What would make it weaker: <e.g. most exact quotes are older than 5 years>

## Counts
| Platform / source file | Exact | Close | Adjacent | Total | Strongest emotion |
|---|---|---|---|---|---|
| research | | | | | |
| news | | | | | |
| reviews (app stores, review sites) | | | | | |
| forums | | | | | |
| complaints | | | | | |
| **Total** | | | | | |

## Top 5 quotes for slides
1. "<quote in English; our translation if the original is not English>" — <role>, <platform>, <date> — [link](URL) — <match>
   (Why this one: <short, real, emotional, matches our user>)

## Words people actually use (reuse in the pitch)
- "<phrase>" (seen n times, platforms)
- Words they do NOT use (avoid in the pitch): <our jargon that nobody says>

## Strongest statistic
- <claim> — <number> (reported) — [source](URL), accessed YYYY-MM-DD — passes the playbook §4.4 bar? <yes/no, why>
- Suggested slide line: "<one sentence in the user's unit>"

## Gaps and next steps
- Blocked sources: <list of `blocked:` lines from the source files, or "none">
- <missing source, needs a live interview at the event (playbook §2.3)>
- Suggested next skill: <...>
```

## `03-research/sources.md` line (append only)

```
claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence
```
Example (shape only, not a real fact):
```
share of online grocery orders with a missing item | <n> | % of orders | 2024 | Finland | <report title> | <URL> | 2026-11-13 | primary | medium (UNVERIFIED, single source)
```

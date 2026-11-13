# /fact-check templates

Sections: Claims file · Verifier prompt · Batch file · Report · sources.md header.

---

## Claims file

Path: `03-research/fact-check/<RUN>/claims.md`

```markdown
# Claims extracted: <RUN>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: /fact-check
- Based on core.md: <"Last updated" value from 04-pitch/core.md, or "template, not filled">
- Scope: <files checked> · Mode: <full | quick>

| id | claim (exact, short) | file:line | kind | value | unit | year | geo | label in pitch | step-3 result |
|---|---|---|---|---|---|---|---|---|---|
| C1 | "1 in 10 orders misses an item" | 04-pitch/deck/outline.md:12; 04-pitch/core.md:9 | stat | 10 | % of orders | — | — | none | → web (batch A) |
```

`step-3 result`: `verified (sources.md line N)`, `lead: <URL>`, `feedback log <date>`, `measured: <where>`,
or `→ web (batch X)`.

---

## Verifier prompt

Fill the `<…>` parts. One prompt per agent, all agents launched in ONE message.

```text
You are fact-check verifier <X> for the /fact-check skill. Follow your agent instructions.

Angle: <Market and statistics | Competitors and superlatives | People, partner and event>.
Today's date: <YYYY-MM-DD>. Budget: about 4 searches/fetches per claim, 25 in total.
Context: hackathon pitch for Junction 2026 (Espoo, Finland). Challenge/partner: <from core.md, or "unknown">.
Idea in one line: <one-liner from core.md>.

Claims to check (keep the ids):
<rows copied from claims.md for this batch>

Leads already found (start here; still open the page yourself):
<C-id: URL, or "none">

Write your results to: <03-research/fact-check/<RUN>/batch-<X>.md>
Use the "Batch file" format in .claude/skills/fact-check/templates.md exactly.
Return only the file path and the count per verdict (max 60 words).
```

---

## Batch file

```markdown
# Fact-check batch <X>: <angle>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: fact-check-verifier <X>
- Searches/fetches used: <n>

| id | claim | verdict | what the source says (value, unit, year, geo) | correct value or safer wording | source title | URL | accessed | primary/secondary | notes |
|---|---|---|---|---|---|---|---|---|---|
| C1 | "1 in 10 orders misses an item" | overclaim | "up to 8% of online grocery orders have a missing item", US, 2023 | "up to 8% of online grocery orders (US, 2023, reported)" | <title> | <URL> | YYYY-MM-DD | secondary | single source; snippet-only for the second link |

## Blocked or empty searches
- <query or URL> — <blocked / nothing found>
```

---

## Report

Path: `04-pitch/fact-check-report.md` (copy at `03-research/fact-check/<RUN>/report.md`).

```markdown
# Fact-check report<" (QUICK)" if --quick>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: /fact-check · Run folder: 03-research/fact-check/<RUN>/
- Based on core.md version/date: <"Last updated" value>
- Scope: <files> · Mode: <full | quick> · Claims: <N>
- Result: <n> verified · <n> needs source · <n> wrong · <n> outdated · <n> unverifiable · <n> overclaim
- Appended to 03-research/sources.md: <n> lines

## Must fix before presenting

1. **C4 wrong**, `04-pitch/deck/outline.md:14`: change "€2 bn market" → "<exact replacement sentence>".
2. ...

(or "Nothing blocking.")

## All claims

| id | claim | file:line | verdict | flags | correct value or safer wording | source URL | accessed |
|---|---|---|---|---|---|---|---|
| C1 | ... | ... | ... | no label; superlative | ... | ... | YYYY-MM-DD |

## Not checked
- <binary files skipped, blocked pages, claims over budget>

## Notes
- <cross-file inconsistencies, slide footnotes missing, anything the team must ask the partner rep>
```

Rules for the table:
- One row per claim; several `file:line` values separated by `;`.
- "correct value or safer wording" is paste-ready text, not advice. For `verified` with no flags write "OK".
- Source URL is the best source (primary first). For `verified` from `sources.md` write the URL from that line and
  add "(sources.md)". No URL → write "none" and the verdict cannot be `verified`.

---

## sources.md header

Use only if `03-research/sources.md` does not exist yet.

```markdown
# Sources log

One line per fact used anywhere in the pitch. Append only. Format and rules: [README.md](README.md).

claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence
---|---|---|---|---|---|---|---|---|---
```

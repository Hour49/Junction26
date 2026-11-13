# /feedback templates

## Log file header
Used only when `03-research/feedback/log.md` is missing.

```markdown
# Feedback log

- Created: YYYY-MM-DD HH:MM (Helsinki) · Written by /feedback
- Based on core.md: each entry records the core.md "Last updated" value it was logged against.
- Who = role + company only. No personal names or contact details.
- Status: OPEN → RESEARCHING → RESEARCHED → APPLIED / REJECTED (with why) / DONE
- Commands: `/feedback <who>: <notes>` · `/feedback summary` · `/feedback close F-012 <outcome>`

<!-- entries: newest first -->
```

## Log entry
Insert directly under `<!-- entries: newest first -->`. Leave out nothing; use `—` for empty buckets.

````markdown
## F-012 · 2026-11-13 21:40 · Mentor, Valio Aimo · OPEN
- Based on core.md: <Last updated value, or "template, not filled yet">
- Setting: <30-s intro / table demo / booth chat / rehearsal / unknown>
- Notes as typed: "<her notes, private details removed>"
- Signal: <commitment if any: offered data, intro, time, "come to our table"; else "compliments only">

**Liked**
- <item>

**Concerns**
- <item>

**Similar products named** (their claim, UNVERIFIED until checked)
- <product/company>: <what they said it does>

**Questions they asked**
- <question>

**Research requests**
- <item>

**Suggested idea changes**
- <item>

**Actions**
- [ ] F-012.1 `/market-scan <name>`: <why> (running → [followups/F-012-<topic>.md](followups/F-012-<topic>.md))
- [ ] F-012.2 `/fact-check <claim>`: <why>
- [ ] F-012.3 `/jury-drill`: add "<question>"; answer needs <number/source>
- [ ] F-012.4 Ask <role> at <place>: "<exact question>" (Madalina)

**Proposed core.md changes** (not applied; Madalina decides)
```diff
- <line as it is in core.md now>
+ <proposed line> (backed by F-012.n)
```

**Status log**
- 2026-11-13 21:40 OPEN
````

## Subagent prompt
Fill every `<…>`. One prompt per subagent; each gets a different item.

```
You are the feedback-followup agent. Feedback ID: <F-012>. Item <F-012.n>.
Who said it: <role, company>. What they said: "<the fragment, no names>".
Question to answer: <one precise question, e.g. "Does Picnic offer automatic substitutions for
out-of-stock grocery items, and how do customers approve them?">
Our idea in one line: <from core.md, or the practice idea if core.md is empty>.
Today: <YYYY-MM-DD>. core.md last updated: <value>.
Write to: 03-research/feedback/followups/<F-012-topic>.md, using the "Follow-up file" section of
.claude/skills/feedback/templates.md. At most ~6 searches. Return path + one-line answer + confidence.
```

## Follow-up file

```markdown
# F-012.n: <topic>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: feedback-followup agent
- Based on core.md: <Last updated value>
- Question: <the one question>
- Answer in one line: <answer> (confidence: high / medium / low)

## Findings
- <finding> — <number if any> (<measured|reported|assumed>) — [source title](URL), accessed YYYY-MM-DD

## What this means for the pitch
- <how it changes our difference vs alternatives, a Q&A answer, or nothing>

## Open questions / UNVERIFIED
- <item>

## Searched
- <queries tried, including ones that found nothing>
```

## Summary file

```markdown
# Feedback summary

- Date: YYYY-MM-DD HH:MM (Helsinki) · Written by /feedback summary
- Based on core.md: <Last updated value>
- Entries: <n> (F-001 … F-0NN) · People: <n> (jury <n>, partner <n>, mentor <n>, peer <n>) · Open actions: <n>

## Top 3 changes to consider
1. **<change>** — said by <n> people (<F-IDs>). Evidence: <follow-up answer + link>.
   ```diff
   - <core.md line now>
   + <proposed line>
   ```

## Patterns (2+ different people)
| Point | Who said it | F-IDs | Checked? |
|---|---|---|---|

## Said once
- <point> (F-0NN, <role>)

## Open items by next skill
- `/market-scan`: F-0NN.n <item>
- `/fact-check`: …
- `/pain-points`: …
- `/jury-drill`: …
- Pitch skills: …
- Madalina asks in person: …
```

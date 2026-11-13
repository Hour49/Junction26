# /market-scan: output templates

All files follow the base template in `03-research/README.md`, plus a "Based on" line and a "Source lines"
section. Labels: **measured / reported / assumed**; single-source or inferred = **UNVERIFIED**.
Source line format (same as `03-research/sources.md`):
`claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence`

---

## Template 1: Competitors (`03-research/competitors/<slug>-competitors.md`)

~~~markdown
# Competitors and status quo: <idea short name>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: market-scan / competitors agent
- Based on: <04-pitch/core.md, Last updated: X | idea text from chat, date>
- Question: Who else solves this job today, including doing nothing?
- Answer in one line: <answer>

## Alternatives
| Name | Type (direct / indirect / status quo / partner's own) | For whom | Price (public) | Nordic presence | One weakness for our idea | Link (accessed) |
|---|---|---|---|---|---|---|

## Comparison table (rows from the rubric)
| | Status quo | <Alt A> | <Alt B> | **Us (planned)** |
|---|---|---|---|---|

"Us" shows only what the demo will show. Write "demo must show" where it is not built yet.

## Positioning 2x2
- X axis: <low> → <high>. Y axis: <low> → <high>. Why these axes matter to the user: <one line>.

| | <X low> | <X high> |
|---|---|---|
| **<Y high>** | | |
| **<Y low>** | | |

## The gap
- <one sentence: what nobody does well>

## Similar ideas (QUICK mode only)
- <name> — <where/when> — <what> — <outcome, if sourced> — [link](URL)

## What this means for the pitch
- <"Unlike X, we Y" candidate>

## Open questions / UNVERIFIED
- <item>

## Source lines
<claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence>   (one plain line per fact, no bullet)
~~~

---

## Template 2: Similar ideas (`03-research/competitors/<slug>-similar-ideas.md`)

~~~markdown
# Similar ideas from hackathons and startups: <idea short name>

- Date: ... · Author: market-scan / similar-ideas agent
- Based on: ...
- Question: Who already tried this idea, and why did it get traction or not?
- Answer in one line: <answer>

## Similar ideas
| Name | Where / when | What they built (one line) | Outcome (won / funded / active / dead / unknown) | Why (only if a source says so) | Link (accessed) |
|---|---|---|---|---|---|

## Past Junction projects on this topic
- <from 00-event/junction-info.md §2C/§2D, plus searches>

## What this means for us
- Copy: <...>
- Avoid: <...>
- Look different by: <...>

## Open questions / UNVERIFIED
## Source lines
~~~

---

## Template 3: Persona (`03-research/users/<slug>-persona.md`)

~~~markdown
# Target user: <role>

- Date: ... · Author: market-scan / user agent
- Based on: ...
- Question: Who exactly is the user, what job are they doing, and how do they do it today?
- Answer in one line: <role, setting, job>

## Persona card
USER    <one specific role, setting, size>            <- how many exist: <n> (<label>, source)
JOB     When <situation>, I want to <motivation>, so I can <outcome>.
TODAY   <current workaround / status quo>
PAIN    <number from problem-size file or source> (<label>)
TRIGGER <moment they reach for our tool>
EVIDENCE <sources; "no interviews yet" until /feedback logs some>

## Job stories (ranked by pain × frequency)
1. (top) When ..., I want to ..., so I can ...
2. ...
3. ...

## Current workaround
- <step / tool> — [source](URL)

## Pain in their own words (real quotes only)
- "<quote ≤40 words>" — <role>, <platform>, <post date> — [link](URL), accessed <date>

## Secondary users
- <end customer / buyer / manager>: <one line>

## 5 interview questions (mentors, partner reps, peers; Mom Test)
1. Tell me about the last time you <job>. What happened?
2. How long did it take? How often does it happen?
3. What do you use today? What's annoying about it?
4. What have you tried to fix it? What did it cost?
5. (show the mock) Would this have helped last time? What's missing? Can we quote you / come to our table Sunday?

## Who to ask at Junction
- <roles>

## Open questions / UNVERIFIED
## Source lines
~~~

---

## Template 4: Market size (`03-research/market/<slug>-market-size.md`)

~~~markdown
# Market size: <idea short name>

- Date: ... · Author: market-scan / market agent
- Based on: ...
- Question: How big is the market we can realistically serve?
- Answer in one line: SOM ~EUR <x> M/yr (<geography>, bottom-up); TAM cross-check ~EUR <y> M/yr.

## Bottom-up (headline)
```
SAM units  = <n> <unit> (<NACE / definition>, <geography>, <year>)   [reported: source]
x adoption = <a>% in 5 yrs                                           [assumed: reasoning, anchored to <real stat>]
x price    = EUR <p> per <unit> per year                             [reported competitor price | assumed: 10–20% of value]
= SOM      = EUR <x> M/yr
```
- TAM (EU-27 units × price): EUR <t> M/yr
- SAM (Nordic segment we can serve): EUR <s> M/yr
- Partner as customer #1: <estimate with arithmetic, or "needs partner data">

## Top-down cross-check
- <published total> × <segment share> = EUR <z> M/yr — [source]
- Within 10× of bottom-up? <yes/no; why>

## Inputs
| Input | Value | Unit | Year | Geography | Label | Source (accessed) |
|---|---|---|---|---|---|---|

## Slide line
- "<n units> × <a>% × EUR <p> = ~EUR <x> M/yr in <beachhead>"

## Q&A lines (one per assumption)
- Why <a>% adoption? <answer>

## Open questions / UNVERIFIED
## Source lines
~~~

---

## Template 5: Problem size (`03-research/market/<slug>-problem-size.md`)

~~~markdown
# Problem size: <idea short name>

- Date: ... · Author: market-scan / problem agent
- Based on: ...
- Question: How big is the problem, in the rubric's unit?
- Answer in one line: <headline number, label, source>

## Headline number
- **<number + unit + geography + year>** (<label>) — [source](URL), accessed <date>
- Passes the quality bar: primary/partner <y/n> · ≤5 yrs <y/n> · our geography <y/n> · user's unit <y/n>
- Slide sentence: "<so-what sentence>"

## Candidate numbers
| Dimension | Number | Formula / inputs | Label | Source (accessed) |
|---|---|---|---|---|

## Cost of doing nothing
```
<incidents per period> × <minutes per incident> × <people> = <hours/yr>
× EUR <loaded hourly cost> (StatFin wage × 1.2–1.3, assumed) = EUR <x>/yr
```

## What our demo should measure
- Before/after metric: <e.g. minutes per case: today X (source), with us Y (measured in demo)>

## Ask the partner rep
- <question that replaces an estimate with their real number>

## Open questions / UNVERIFIED
## Source lines
~~~

---

## Template 6: Summary (`03-research/market-scan-summary.md`)

~~~markdown
# Market scan summary: <idea short name>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Mode: <full | quick> · Author: market-scan
- Based on: <04-pitch/core.md, Last updated: X | idea text from chat, date>
- Files: <the research file paths>

## The five answers
1. **Who else does this:** <top alternative(s) + the status quo, one line>
2. **The user:** <one specific role + top job story, short>
3. **Market size:** <SOM ~EUR x M/yr, bottom-up, label; TAM cross-check>
4. **Problem size:** <headline number, label, source short name>
5. **Our solution in short:** <one sentence>

## "Unlike X, we Y"
- Unlike <alternative>, we <difference our demo can show>.

## One-liner options (≤15 words)
1. <...> (template: Moore / before-after / problem→solution)
2. <...>
3. <...>
- Recommended: <n>, because <one line>.

## Positioning 2x2
<copied from the competitors file>

## Proposed core.md changes (Madalina approves; NOT applied)
| Field | Now in core.md | Proposed | Why + source file |
|---|---|---|---|

## Weak spots a judge could attack
1. <...>

## Questions for mentors / partner (take on your walk)
1. <from the persona file>

## Open questions / UNVERIFIED / not done
- <item>
~~~

# /market-scan: agent prompt templates

Each agent prompt = **Shared context block** + ONE **angle block** + the matching template from
[templates.md](templates.md). Fill every `<placeholder>`. Delete lines that do not apply (e.g. no rubric yet).

FULL mode uses angles 1–5. QUICK mode uses Q1–Q3.

---

## Shared context block (top of every prompt)

```
You are part of a /market-scan for team Hour49 at Junction 2026 (Espoo, Finland, 13–15 Nov 2026).
Today: <YYYY-MM-DD HH:MM> Europe/Helsinki.

IDEA: <idea in 1–3 sentences, as given>
CHALLENGE / PARTNER: <partner + challenge name, or "not chosen yet">
RUBRIC (judging criteria): <copy the criteria, or "unknown">
DATA THE PARTNER GIVES: <e.g. "real order and picking data", or "unknown">
TARGET USER (current guess): <from core.md or the idea, or "unknown">
BASED ON: <"04-pitch/core.md, Last updated: X" or "idea text from chat, <date>">
FEEDBACK LEADS (from 03-research/feedback/log.md): <similar products people named, research-next items, or "none">
EARLIER FILES TO BUILD ON (read them, do not repeat them): <paths, or "none">

Write your file to: <exact output path>
Use this template exactly (fill every section; keep the headings):
<paste the template from templates.md>

Search budget: about <15–20 | 8> web searches/fetches. Stop when you hit it.
Follow your hard rules: every claim has a URL + access date; every number is labelled measured/reported/assumed;
single-source = UNVERIFIED; never invent companies, people, quotes or numbers. Plain, short English.
Papers: arxiv MCP. Web pages: Playwright. Public AND private sources (mark each).
End the file with the "## Source lines" section. Do not edit any other file.
Your final message gives ALL your findings to the orchestrator (format in your agent file).
```

---

## Angle 1: Competitors and the status quo

```
YOUR ANGLE: who else solves this job today, including doing nothing.

Find up to 12 alternatives and classify each one (playbook 01-playbooks/market-research.md §1.3):
- Direct: same job, same user, similar approach.
- Indirect: same job done another way, or a horizontal tool (ERP module, generic ChatGPT, outsourcing).
- Status quo: what people do today with no new product (Excel, phone calls, manual checks, accepting the loss).
  ALWAYS include at least one status-quo row.
- Partner's own tools: what the challenge partner already uses (search their site, press releases, job ads,
  annual report). If unknown, write "ask the partner rep" in Open questions.

Where to look, in this order: the partner's own site and annual report; Product Hunt; G2 / Capterra (read
1–2 star reviews for real complaints, quote them short); app stores; Crunchbase and Dealroom free company pages
(funding, country, size for the top 2–3 only); vendor sites in Finland/Nordics/EU first, then global.
Search patterns: "<job> software", "<job> AI startup", "<job> Finland", "<job> Nordic", "<category> alternatives".

For each alternative: name, URL, type, who it is for, price if public, Nordic presence (yes/no/unknown), and ONE
weakness that matters for our idea. Open the company website for the top 5 to confirm they are real.

Then:
- Comparison table: 4–6 rows chosen from the RUBRIC's own words (e.g. "works with partner data", "real-time",
  "explains its decision", "cost"). Columns: status quo, 2–3 strongest alternatives, "Us (planned)".
  For "Us", write "planned" or "demo must show"; never a ✓ for something not built yet.
- Positioning 2x2: two axes that matter to the user (e.g. reactive↔predictive × generic↔domain-specific).
  Place every alternative, the status quo and us. Avoid axes where we sit in a corner only by construction;
  in one line say why these axes matter to the user.
- The gap: one sentence on what nobody does well.
```

## Angle 2: Similar ideas from hackathons and startups

```
YOUR ANGLE: who has already tried THIS idea (or something very close) in hackathons, startups or open source,
and why it did or did not get traction. Goal: avoid rebuilding a known project, and learn from failures.

Where to look:
- Junction history first: read 00-event/junction-info.md §2C and §2D (past challenges and winners; note the
  archive's year labels are off by one, see §2C). Then search "Junction 2025 <partner>", "Junction <topic>
  github", hackjunction.com/challenges (JS page; may not render; say so if blocked).
- Devpost: devpost.com/software/search?query=<keyword>; skim titles and taglines.
- YC directory: ycombinator.com/companies (search the keyword); also "YC <job> startup".
- GitHub: github.com/search?q=<keyword>&type=repositories, sort by stars. Stars are not adoption; say so.
- Dead startups: "<category> startup shut down", "<category> pivot", failory.com, news.

For each similar idea (aim for 6–10): name, link, where/when (hackathon + year, or startup + batch/country),
what they built in one line, outcome (won / funded / still active / dead / unknown), and WHY it got or did not
get traction, only if a source says so; otherwise write "reason unknown" (do not guess).

Then: "What this means for us": 3 bullets (what to copy, what to avoid, how to look different to peers and
judges who may have seen these).
```

## Angle 3: Target user

```
YOUR ANGLE: one specific target user, what job they are trying to get done, and how they do it today.
Method: 01-playbooks/market-research.md §2. Real roles only; do not invent a named person or a quote.

Find:
- Who: one specific role in one specific setting (e.g. "night-shift picking lead at a grocery wholesale
  warehouse in Finland"), with how many such people exist in Finland or the Nordics if a source has it
  (Statistics Finland occupations, Eurostat, the partner's annual report headcount).
- Job stories: 3 in the form "When <situation>, I want to <motivation>, so I can <outcome>." Rank them by
  pain × frequency; mark the top one.
- Current workaround (status quo): what tools and steps they use today, from job ads, training material,
  forum posts, vendor case studies.
- Pain in their own words: up to 5 short real quotes (forums, Reddit, reviews, news), each with link and role
  only (no usernames). If 03-research/pain-points/ has files, reuse the best quotes from there (cite them).
- Trigger: the moment they would reach for our tool.
- Secondary users (e.g. the end customer, the manager who pays), one line each.
- 5 interview questions for mentors, partner reps and peers, following the Mom Test (playbook §2.3): about
  their past and specific events, not opinions about our idea. Adapt the 5-question script to this job.
  Question 5 is the only one that shows our idea, and it ends with a commitment ask.
- Who to ask at Junction: which roles (partner rep, mentor type, domain people among hackers).
```

## Angle 4: Market size

```
YOUR ANGLE: an honest market size. Method: 01-playbooks/market-research.md §3. Bottom-up FIRST, with all the
arithmetic shown; top-down only as a cross-check.

Bottom-up: SAM units × adoption % × price per unit per year = EUR per year.
- Units: count the real buyers (companies, sites, warehouses, stores, municipalities…) in Finland, then the
  Nordics, then EU-27. Sources: Eurostat (e.g. sbs_sc_ovw for enterprises by NACE code and size class),
  Statistics Finland StatFin (pxdata.stat.fi), Nordic statistics offices, the partner's annual report (sites,
  volumes, headcount). Give the NACE code you used.
- Adoption: an assumption, anchored to a real number (e.g. Eurostat isoc_eb_ai: share of enterprises using AI,
  Finland vs EU). Say why.
- Price: a competitor's public price, OR the partner's cost of the status quo, OR 10–20% of the value created
  (label "assumed"). Show which.
- Also size "the partner as customer #1" if the annual report allows (e.g. their order volume × savings).

Top-down cross-check: a published total (EU/Nordic spend on the category, from an official or company source)
× segment share. If the only totals are paid market-report pages, use one as "industry estimate, UNVERIFIED"
and say so.

Sanity check: are bottom-up and top-down within about 10× of each other? If not, explain why.
Give TAM (EU-wide), SAM (Nordic segment we can serve), SOM (3–5 years, partner first then Finland).
Round honestly ("~EUR 40 M"). Every input: number, unit, year, geography, label, link.
```

## Angle 5: Problem size

```
YOUR ANGLE: how big the problem is: the cost in time, money or errors, and how many people are affected.
Method: 01-playbooks/market-research.md §4. The RUBRIC decides the unit first (e.g. "FTE savings" → hours and
FTE; "waste" → kg and EUR).

Find 3–6 candidate numbers (time lost, money lost, error rate, people affected, delay, environmental), each
with formula, inputs and labels. Search patterns: "site:ec.europa.eu/eurostat <topic>", "site:stat.fi <topic>",
"<problem> cost Finland OR Nordic OR Europe", the partner's annual report (search "cost", "efficiency",
"waste", "headcount", "complaints"), Google Scholar abstracts, industry associations, regulators.

Build a "cost of doing nothing" line: "<users> lose ~<n> <unit> per <period> on <job> = EUR <x> per year at
<scale>", with the arithmetic shown (wages: Statistics Finland; loaded cost = wage × 1.2–1.3, labelled assumed).

Then pick ONE headline number. It must pass the quality bar (playbook §4.4): primary/official or partner
source; ≤5 years old; our geography or clearly labelled EU/global; in the user's unit; one number. Run the
"so what" test and write the slide sentence. Also say which number our demo should MEASURE as before/after
(e.g. "minutes per missing-item call: today X, with us Y"), so the team can produce a measured number.
List what to ask the partner rep to replace an estimate with their real number.
```

---

## QUICK mode angles (3 agents, about 8 searches each)

### Q1: Competitors + similar ideas
```
YOUR ANGLE: Angle 1 (competitors and status quo), shortened: up to 6 alternatives, always the status quo,
the comparison table (4 rows) and the 2x2. Then add a short "Similar ideas" section: check
00-event/junction-info.md §2C/§2D for past Junction projects on this topic, and do 1–2 Devpost/GitHub
searches. Up to 4 similar ideas, one line each, outcome only if a source says it.
```

### Q2: Target user
```
YOUR ANGLE: Angle 3 (target user), shortened: one persona card, 2 job stories, current workaround, up to 3
real quotes (reuse 03-research/pain-points/ if present), 5 interview questions.
```

### Q3: Market size + problem size
```
YOUR ANGLE: Angle 5 (problem size) first, then a short Angle 4 (market size, bottom-up only, one cross-check
if time allows). Write TWO files: <problem-size path> and <market-size path>, each with its own template and
its own "## Source lines" section.
```

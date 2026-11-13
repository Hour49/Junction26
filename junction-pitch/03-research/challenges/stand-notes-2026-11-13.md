# Partner stand notes and first challenge ranking (before the official briefs)

- Date: 2026-11-13 17:50 (Helsinki) · Author: Bogdan (talks at the stands) and his Claude orchestrator (research,
  analysis)
- Question: what do the partners next to our spot want, what do we still have to ask them, and which challenge fits
  team Hour49 best?
- Answer in one line: **Stoa first, Cala second, Hostinger third**, pending the official briefs (Fri 18:00) and two
  answers: can Stoa give us a sample folder tonight, and does Cala's data carry dates we can backtest on?

Status: what the partners said is verbal, told to Bogdan at the stands on 2026-11-13 around 17:45; it is
**UNVERIFIED until the official brief** (platform "Challenges" tab or the opening videos). When `/challenge-pick` runs on
the official briefs, its `ranking.md` supersedes the ranking here.

## 1. What the partners said they want (verbal, 2026-11-13)

| Partner | What they want (Bogdan's notes) | Track (from `00-event/junction-info.md` §2A, inferred) |
|---|---|---|
| **Stoa** | "You get architectural files, multimodal etc., written legacy, and you standardise these to make sure they are up to date, make them in a standard format, then to be able to be fed into an AI for easier access, with potential 3D drawings." | not assigned on the site; most likely **Data** (assumed): ask the rep or check the platform Challenges tab |
| **Cala** | "A way to find unicorn companies, like an algorithm." | FinTech (with S-Pankki), UNVERIFIED |
| **Hostinger** | "An app built on their setup which detects propaganda." | Agentic AI, UNVERIFIED |

Not yet asked: Valio Aimo, Google DeepMind, AstraZeneca, MariaDB, Verda (questions in §5).

## 2. Stoa: legacy architectural files to a standard, AI-ready format (3D optional)

**Who they are (reported):** Stoa, [stoabuild.com](https://stoabuild.com/) (linked from the Junction 2026 partner wall
as a major partner, [2026.hackjunction.com](https://2026.hackjunction.com/), accessed 2026-11-13 18:05): "AI for
construction projects, answered from your own documents". It reads a project's drawings, specifications, contracts,
schedule and site records and answers with the document and page behind every answer; hosted in the EU; "live in two
days"; used on "more than twenty Nordic sites, from data halls to rail"; claims "a week back per project engineer" and
"2–8 h shorter from problem raised to decision made" (their claims, reported). Track: the site does not assign Stoa to
a track; Data is the closest (assumed).

Full partner profile with their product, examples and claims: [stoa-legacy-files/partner.md](stoa-legacy-files/partner.md).
What we can build without architecture expertise (sheet register, gap and conflict finder, renovation 3D): [stoa-legacy-files/ideas.md](stoa-legacy-files/ideas.md).

**What this changes:** the cited question answering is **their product**. Don't rebuild it. Our build is the layer in
front of it: turning messy legacy and multimodal files into a standard, up-to-date format their kind of system can
ingest (and the 3D view). Ask what format their pipeline takes in. EU hosting matters to them, so expect EU-only data
rules (Verda's EU GPUs then beat a US cloud LLM).

**Existing product to know:** Make a BIM, a Helsinki startup (founded 2023), turns 2D architectural drawings into BIM
models with AI and has modelled about a thousand buildings (reported)
([Uusimaa Regional Council](https://uudenmaanliitto.fi/en/make-a-bim-uses-ai-to-transform-building-information-modeling/),
[Tampere University](https://research.tuni.fi/cme-en/livecol/make-a-bim-turns-2d-drawings-into-3d-models-with-the-help-of-ai/),
accessed 2026-11-13). So our angle is cleaning up and querying messy legacy archives, not 2D-to-3D alone.

**A build that could win (assumed):**
1. Ingest a messy folder: scanned drawings, PDFs, DWG/DXF, old text specs, photos.
2. Extract with a vision model (Gemini reads drawings and long PDFs): title block (project, revision, date), rooms,
   doors, dimensions, materials. Every fact keeps a link to the spot on the source sheet.
3. Standardise into one schema (building > floors > spaces > elements), each fact with source and date; export to IFC
   (the open BIM standard) if they want it.
4. "Up to date": pick the latest revision, flag drawings that conflict or are out of date.
5. Ask it: chat answers ("where are the fire doors on floor 3?", "which drawings predate the last renovation?") with
   citations to the drawing.
6. Stretch: extrude the extracted walls into a simple 3D model in the browser (three.js).
7. The number: extraction accuracy on a sample they already checked by hand, and time to answer vs searching by hand.

**Questions for Stoa:**
- Which files exactly (scans, PDFs, DWG, IFC, Word/Excel, photos), how old, which language, how many? **Can we get a
  sample folder tonight?**
- "Standard format": do they have a target (IFC, their own schema, a naming standard such as ISO 19650) or do we
  propose one?
- "Up to date": how do they know which version is current (revision blocks, dates, change logs)? Is finding outdated
  or conflicting documents part of the task?
- Who asks the AI what (facility managers, renovation planners, architects, permit officers)? 3-5 example questions.
- 3D: scored or a bonus? Rough massing from 2D, or real IFC walls?
- Judging criteria, prize, would they pilot it, do they have a hand-checked set to compare against?
- Data rules: may files go to cloud LLMs, or must they stay in the EU (decides Gemini vs models on Verda GPUs)?
- What does Stoa do, and what would they use this for?

**Fit:** document agents are our track record (eGata, a city-hall paperwork agent); AI/backend people build the
extraction pipeline and agents, frontend/design builds the 3D viewer and UI, the business lead interviews facility
managers. Stacks with DeepMind (multimodal: a strong "best use of Gemini" case), Verda GPUs, MariaDB vector search.
**Risk:** reading drawings well in 48 h is hard: limit to floor plans plus title blocks, 3D as extruded walls only.

## 3. Cala: "find future unicorns, like an algorithm"

**Who they are (reported):** a verified knowledge layer for AI agents: turns web content into typed facts with sources,
confidence scores and provenance; API and an MCP server (`https://api.cala.ai/mcp/`, tool `knowledge_search`), a
LangChain integration (`langchain-cala`)
([mcpservers.org](https://mcpservers.org/servers/docs-cala-ai-integrations-mcp),
[LangChain docs](https://docs.langchain.com/oss/javascript/integrations/providers/cala),
[getdarwin.ai](https://content.getdarwin.ai/en/cala-ai-structured-knowledge-for-ai-agents), accessed 2026-11-13).
Workshop Sat 11:15 (`00-event/junction-info.md` §2A).

**A build that could win (assumed):** a ranking model that is backtested and explains itself.
- Snapshot companies as of a past date (e.g. 2019), predict which became unicorns by now, report precision on the top 50
  against the base rate. One clear number.
- Every score comes with Cala's sourced facts as the "why" (funding speed, top-tier investors, founder track record,
  hiring growth, sector momentum): provenance is Cala's selling point.
- An agent that researches any startup on demand and returns its score with citations; an investor dashboard.

**Questions for Cala:**
- **Point-in-time data:** do facts carry dates, so we can backtest without leaking the future? Without it the
  algorithm can't be proven. Most important question.
- Ground truth: do they give a list of known unicorns, or do we label them?
- Scale: can we pull thousands of companies, or only query one at a time? Weekend rate limits?
- Coverage: which fields are strong (rounds with dates and amounts, investors, founders' history, headcount)? Nordic
  and EU coverage?
- Do they judge the algorithm itself (ranking on a hidden set) or a product for VCs? Does explainability count?
- Horizon: "unicorn within N years"? May we add public data (GitHub, job posts, web traffic)?

**Fit:** data plus agents, two teammates are into finance, the business lead can frame it for VCs, frontend builds the
dashboard. Strong if the data can be backtested.

## 4. Hostinger: "an app on their setup that detects propaganda"

**Who they are (reported):** web hosting plus Horizons (builds a site or app from a prompt) and "Hostinger Agent" chat.
Official API MCP server (`hostinger-api-mcp`: domains, DNS, hosting, VPS; also hosted at `mcp.hostinger.com`, needs
an API token); its Horizons part is small, about 2 tools (create a site from a prompt, check its status)
([Hostinger support](https://www.hostinger.com/support/11079316-hostinger-api-mcp-server/),
[Hostinger docs](https://docs.hostinger.com/hostinger-connector/overview),
[changelog](https://www.hostinger.com/changelog), accessed 2026-11-13). Keynote Sat 13:00.

**A build that could win (assumed):** a polished live app that finds the manipulation techniques, not a true/false
verdict: paste a URL, post or transcript; it highlights spans and labels the technique (loaded language, appeal to
fear, whataboutism, name-calling, flag-waving, ...) with a short explanation. Number: score on a public
propaganda-technique dataset (a SemEval news task exists for this: UNVERIFIED, check before citing). Could combine Cala
(verify factual claims) and Gemini (video and images). European disinformation angle fits "European Tech Renaissance".

**Questions for Hostinger:**
- Does "their setup" mean built with Horizons, or hosted on Hostinger (hosting/VPS with our own backend)? Credits, API
  token, MCP access? A sandbox so nothing buys a domain or charges a card?
- Users: readers, journalists, moderators, schools? Languages (English, Finnish, Russian)?
- Manipulation techniques or false claims? How do they want political neutrality handled?
- Judged how: their test examples, a dataset, a live demo? Must it be live on a Hostinger domain at judging?
- Inputs: text, URLs, social posts, video?

**Fit:** easy to demo; LLM pipelines plus design. Risk: many teams will build an LLM-classifier app, and the topic is
politically sensitive.

## 5. Questions for the other partners near our spot

Ask every partner: what exactly is the challenge and what data or APIs do we get Friday night (real or mock)? How is
it scored, is there a number (time, cost, FTE)? Who is the real user, can we talk to one this weekend? What did last
year's winner do that others didn't? Would you pilot a good demo?

- **Valio Aimo** (Valio's food-service wholesale and logistics arm). 2025 challenge "Zero-Fail Logistics": predict
  missing items, voice-first customer care; real order and picking data; judged on production feasibility, FTE
  savings; "strong demos considered for real development" (`00-event/junction-info.md` §2C). Ask: same problem area in
  2026? Which data, how many months? Can we talk to picking or customer service? What does "production-ready" mean
  (their systems, a handheld app, voice)?
- **Google DeepMind** (special partner, keynote and workshop Fri 20:15): what is the prize and how is it judged? Which
  models and quotas (Gemini, Live API for real-time voice, Gemma)? Does "best use of Gemini" need a specific feature?
- **Verda** (formerly DataCrunch, Helsinki GPU cloud, owns the AI Infrastructure track, workshop Fri 20:45): GPU credits
  and how to claim them? Serverless inference endpoints? What does the track reward (cost, latency, open models,
  fine-tuning)?
  What Verda offers, prices and how it fits: [verda-infra.md](verda-infra.md).
- **MariaDB** (Data track, inferred): a challenge or only credits? Vector search and RAG inside MariaDB, or their
  cloud? An MCP server? Could stack on Stoa or Valio Aimo.
- **AstraZeneca** (Healthcare track, inferred): which data, synthetic? R&D, clinical trials, patients? Regulatory
  frame? Is there a document or paperwork workflow (our only real angle)?

## 6. First ranking (orchestrator, 2026-11-13 17:50; replace with `/challenge-pick` output)

| Rank | Challenge | Why | Deciding question |
|---|---|---|---|
| 1 | Stoa | Closest to our track record (document agents, OCR/vision), visual demo with 3D, measurable number, stacks with DeepMind; probably fewer teams than propaganda detection (assumed) | Sample folder tonight? |
| 2 | Cala | A backtested hit rate with cited reasons is hard to match; finance interest on the team | Point-in-time data? |
| 3 | Hostinger | Easy to demo | Crowded, politically sensitive |
| - | Valio Aimo, AstraZeneca | Not asked yet; AstraZeneca has no domain fit | - |

Stack on any of them: DeepMind (Gemini), Verda credits; MariaDB if the data fits.

## Open questions / UNVERIFIED

- All three partner asks are verbal; the official briefs come at 18:00.
- Stoa's track (site lists none; Data assumed) and the input format their pipeline takes.
- Cala's FinTech track and Hostinger's Agentic AI track are inferred from the partner list.
- The SemEval propaganda-technique dataset: check it exists and its licence before using it.

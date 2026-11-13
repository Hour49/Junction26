# Stoa: the partner

- Date: 2026-11-13 18:15 (Helsinki) · Author: Bogdan's Claude orchestrator
- Question: what does Stoa actually do, and what does that tell us about their Junction challenge?
- Answer in one line: Stoa is an EU-hosted AI assistant for construction site teams that reads a project's drawings,
  specs, contracts, schedule and site records, answers with the page behind every sentence, tracks what changed between
  revisions and drafts the paperwork (claims, RFIs, work plans). Their challenge is the messy legacy input in front of
  that product.

All facts below are Stoa's own claims from [stoabuild.com](https://stoabuild.com/) (home, /product, /case-examples,
/about/team, /about/security), accessed 2026-11-13 18:10, so they are **reported**, single-source. A web search for
the company and its co-founder found no independent coverage (accessed 2026-11-13). Junction lists Stoa as a major
(challenge) partner and links that site ([2026.hackjunction.com](https://2026.hackjunction.com/), accessed
2026-11-13).

## What the product does

- **Connects** read-only to the systems a site already runs (M-Files, SharePoint, OneDrive, Dalux, Congrid "and the
  rest"), keeping each system's folder permissions. "Live in two working days", "no migration project, no cleanup".
- **Ask your project:** plain-language questions answered from drawings, specifications, contracts, schedule, quality
  inspections, meeting minutes and email, every sentence cited to document and page. It "reads the drawings themselves,
  not only the text around them". Works across languages (Finnish drawings, Swedish contracts, English specs).
  Their demo: "What rating do the stair core doors need?" → "EI 60-Sa and self-closing", cited to spec §5.3, noting
  the Level 2 plan's version 6 did not change them.
- **Linked information:** wall types, finish codes, door tags and drawing callouts are clickable on the sheet; a click
  opens the detail, schedule row and spec clause that govern it.
- **Always the current revision:** it compares revisions and answers only from the latest; a drawing in both a draft
  folder and a construction-issue folder is taken from the construction-issue one.
- **Change tracking:** finds changes by comparing revisions "whether or not anyone announced them"; side-by-side,
  wipe and overlay views; AI-written change notes (their demo: "the partition wall on grid E between rows 4 and 6 has
  been removed, merging rooms 205 and 206"; "a new door O9 has been added in the corridor wall of room 103"); a
  daily email of yesterday's changes, filtered to your discipline; flags conflicts with other disciplines.
- **From information to output:** drafts work-phase plans, claims from the record, contract reviews (risks,
  responsibilities, costs, schedule, cited to clauses), tender requests; exports Word, Excel, PDF.
- **Skills:** save a way of working (draft a claim, prepare a meeting from open actions, write an ITP on your template)
  and rerun it on other documents.
- **Situational awareness and automations:** a one-page overview of what is stuck and what it blocks (a drawing an
  activity waits on, an approval that never came back), open RFIs, scheduled checks that post reports.

## Who uses it and the numbers they claim

- Five project kinds: energy and data centres, commercial, residential, infrastructure, renovation. "More than twenty
  Nordic sites, from data halls to rail"; "€4B+ of project value running on Stoa, including some of the largest
  data-centre sites in the Nordics".
- Claimed outcomes (design-partner interviews, 7/2026): 2–8 h a week back per project engineer (mostly time spent
  finding where something was written down); 40 % shorter from problem raised to decision; €3M+ in mistakes caught
  before site (conflicts between the programme and the documents it depends on); 5x faster onboarding.
- Data-centre example: RFIs answered from drawings and specs in minutes; timeline conflicts and missing prerequisites
  caught before they cost a day; claims spotted and drafted from the record.

## Company and data rules

- Co-founder and Chief Product Officer: Taavi Paananen (named on /about/team). The page quotes a customer-side
  Nordics Director. No funding information found.
- EU residency for storage, processing and embeddings; never used to train models; deletion within 30 days; GDPR
  Art. 28 DPA; designed for the EU AI Act's transparency rules; ISO/IEC 27001 in progress. Answers come only from the
  project's own documents, never the open web.

## What this means for the challenge (assumed)

- The chat with citations, revision tracking and change detection are **their product**: rebuilding them is not the
  job. The verbal brief (legacy, multimodal files → standard, up-to-date format → AI-ready, maybe 3D) is about input
  their product doesn't handle well yet: old archives that predate M-Files and Dalux. Scanned paper drawings,
  hand-annotated sheets, inconsistent naming, no revision history, mixed formats.
- **Renovation** is the natural use case: a 1970s building's archive has to become a current, structured record before
  anyone can plan work on it. A 3D view from old 2D plans fits there.
- Our output should plug into how they think: per-sheet metadata (number, title, discipline, revision, date, status),
  extracted codes (wall types, door tags, room numbers) linked across sheets, a "current revision" decision with its
  reason, and page-level provenance for every fact. Ask which format they want.
- EU-only processing is a hard rule for them: expect it in the challenge. Models on EU GPUs (Verda) or EU endpoints.

## Questions this raises for the rep

- Is the challenge about legacy archives (renovation, pre-digital projects) or about live projects' messy uploads?
- What input do they give us (scans, PDFs, DWG, IFC, photos, Finnish text)? A sample tonight?
- What output format would they ingest: their own schema, IFC, a sheet index, JSON per document?
- Does "up to date" mean picking the current revision in a pile, or reconciling an old archive with the as-built
  state (site photos, later renovations)?
- 3D: from 2D plans for renovation planning, or from existing BIM models?
- EU-only models required for the weekend?

## Open questions / UNVERIFIED

- All figures and customer claims are Stoa's own; no independent source found.
- Their Junction track (the site assigns none; Data assumed).

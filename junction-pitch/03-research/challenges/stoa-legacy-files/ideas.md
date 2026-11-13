# Stoa: what we could build without being architects or engineers

- Date: 2026-11-13 18:25 (Helsinki) · Author: Bogdan's Claude orchestrator, from Bogdan's question "we don't have that
  much experience as architects or engineers, could we work on this and build something unique that touches their pain
  points?"
- Answer in one line: yes, if we check **consistency and completeness** (things a careful non-expert can verify) and
  never claim **engineering correctness**; aimed at the archives Stoa's product can't onboard: pre-digital,
  renovation-era files.
- Based on: [partner.md](partner.md) (Stoa's product and claims) and the verbal brief in
  [../stand-notes-2026-11-13.md](../stand-notes-2026-11-13.md). Everything here is **assumed** until the official
  brief and the rep's answers.

## Why the domain gap matters less than it looks

- The hard part of the brief is a document and data problem: scans, mixed formats, inconsistent names, no revision
  history. That is our track record (document agents, OCR/vision, LLM pipelines), not structural design.
- Domain knowledge we do need is vocabulary, learnable in an hour: sheet numbers and disciplines (A-, S-, M-, E-),
  title blocks, revision tables, door and wall tags, room and door schedules, "construction issue" vs draft. ISO 19650
  file naming is the standard to cite for "standard format".
- Where expertise would bite: deciding whether a fire rating or a structure is *right*. Stoa's own rule is "when the
  documents do not hold the answer, say so": we follow it. We report what the documents say, where they disagree and
  what is missing, each cited to the page. No compliance verdicts.

## Their pain points (from their site) and how each idea hits one

| Stoa pain point (their words, reported) | Idea |
|---|---|
| "time spent finding where something was written down" | 1, 2 |
| "Always the current revision" (they need to know which sheet is current) | 1 |
| "€3M+ in mistakes caught before site, by flagging conflicts between the programme and the documents" | 2 |
| "Live in two working days ... no cleanup": breaks on archives that were never digital | 1 |
| Renovation is one of their five project kinds | 1, 3 |

## Ideas

1. **Archive triage: from a messy legacy folder to a clean sheet register** (core).
   Drop in scans, PDFs, photos and odd file names. Output per sheet: number, title, discipline, revision, date,
   status (current / superseded / duplicate / draft), with the confidence and the page region it was read from; plus
   a renamed, ISO 19650-style folder and a JSON export Stoa-like systems can ingest.
   Demo moment: a folder named `scan_0012.pdf ... IMG_4471.jpg` becomes a sorted, linked register in seconds, with
   "A-102 rev D supersedes rev C (title block date 1987-03-02)".
   Number (measured): sheet-register accuracy on a hand-checked sample (fields correct / total).
2. **Gap and conflict finder: what the documents disagree about** (core, the "wow").
   Mechanical cross-checks that need no engineering judgement: a door tag on the plan with no row in the door
   schedule; a room number in the plan missing from the room schedule; a callout pointing to a sheet that isn't in the
   archive; a revision table that disagrees with the title block; the same sheet in two revisions with a changed
   dimension. Each finding cites both pages and shows them side by side.
   Demo moment: "12 doors on level 2 have no schedule entry; sheet A-501 is referenced 7 times and missing".
   Number (measured): planted inconsistencies found / planted (recall) on a sample.
3. **Renovation 3D: old floor plans to a walkable model** (stretch, visual).
   Extract walls, doors and room labels from a scanned plan and extrude them into a simple 3D model in the browser
   (three.js), each room clickable back to its source sheet. Rough massing only, labelled as such.
   Demo moment: a 1970s scan turns into a 3D floor you can orbit.

Recommendation: build 1 + 2 as the product, 3 only once 1 and 2 work end to end. The pitch line: "Stoa goes live on a
new project in two days. We make that true for buildings whose documents were never digital."

## Making up for the domain gap

- Ask the Stoa rep tonight: a sample folder, 3-5 questions their users ask, what "correct" looks like, and 15 minutes
  with one of their engineers on Saturday to check our extraction on 10 sheets.
- Madalina interviews 2-3 construction people at the venue (Stoa's team, other partners) about renovation archives.
- City of Espoo is a challenge partner: ask whether old building-permit drawings are a pain for them (UNVERIFIED that
  they have such an archive or would share it).
- Data fallback if Stoa gives none: CubiCasa5K, a public dataset of annotated Finnish floor-plan images (from
  memory: check it exists, its size and its licence before relying on it). Good for idea 3 and for testing wall and room
  extraction; it has no revisions or schedules, so ideas 1-2 still need Stoa-like documents.
- Keep every output cited and every claim a consistency claim; label 3D as approximate.

## Team fit

AI/backend (Bogdan, Tudor): extraction pipeline (vision LLM + OCR), the cross-check engine, the export. Frontend and
design (Beatrice, Tudor): the register UI, side-by-side evidence view, the 3D viewer. Problem and pitch (Madalina):
interviews, the renovation story, the numbers. Stack: DeepMind (Gemini for drawings; "best use of Gemini"), Verda EU
GPUs if EU-only processing is required, MariaDB for the register if it fits.

## Risks

- Extraction quality on bad scans in 48 h: start on title blocks (structured, high value) before plan contents.
- Judges with construction backgrounds: no engineering verdicts; show the evidence and let them judge.
- Overlap with Stoa's own roadmap: ask the rep what they would love to plug in, and position it as their onboarding
  step, not a competitor.

## Open questions / UNVERIFIED

- The official brief (18:00), the data they give, the output format they want, EU-only rules.
- CubiCasa5K details and licence.

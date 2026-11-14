# Requirements: drawing questions answered with proof (Stoa challenge)

Status: draft 1, 2026-11-13 20:30, from the brainstorm between Bogdan and the `requirements` agent. Not yet agreed
with the team. Clickable mock: `demo/index.html`. "Countersign" is a working name.

## 1. What we are building

A tool that takes a project's drawings in whatever form they come (CAD, BIM model, PDF, scan), reads each one
once into a structured drawing model, and then answers quantity questions from that model. Every answer comes
with the marks on the drawing that prove it, the counting rule that was applied, and what it cost.

Decided by Bogdan, 2026-11-13 20:15: "go with A+B+C", plus an ingestion phase shown in detail and two user roles.

- **A. Proof first.** A count is a set of numbered marks on the drawing. An area is a set of shaded rooms with the
  sum written out. The rule ("an open doorway is not a door") is shown with the number.
- **B. Ingest once, answer cheaply.** All drawing work happens at ingest. A question is turned into a query over
  the drawing model; most answers are lookups with no model call on the drawing.
- **C. Two methods, and a person where they disagree.** Each quantity is counted a second, independent way at
  ingest. Disagreements are shown as contested marks and settled by a surveyor, not hidden.

## 2. Why this shape (what the brief and the data say)

- Stoa judges four things equally: accuracy, a visual trace a human can verify, creativity, low inference cost.
  Their CTO judges and wants a technical walkthrough (feedback log F-004).
- The dataset: 127,044 questions on 5,939 files. 67% are on CubiCasa raster plans, 30% on Swiss Dwellings
  (DXF, PDF and PNG of the same drawing), the rest on IFC models and one practice's drawing sets. About 88% are
  counts, scored exact; areas, lengths and volumes are scored within 2%.
- Review findings so far (dataset review, board #15, 2026-11-13): Swiss counts can be re-derived
  from the DXF with 100% agreement, but counting door arcs instead of openings is wrong on 43% of plans, so the
  counting rule matters as much as the detection. CubiCasa answers follow the annotator's labels (an unlabelled
  bedroom counts as 0; "windows" may mean panes). Many scans are rotated or very small. Legacy archives have no
  questions, and many of their sheets are not floor plans.
- Published results put vision-language models at roughly 40-55% exact on door and window counts (board #14), so
  a model looking at the picture cannot be the only method.

## 3. Users

| Role | Wants | Main screen |
| --- | --- | --- |
| Engineer | An answer to one question now, and enough proof to trust it | Ask box, answer card, marks on the drawing |
| Surveyor | A full takeoff of a drawing that they can sign | Takeoff table, review queue, mark editing, sign-off, export |

The two roles share state: what the surveyor signs, the engineer sees as verified.

## 4. Functional requirements

Priority: **M** must have for the demo, **S** should, **C** could.

### Ingest

| Id | Requirement | Pri |
| --- | --- | --- |
| I1 | Accept a zip or single files: DXF, DWG, IFC, SVG, PDF, PNG, JPEG. Unpack safely (path check, size caps). | M |
| I2 | Hash every file; a file seen before is not ingested again. | M |
| I3 | Detect the type from content. Group same-name files as one drawing. Set aside non-drawings with a reason. | M |
| I4 | Route each drawing to the richest source: model, then CAD, then vector PDF or SVG, then raster. Record the route. | M |
| I5 | Fix orientation (0/90/180/270) and skew on rasters. | M |
| I6 | Find the scale and its uncertainty (CAD units, written scale, scale bar, dimensions). Without a scale, refuse lengths and areas but still count. | M |
| I7 | Split multi-view sheets into views and type them (plan, section, elevation). | S |
| I8 | Extract rooms, openings, fixtures, labels and units per route, each with its region on the sheet and a confidence. | M |
| I9 | Write one drawing model schema for all routes. Counting rules are data in it. | M |
| I10 | Count each quantity a second, independent way; flag the marks that differ. | M |
| I11 | Precompute the known question types with their marks. | M |
| I12 | Show ingest progress per file and per stage, with a readable trace of what each stage found. | M |
| I13 | Open encrypted PDFs that have an empty password; convert DWG to DXF. | S |

### Answering (engineer)

| Id | Requirement | Pri |
| --- | --- | --- |
| Q1 | Turn a question in any of the dataset's languages into a query over the drawing model. | M |
| Q2 | Answer with value and unit, in the format the scorer expects. | M |
| Q3 | Show the evidence on the drawing: numbered marks for counts, shaded regions and the written sum for areas. | M |
| Q4 | Show the counting rule applied, including what it left out and why. | M |
| Q5 | Show how it was answered: query, method, second method's result, cost, time. | M |
| Q6 | When methods disagree, show both numbers and the contested marks. | M |
| Q7 | Refuse with a reason when the drawing model cannot answer (no plan view, no scale, resolution too low, not a quantity). | M |
| Q8 | Lengths and volumes (IFC models, dimensioned drawings). | S |
| Q9 | Text lookups on the sheet (title block, labels, schedules). | C |

### Review (surveyor)

| Id | Requirement | Pri |
| --- | --- | --- |
| R1 | Takeoff table per drawing: quantity, value, state. | M |
| R2 | Review queue: quantities where methods disagree or a check failed. | M |
| R3 | Accept or reject a mark, add a missed one, include or leave out a room; the value updates at once. | M |
| R4 | Sign off a quantity (who, when). Signed values are marked verified everywhere. | S |
| R5 | Export the takeoff as CSV. | S |
| R6 | Corrections are kept as labelled examples for evaluating and improving the extractors. | C |
| R7 | Every finding in a project is one located issue (conflict, refused answer, reading flag, set-aside file, failed code check): kind, severity, drawing, floor where the source states it, page and box, one sentence of why, state. One list per project as JSON, CSV and a zip with the pages marked (story #140, decision 0008; MUST DO, Bogdan 2026-11-14). | M |

## 5. Non-functional requirements

- **Accuracy is measured, not claimed.** Per source and per question type, on a held-out sample of Stoa's
  questions with Stoa's rule (board #15, `eval/`). The pitch shows the table, including where we fail.
- **Cost is logged per question and per ingested file**, in money and in model calls. Target: no model call on
  the drawing at question time for the precomputed types.
- **No silent guesses.** A low-confidence or contested answer says so.
- **Partner data** stays out of the repo and out of any third-party service until Stoa's rules are known. Stoa
  processes in the EU; models should run on EU infrastructure (Verda) or EU endpoints.
- **Licences**: a drawing shown on screen carries its credit from the dataset's `LICENSE.md`.
- Backend: Python 3.13 and FastAPI (decision 0001). Frontend: not picked.

## 6. Out of scope for the hackathon

Revision comparison and change tracking, document Q&A over specifications and contracts, connectors to document
systems (all of these are Stoa's existing product); 3D reconstruction; user accounts.

## 7. Open questions

1. How does Stoa score: a hidden question set (which templates and formats, is the DXF given?) or the Sunday demo
   only? Decides how much effort goes into CubiCasa rasters. Owner: Bogdan, ask at the stand.
2. Which counting conventions does the hidden set use where the dataset is ambiguous (window panes, unlabelled
   rooms)? We follow the dataset's labels until told otherwise.
3. What accuracy can the raster route reach on CubiCasa counts? Waiting on Tudor's parsing numbers (board #14).
   If it is low, the raster route ships as "assisted, surveyor-verified" and the pitch says so.
4. Is the second count (I10) a small vision model, a second detector, or both? Depends on cost per page on Verda.
5. Does the surveyor role matter to Stoa's users, or is it our evaluation tool? Ask at the Saturday check-in.

## 8. What the mock shows and what it does not

The mock in `demo/` shows the three screens with two synthetic drawings (one vector, one scan) whose numbers are
computed from their own geometry. It does not parse files, run any model or measure any cost; those numbers are
placeholders until the pipeline exists.

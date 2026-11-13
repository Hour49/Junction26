# Spec v0: legacy archive to a current register and located findings (Stoa)

- Status: **draft**, proposed by the orchestrator on 2026-11-13 ~20:20, from a brainstorm with Bogdan. Not decided:
  see §9. Changes go through a PR; the output format becomes decision record 0002 once agreed.
- Challenge: Stoa (assumed: our first pick, official brief and sample files not seen yet). Background:
  [partner.md](../junction-pitch/03-research/challenges/stoa-legacy-files/partner.md),
  [ideas.md](../junction-pitch/03-research/challenges/stoa-legacy-files/ideas.md), feedback F-003 and F-004 in the
  [feedback log](../junction-pitch/03-research/feedback/log.md).
- Rules for how we build it: [ENGINEERING.md](ENGINEERING.md), [QA.md](QA.md).

## 1. What we build

A folder of old, messy building documents goes in. Out come (a) a **register**: one entry per page saying what it
is, which floor, sheet number, revision, date and whether it is the current version; and (b) **findings**: places
where the documents disagree or something is missing, each with the floor, the sheet and the spot on the page.

We check **consistency and completeness**, never engineering correctness: we say what the documents say, where they
disagree and what is missing, and every claim cites a page. The output is shaped to drop into a floor-by-floor issue
view like the one Stoa showed (F-004).

First step: the **golden case** (§6) and its expected output, so every later change is measured.

## 2. Input (assumed until the brief)

A folder, any nesting, junk file names. Supported in v0: PDF (scanned or vector, many pages), JPEG/PNG (scans and
photos of sheets), XLSX (schedules). DOCX if time allows. DWG is out (closed format; ask Stoa, §9). Text may be
Finnish, Swedish or English.

## 3. Pipeline

| Stage | Layer | In | Out |
| --- | --- | --- | --- |
| ingest | api + adapters | folder | pages: image + text layer if any + provenance (file, page, sha256) |
| classify | adapter (vision model) | page | kind: drawing, schedule, specification, photo, other; discipline |
| extract | adapter (vision model, OCR) | page | title block, revision table, tags (doors, rooms, wall types), references to other sheets, each with a box and a confidence |
| resolve | core (pure) | all extractions | canonical sheet ids, floors, current / superseded / duplicate / draft with the reason, links between sheets |
| check | core (pure) | resolved archive | findings (§5), deterministic rules |
| export | core + api | register, findings | `register.v1.json`, `findings.v1.json`, renamed copies |
| UI | frontend (not picked) | the two JSON files | floor view, findings list, plan with the spot highlighted, evidence side by side |

Every outside service sits behind one adapter with a fake (ENGINEERING.md §2): the vision model (Gemini, or Kimi
K3.1 Pro / DeepSeek V4.1 Flash on Verda when data must stay in the EU), OCR, and a trained detector later only if it
beats the prompted model on the golden case. Resolve and check are plain Python in `backend/app/core`: this is the
part the Stoa CTO will question, so it stays deterministic and explainable.

## 4. Output format v1

Pydantic models in `backend/app/core/contracts.py`; JSON Schemas generated into `contracts/register.v1.schema.json`
and `contracts/findings.v1.schema.json`, with a test that fails when the committed schema and the models drift.

Conventions: a box is `[x0, y0, x1, y1]` as fractions of the page image as rendered (origin top left), so the UI
draws over the original. `floor` is a string: `"B1"` for the first basement, `"1"` for the ground floor (Finnish
numbering), `"2"` and up, `null` when unknown. Dates are ISO `YYYY-MM-DD`. Confidence is 0-1.

Register entry (one per page):

```json
{
  "id": "doc-0007",
  "source": {"file": "scan_0012.pdf", "page": 1, "sha256": "…"},
  "kind": "drawing",
  "discipline": "A",
  "floor": "2",
  "sheet": {"number": "A-102", "title": "2nd floor plan", "revision": "D", "date": "1987-03-02", "scale": "1:100"},
  "status": "current",
  "status_reason": "rev D supersedes rev C (title block 1987-03-02 vs 1986-11-20)",
  "standard_name": "K-ARC-L02-DR-A-0102_D.pdf",
  "evidence": {"sheet.number": {"page": 1, "box": [0.81, 0.90, 0.97, 0.94], "confidence": 0.93}}
}
```

`status`: `current`, `superseded`, `duplicate`, `draft`, `unknown`. `standard_name` follows ISO 19650 naming,
simplified to `<project>-<originator>-<level>-<type>-<role>-<number>_<rev>`.

Finding:

```json
{
  "id": "F-012",
  "rule": "door_missing_from_schedule",
  "severity": "high",
  "floor": "2",
  "subject": "D-214",
  "message": "Door D-214 is on A-102 rev D but not in the door schedule A-601.",
  "evidence": [{"doc": "doc-0007", "box": [0.42, 0.31, 0.45, 0.34]}, {"doc": "doc-0011", "box": null}]
}
```

`severity`: `high` (someone could work from wrong or missing information), `medium` (schedules and plans disagree),
`low` (naming, unreadable fields).

## 5. Rules v1 (core, deterministic)

| Rule | Fires when |
| --- | --- |
| `revision_mismatch` | the newest row of a sheet's revision table differs from its title block revision |
| `missing_referenced_sheet` | a callout or a document refers to a sheet number that is not in the archive |
| `door_missing_from_schedule` | a door tag on a current plan has no row in the door schedule |
| `room_missing_from_schedule` | a room number on a current plan has no row in the room schedule |
| `room_name_mismatch` | a room's name on the plan and in the room schedule differ |
| `floor_without_plan` | a floor appears in sections or other sheets but has no current plan |
| `draft_only` | a sheet exists only as a draft, with no issued version |
| `unreadable_page` | a page's sheet number or revision could not be read above the confidence threshold |

Superseded and duplicate pages are a `status` in the register, not findings.

## 6. Golden case

**Case 1, `building-k` (synthetic, committed).** A generator draws the documents for one small building (basement
and three floors), renders them to PDF and PNG, then ages them (noise, skew, blur, JPEG, one sheet photographed at
an angle). Because it draws them, it also writes the right answers: `expected/register.json` and
`expected/findings.json`, including the exact box of every tag it drew. Seeded, so reruns are identical. Some titles
in Finnish. About 15 files with junk names:

- plans for floors 1-3 (A-101 rev B, A-102 rev C and rev D, A-103 rev A as an angled photo), no basement plan;
- section A-301 showing B1 to 3; door schedule A-601 (scanned table); room schedule A-602 (XLSX);
- a second copy of A-102 rev D under another name; elevation A-201 only as a draft;
- a specification excerpt that refers to A-501; a heavily blurred page; one site photo.

Planted problems, one per rule: A-101's revision table says C, its title block B; A-501 referenced but missing;
door D-214 on A-102 rev D but not in A-601; one room missing from A-602; room 205 "Office" on the plan, "Storage" in
A-602; basement without a plan; A-201 draft only; the blurred page unreadable. Plus the expected statuses:
A-102 rev C superseded, the copy a duplicate.

Layout: `eval/generate.py`, `eval/golden/building-k/input/`, `eval/golden/building-k/expected/`. `eval/` is its own
uv project with its own `check.sh` (CI picks it up). Drawing with reportlab (BSD), ageing with Pillow and OpenCV.
The whole case stays under 5 MB per file (pre-commit hook).

**Case 2, real sheets (private, gitignored).** If Stoa gives us files, we hand-label 10-20 pages in the same format
under `data/private/`. Never committed (public repo).

## 7. Scoring

`eval/score.py --expected <dir> --actual <dir>` reads only the two JSON files per side, so it doesn't depend on the
backend's code. It reports, per case:

- register: share of correct fields, per field and overall, after normalising (trimmed, upper-case sheet numbers,
  ISO dates); `kind` accuracy; `status` accuracy;
- findings: precision and recall, where a match is the same `rule`, the same `subject` (if any) and the same main
  document;
- location: share of expected boxes that the output hits with an overlap (IoU) of at least 0.5.

Output: a table on stdout and `score.json`. The numbers in the README and the pitch come from this script on
committed data (ENGINEERING.md §5).

## 8. Tools (licences checked against ENGINEERING.md §4)

| Need | Use | Not |
| --- | --- | --- |
| Render PDF pages | pypdfium2 (Apache/BSD) | PyMuPDF (AGPL) |
| Images | Pillow, OpenCV (Apache) | |
| OCR | Tesseract with Finnish, or the vision model alone: the golden case decides | |
| Detector, only if needed | torchvision or Hugging Face RT-DETR (Apache/BSD) | Ultralytics YOLO (AGPL) |
| Vision model | Gemini (DeepMind partner); Kimi K3.1 Pro / DeepSeek V4.1 Flash on Verda for EU-only | |
| Generator | reportlab (BSD) | |
| 3D, stretch | three.js (MIT); IFC via IfcOpenShell (LGPL) | |
| Training data, demo only | CubiCasa5K, FloorPlanCAD: both CC BY-NC 4.0, never committed, declared in the submission | |

## 9. Open decisions and questions

For Bogdan:
1. Commit to Stoa tonight? (Recommended: yes; the golden case is useful for any document challenge.)
2. Generate the golden case, or draw it by hand? (Recommended: generate it, plus 3-4 real scans as a reality check.)
3. Is the output format in §4 right, or wait for Stoa's? (Recommended: adopt it now as v1 and change it if they
   answer differently.)

For Stoa: the official brief and sample files; the format they would ingest; what sits behind a located issue in
their app (floor, plan coordinates, schedule ids); DWG or not; how much is Finnish or handwritten.

## 10. Plan once decided

Three workers, split by files:
- **contract**: the models in `backend/app/core/contracts.py`, the generated schemas, decision record 0002,
  `eval/score.py` with tests.
- **golden**: `eval/generate.py` and `eval/golden/building-k/`.
- **baseline**: the vision-model adapter and its fake, plus a backend command that runs ingest, classify and
  extract on a folder and writes `register.v1.json`. First run on the golden case. Cost first: about 16 pages, one
  call each, a few cents.

Milestones: first scores on the golden case around midnight Fri; first end-to-end run (resolve, check, findings, UI
on fakes) Sat ~14:00, as in QA.md §7.

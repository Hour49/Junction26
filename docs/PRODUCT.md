# The product, step by step

Moved here from the README on 2026-11-14, text unchanged apart from the links. The README has the short
version with pictures; this page keeps the values the product is checked against, the steps in the order a user
meets them, the status on main, every measured number with its caveats, and the full list of limits. One number
has moved since: the golden run below is commit bd2471f (92.2%); the latest in the series is 240e620, 2749 of 2948
(93.2%), in [GOLDEN.md](GOLDEN.md).

## Key values

The product has to respect these six values, in this order (team notes, 2026-11-13). Every feature, answer and
demo screen gets checked against them.

1. Transparency. Each answer highlights the file it came from and the place in that file where it was found
   (page and box), so a person can check it.
2. Confidence. Each answer says how sure the system is.
3. Conflicts. When sources disagree, the system shows the conflict and does not quietly pick one side.
4. Rules. Answers are checked against the building code of the country the project is in.
5. Abstention. When the evidence is too weak, the system says it does not know instead of guessing.
6. UX. The screens make all of the above easy to see and act on.

The flow these values imply: ingest → AI decision (a decision model) → the conflicts it found (for example
"5 conflicts") → how each one was resolved.

## The product

Drawing Q&A for construction projects. A surveyor drops a project, asks questions about it, and gets answers
that show where on the drawing they came from. In the order a user meets it:

1. Upload. A zip, or single PDFs, images, IFC models and DXF files ([docs/API.md](API.md), upload limits
   under "Conventions").
2. File triage. Each image is first sorted as a floor plan or not. A file that is not a plan is set aside, kept,
   and described in words. A person can still ask for it to be read as a plan
   ([decision 0010](decisions/0010-file-triage.md)).
3. Reading, one route per kind of file: a drawn PDF is read from its vectors, an image (scan, photo, sketch) by
   detectors and a room reader, an IFC model through its own objects. Every drawing lists what was looked
   for, so a class that was not read says so instead of showing a zero ([docs/PIPELINE.md](PIPELINE.md)).
4. Ask with proof. A question in plain words (11 languages) gets a value with its unit, marks on the plan page,
   the method that produced it, and the credit for any licensed data. Its confidence is a level, High, Medium or
   Low (#233), never a model score as a percentage. Where the evidence is too weak the answer says it does not know.
5. Double-check requests. An answer the system cannot certify asks a person to look: it shows the disputed
   marks, and the person signs it off or fixes it, instead of a silent guess
   ([spec](specs/frontend/double-check.md)).
6. Conflicts and located issues. Where two readings of one quantity disagree, both values are shown. Conflicts,
   refused answers, reading flags and set-aside files make one list of located issues (file, page, box, one
   sentence of why), exported as JSON, CSV or a zip with the pages marked
   ([decision 0008](decisions/0008-located-issues.md)).
7. Building-code pre-check, for Finland and the canton of Zürich. "A pre-check of a few rules, not a compliance
   certificate." The failed checks join the issues list.

Status on main, 2026-11-14: steps 1 to 7 are merged: the double-check request (#129), plan counts that are sure
only when two readers agree (#174), the building-code pre-check with its rule packs for Finland and Zürich (#139,
decision 0009), the located issues list (#140), and file triage with its register, description form, relevance
verdict and overrule (#183). The Gemini describer (#193, `TRIAGE_DESCRIBER=gemini`) and the local SigLIP2 classifier (#202) are off by
default, so triage stays off in the demo configuration unless its settings are switched on.

Merged since:
- Each drawing in the project response has a plain name and its licence credit (#224).
- Issues have answers, answer chips and open counts on the project (#223).
- A spend guard caps Gemini cost with `GEMINI_BUDGET_USD` and an hourly limit, and a public ledger API shows the
  spend (#225).
- Each conflict card has a plain title, a reason and suggested answers, and a settle keeps a typed answer as its
  note (#226).
- The demo archive holds no CubiCasa scan any more: their licence (CC BY-NC-SA) does not allow a public demo. It
  has five plans we may serve with credit instead (#231).

What we tried on the raster track, and what it gave: [docs/EXPERIMENTS.md](EXPERIMENTS.md).
Golden-set method and results: [docs/GOLDEN.md](GOLDEN.md). Known issues: [docs/KNOWN.md](KNOWN.md).
All decision records: [docs/decisions/](decisions/README.md).

### Numbers

- Golden v2, whole pipeline, run from a clean export of commit bd2471f: 2717 of 2948 answers right (92.2%), 92.9%
  on the holdout questions, 4.5% abstained. The dev column is in-sample because of the dev prior, so the holdout
  is the honest one. The series is in [docs/GOLDEN.md](GOLDEN.md).
- Shipping raster config C1-T1, CubiCasa test split, read once through the API: 87.0% exact (5,846 of 6,718
  questions, 376 test pages; kitchen counts 92.2%, read from the drawing). The same read scored through the CLI
  gave 87.2% (5,860), because the CLI answers kitchen from the prior and the API never does for an uploaded file.
  The validation split gave 88.5%. Config C's earlier test read was 85.0% (5708 of 6718, 95% CI [83.4, 86.5],
  against 56.3% for the train prior, [docs/EXPERIMENTS.md](EXPERIMENTS.md)).
- Double-check policy, test certificate (the policy fit on validation, then run once on the test pages): it flags
  97.0% of the wrong answers (846 of 872 questions; one-sided 95% bound 95.3%), asks on 62.1% of all answers, and
  98.98% of the answers it leaves alone are exact (2518 of 2544). On validation it asked on 55.1% and flagged
  96.0%. The certificate covers the raster route; vector and BIM are certified on golden v2's holdout
  ([docs/GOLDEN.md](GOLDEN.md)).
- Confidence levels on the same test read (3,359 answers, one per page and family): High is 37.9% of answers and
  99.0% exact (95% interval [98.3, 99.4]), Medium 41.1% and 92.8% [91.3, 94.0], Low 21.0% and 54.2% [50.6, 57.9].
  The rule and its thresholds were written down before the test numbers were computed.
- With `CARBON_LEVELS=ladder`, a Medium answer that Gemini Carbon, read as a second reader, counts the same becomes
  High, and one it counts differently becomes Low. On 256 validation pages kept out of every earlier Carbon test
  (2,271 answers, one per page and family), High goes from 44.9% of answers at 99.0% exact [98.2, 99.5] to 69.7%
  at 97.7% [96.8, 98.3]; the promoted answers alone are 95.2% exact [93.1, 96.7]. Medium keeps 5.9% at 96.3%,
  Low 24.4% at 61.4%. Not measured on the test pages.

### Limits

- Sketches: we claim no door counting. On 14 hand-drawn sheets the door count was in range on 0 of 10, and every
  door, window and room count asked for a check (K8 in [docs/KNOWN.md](KNOWN.md)).
- The double-check policy asks about 62% of answers on the test pages to catch 97% of the wrong ones, so a
  person reviews many right answers too (K9).
- On an image, areas come from an estimated scale (`RASTER_SCALE=priors`) and are labelled estimates. One can be
  far off while printing a narrow band (K5: +74%, +100% and -37% on three golden rooms).
- On plans without printed room labels the reader types rooms by furniture, while the gold labels only count
  what is printed, so "bedrooms" can be 0 on a plan that shows beds (EXPERIMENTS.md).
- Windows stayed at about 45-55% in every track we tried (EXPERIMENTS.md).
- Schedules are read on gold drawings only; the vector extractor reads no tables yet (backend/README.md).
- No login: the sign-off name is typed by the surveyor (decision 0001), and the API is for localhost or a private
  network only.
- The building-code pre-check covers a few rules, in Finland and the canton of Zürich only. It is not a compliance check.

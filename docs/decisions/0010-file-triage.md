# 0010: Every uploaded image is triaged before any reader: floor plan, other drawing or not a drawing; a non-plan is kept, described and judged against the project

- Status: accepted, with the orchestrator's 4 amendments (2026-11-14 13:11) and the 12 answers to Tudor's fleet's
  review (board #152, c6876449112); both are written into the sections below and listed at the end. Section 8
  (register, description form, relevance by rule; COMMON decisions 8-11) proposed 2026-11-14 14:20, accepted by
  the orchestrator with two additions and by Tudor's fleet's review (#152 c6877112058), built in PR #183
- Date: written 2026-11-14 13:09, accepted 13:11 (Europe/Helsinki)
- Decided by: agent tables-fix (worker), for Bogdan's new feature of 2026-11-14 ("FIRST AFTER UPLOAD, EACH OF THE
  PHOTOS GOES THROUGH A CLASSIFIER, is this a floor plan or not ? Then if it is not, we need to make it go through a
  vision model to text. Then after the context with everything, and the correct floor plan uploaded, we should look
  if text description of the image is relevant or not") and the orchestrator's decisions 1-7 in
  `.agents/briefs/triage/COMMON.md`; accepted by Bogdan's orchestrator and posted to Tudor's fleet
- Board thread: #152

## Context

- The Stoa archive sources are not only floor plans. Of the 374 preview archive files, 160 (43%) show a floor plan.
  The rest are elevations, sections, site plans, details and covers, plus 21 random pictures (a music score, an
  anatomy print, an icon). Answer key: `.agents/research/archive-kinds/preview-374.json`.
- Ingest today asks only "is this a drawing format" (`core/pipeline/identify.py`, by bytes) and "what content kind"
  (`ContentProbe`, stage 3). An elevation scan is a `png_plan` and goes to the floor-plan readers.
- What the hosted sheet-kind signal does today (`adapters/decisions_kind`, `KindProbe`, on with
  `DECISIONS_KIND=true`, which demo config C sets):
  - It wraps the probe, and asks Gemini Decisions a 6-way choice only for `png_plan` and `jpeg_plan`.
  - Above P(photo of a plan) 0.9 it turns the kind into `photo_plan`, for the rectifier.
  - Above P(not a drawing) 0.5 it turns it into `unknown`, which ingest sets aside.
  - It never stops an elevation, section or site plan from being read as a floor plan. It doesn't look at
    `pdf_scan` or `photo`. It writes no description.
- `judge.py` then flags a sheet whose reader read nothing. It never says "this is not a floor plan".

## Decision

### 1. Where it runs: a triage step inside stage 3, after the probe, before grouping and routing

`IngestService._probed` runs on the probing threads. It calls the `ContentProbe` (with `KindProbe` when the kind
signal is on), then, with triage on, the `Classifier` on the same bytes, for every **image-like** file:

- probe kinds `png_plan`, `jpeg_plan`, `photo_plan`, `pdf_scan`, `photo`;
- and `unknown` when the bytes are a PNG or JPEG (what `KindProbe` calls not a drawing).

Vector PDFs, IFC, DXF and SVG are not triaged in this version. Their readers have their own evidence (text and
paths), and Bogdan's request is about photos. A vector elevation sheet still goes to the vector reader as today,
and its empty reading is flagged by `judge.py`.

How triage relates to the kind signal: **one input, not replaced.**

- `KindProbe` keeps its photo flag (`photo_plan` for the rectifier).
- The `Classifier` alone decides plan or not. Its adapter may read the kind signal's cached probabilities as one
  feature (eu-big measures the local model against it and may combine them).
- With triage on, `KindProbe`'s not-a-drawing rule no longer sets an image aside by itself. The classifier's
  `not_drawing` does, so one component makes that call.
  An image the classifier calls a floor plan is read as one: a probe `unknown` PNG or JPEG becomes `png_plan` or
  `jpeg_plan`, a `photo` becomes `photo_plan` (for the rectifier). A non-plan is not framed (no EXIF turn or
  rectifier), since nothing reads it.
- A classifier that can't answer (`Unavailable`) leaves the file as today, with "triage not available: <why>; read
  as today" in the `identify` line.
- With triage off, ingest behaves exactly as today.

### 2. The class per file

```text
Triage = {
  class: "floor_plan" | "other_drawing" | "not_drawing",
  p_plan: float,          # P(a floor plan anywhere on the page), 0..1
  method: str,            # in plain words, e.g. "local classifier v1 (EfficientNet-B0, CPU) + the kind signal"
  description: Description | null,
  relevance: Relevance | null,
  overruled: Overrule | null,
  verdict: "related" | "unrelated" | "unsure" | null,  # overruled.verdict ?? relevance.verdict (#152 item 4)
  note: str | null,       # why description or relevance is null, a plain sentence (#152 item 7)
}
```

- `class` is a closed list (map it to words). `method`, `description.subject`, `relevance.judge`, `matched_on`
  items and the part of the file's `reason` after "not a floor plan: " are plain words shown as they are, never ids
  (#152 item 6).
- `verdict` is the one value the file row, the trace and the issue use. It is null while the file is not judged.
- `note` is set whenever `description` or `relevance` is null (#152 item 7):
  - a floor plan: "a floor plan: it is read, so it is not described or judged";
  - no describer set up (the offline demo): "not described: no description model is set up, so it is not judged";
  - the describer refused or failed: "not described: <why>";
  - described, project still running: "not judged yet: the project is still being read";
  - no judge set up: "not judged: no relevance judge is set up"; the judge could not answer: "not judged: <why>";
    the project's ingest failed: "not judged: the project's ingest failed".
  - With no plan read in the project, `relevance` is not null: it is `unsure` with "no floor plan in the project
    to compare with".

- `floor_plan`: a floor plan anywhere on the page. A sheet with a section above and a plan below is a plan.
- `other_drawing`: an elevation, section, site plan, detail, schedule sheet, perspective or cover.
- `not_drawing`: a photograph, music score, anatomy print, text page or icon.
- **Unsure means `floor_plan`.** The threshold on `p_plan` is chosen by eu-big on held-out data to keep plan recall
  >= 99% (COMMON decision 2). A plan called "not a plan" would never be read, so that is the costly error.
- A `floor_plan` goes on exactly as today: same kinds, routes and readers.
- **A non-plan gets the existing state `set_aside`, with the reason**
  `not a floor plan: <class words>` (P(plan) and the method are in `triage` and the identify line; plain words
  on the file since R6, orchestrator 2026-11-14). It is not given a new state.
  - `set_aside` already means "kept in the project, shown with its reason and its preview, not read". The frontend
    switches on `FileState` with exhaustive maps (`STATE_LABEL: Record<FileState, …>` in
    `frontend/src/ingest/ingest.ts:69`, and `ProjectScreen.tsx`, `history.ts`, `advanced.ts`). A new state would
    widen that enum and break their type check.
  - The new information lives in the additive `FileStatus.triage` object. The screens tell a triaged file from a
    file set aside for its format by `triage != null`.
  - The trace gets no new stage (`STAGE_LABEL` is keyed by `Stage` the same way). The identify stage's line gains
    `; triage: other_drawing (P(plan) 0.03, …)`, and its `cost_usd` includes the classifier's.
- Nothing is deleted. The file's bytes stay in the project, and `preview.png` works as for any set-aside image.

### 3. Description (step 2): only for non-plans, in ingest, cached by content

```text
Description = {
  text: str,               # 1-3 plain sentences: what the picture shows
  subject: str,            # a short label: "south elevation of a two-storey house"
  text_seen: list[str],    # title-block and caption text printed on it, as read, max 20
  language: str | null,    # of text_seen, ISO 639-1; null: none read
  model: str,              # which describer, e.g. "gemini-3.5-flash" or "Qwen3.8-27B (Verda, EU)"
  cost_usd: float,
}
```

- When it runs: on the file's ingest thread, right after triage, only when the class is not `floor_plan`. The
  file is finished (`set_aside`) when its description is written or has failed.
- The describer adapter caches on disk by `(sha256 of the bytes, describer name, prompt version)`, like the Gemini
  caches, so a file is paid for once.
- Privacy (#152 item 11): the repo and the demo are public. The describer is told not to transcribe personal data
  (names of private people, phone numbers, number plates, home addresses); `text_seen` is title-block and caption
  text only. The screen shows `text_seen` collapsed by default.
- On an error, `description` is null and the reason is in the trace. Nothing is guessed, and the file stays set
  aside.
- Async in the sense that it runs in parallel with the plan files on the probing pool (`PROBES_IN_FLIGHT`). It does
  not block a plan's reading.
- Cost: only non-plans are described. Description and judge costs count in `FileStatus.cost_usd` and
  `ProjectView.cost_usd` (#152 item 11); the offline demo stays at 0.00 USD (no model set up).
  - Assumed price: about 2.2 USD per 1,000 described files at the average Gemini call price we measured (6.7 USD
    per 1,000 pages for three calls, `docs/EXPERIMENTS.md`). eu-big measures the real per-call price of Gemini and
    of the EU options before anything is chosen.
  - For the archive (214 of the 374 preview files, 57%, are non-plans) that is about 1.3 USD per 1,000 uploaded
    archive images, or roughly 8.4 USD for all 6,701.
  - Cap and pilot rules as in COMMON.

### 4. Relevance (step 3): once the project's plans are read

```text
Relevance = {
  verdict: "related" | "unrelated" | "unsure",
  why: str,                 # one sentence naming what matched or what is missing
  matched_on: list[str],    # e.g. ["building name 'Villa Rosa' in the title block", "same street name"]
  plans: list[str],         # drawing ids of this project's plans it relates to (may be empty)
  judge: str,               # which judge (model or rules), as `method` above
}
Overrule = { verdict: "related" | "unrelated", by: str, at: str }   # a person's call
```

- When it runs: as the last step of the project's ingest, after every file is finished and before the project is
  `done`, for each described file.
- The judge is given the description and a `ProjectContext` built in core from the project's own data:
  - the text read on the project's drawings: room and flat labels, storeys, table titles, model object names
    and storeys (the drawing model keeps no title-block text yet);
  - every file and folder name;
  - the other descriptions.
- With no plan in the project, the verdict is `unsure` with "no floor plan in the project to compare with".
- `relevance.plans` holds only drawing ids in this project's `drawings[]` (#152 item 10): ingest drops any other
  id a judge returns.
- The relevance is always a suggestion. A person overrules it with
  `POST /api/projects/{id}/files/{file_id}/relevance` `{verdict: related|unrelated, by}`, or `{undo: true}`.
  - `by` follows `SignOffRequest.by` exactly: the free text the person types, required, 1-100 characters, 422
    `validation` otherwise (#152 item 2). `undo` follows unsettle: it needs nothing else, and with no call made it
    is 200 with the file unchanged (#152 item 3).
  - Overruling to `related` does not read the file as a plan: it stays `set_aside`, with no drawing (#152 item 4).
  - The overrule is kept in the project's own status (the file's `triage.overruled`), written by the ingest
    service under its lock, only once the project is `done`. This replaces the separate
    `<projects_dir>/api/triage/<project id>.json` store of the draft (tables-fix, 2026-11-14 13:20): every route
    that shows a `FileStatus` (project, both traces) then shows the call with no merging, and the project list's
    kept counts (#145's `KeptReviews`, keyed on the status) recompute `issues_open` after a call. A side store
    would have left that count stale.
  - The judge's own verdict stays as it was.
- Re-run: a project's files are fixed once its ingest is done (a new upload is a new project), so it runs once per
  ingest. A judge adapter that caches keys on a hash of the `ProjectContext`.

### 5. API (additive to v1)

- `FileStatus.triage: Triage | null` (optional). It is null when triage is off, for a file that isn't image-like,
  and while queued.
  - It appears in `GET /api/projects/{id}` `files[]` and in both trace routes (`FileTrace.file`).
  - `Skipped` stays `{path, reason}`; the reason says "not a floor plan: …".
- `ProjectView` and `ProjectSummary` gain `not_plans: int | null` (#152 item 9): triaged files with `class !=
  floor_plan`. Overruled files still count (a call changes the verdict, not the class). Files set aside for their
  format (`triage: null`) never count. Null until `done`, then final. Left out of the JSON when the project was
  ingested with triage off (the status's `readers` has no `triage`).
- Issues feed (decision 0008): kind `unrelated_file`, already in `IssueKind` since #147 (every planned kind is in
  the type from the start; this decision makes it produced):
  - one issue per non-plan whose `verdict` is not `related`, undescribed and unjudged ones included (#152 item 7),
    and per non-plan a person made a call on;
  - severity: `needs_person` when the judge said `unsure`, else `note` (#152 item 8). It is the judge's verdict,
    not the person's, so a call never moves the issue;
  - state `open`, or `settled` once a person made a call, either way: a call to `related` keeps the issue,
    `settled`, with the same `id` and place in the order, and confirming `unrelated` settles it too (#152 item 1);
  - `why` = the class, the description's subject and the relevance `why` (or the note), and the person's call, for
    example "Not a floor plan (another kind of drawing (…): a music score). Unrelated: no word on it is on the
    project's plans or in its file names. Ana says it is related.";
  - `reason` = the `verdict` (null while there is none); no page, box or drawing; `links.trace` to the file.
  - Such a file has no `set_aside` issue as well.
  - A non-plan judged `related` that nobody called is no issue.
- New route `POST /api/projects/{project_id}/files/{file_id}/relevance`. It is 404 `not-found` for an unknown
  project or file, 409 `not-allowed` until `done`, and 422 `validation` for a body outside the shape (a `verdict`
  of `unsure`, no `by`). It returns the file's `FileStatus`. Relaxed by section 8: any file triage set aside takes
  a call, described or not; a file it did not set aside is 422 `not-triaged`. The draft's 422 `no-description`
  for an undescribed file is gone (#152 item 3 as first built).
- No new trace stage: triage is in the `identify` stage's line, and `Stage` is unchanged (#152 item 5).
- Read it as a floor plan (#152 item 12, shape posted on #152 c6876693460, built 2026-11-14):
  `POST /api/projects/{project_id}/files/{file_id}/triage` `{class: "floor_plan", by}` -> 202 with the file's
  `FileStatus` (`queued`). The ingest service rebuilds the finished project's live record (`Run.resumed`) and
  reads that one file in the background through the usual group, route and readers; the project stays `done`.
  - `Triage.read_as_plan: {by, at} | null` records the call; `class` stays the classifier's. The file leaves
    `not_plans` (a class call; orchestrator, 2026-11-14), gets a `drawing_id` and is in `drawings`.
  - Its `unrelated_file` issue stays, `settled`, same id and place, with "<by> had it read as a floor plan" in
    `why` and, once read, the file's `drawing_id` (R6-a-4); the new drawing's own issues join the list and the
    others keep their order.
  - A reading that fails or a restart cuts off sets the file aside with why and clears `read_as_plan`: the file
    is back to triage's call and can be asked again (R6-a-1, orchestrator 2026-11-14).
  - 404 unknown file; 409 `not-allowed` until done, while a re-read runs, or for a file already read this way; 422
    `not-triaged` for a file triage did not set aside (a new code); 422 `validation` for another `class`.
  - No undo: a reading is not unread. A relevance call still works.
  - A re-read cut off by a restart: the file is set aside at startup ("not read as a floor plan: the server
    restarted during ingest") and the project stays done.
- `openapi-v1.json` is regenerated. Fixtures are appended last: `project_triaged.json` (a project with a
  triaged file, made with the fakes) and `relevance_request.json`. Existing fixtures stay byte-identical: with
  triage off, `triage` and `not_plans` are left out of the JSON (`exclude_if` None, as `Drawing.double_check`
  does).

### 6. Interfaces: three protocols in core, adapters behind settings

In `app/core/ingest/ports.py`:

```python
class Classifier(Protocol):
    def classify(self, image: bytes, probed: Probed) -> Classified | Unavailable: ...   # class, p_plan, method

class Describer(Protocol):
    def describe(self, image: bytes, classified: Classified) -> Description | Unavailable: ...

class RelevanceJudge(Protocol):
    def judge(self, description: Description, context: ProjectContext) -> Relevance | Unavailable: ...
```

- `Unavailable(note)` is the declared degraded mode. A classifier that is unavailable leaves the file as today,
  that is unsure means plan.
- Settings: `TRIAGE_CLASSIFIER`, `TRIAGE_DESCRIBER` and `TRIAGE_JUDGE`, each `off` (default) or an adapter name.
  `app/composition.py` is the only place that picks them. Default `off` everywhere; DEMO_ENV turns triage on only
  after eu-big's classifier passes its gate, and the orchestrator decides that (amendment 3).
  - `TRIAGE_CLASSIFIER=rules` (`app/adapters/triage/rules.py`): no model, from the content probe's kind. It sets
    aside exactly what ingest sets aside today (a camera photo not of a drawing, an image the kind signal calls not
    a drawing) and calls everything else unsure, so a floor plan. It lets the offline demo show triage on those
    files at no cost. The describer has only `off` until eu-big's adapters land.
  - `TRIAGE_JUDGE=rules` (`app/adapters/triage/rules_judge.py`, 2026-11-14): the baseline fixed before any model,
    `not_drawing` -> unrelated, `other_drawing` -> related (unsure since section 8), a `why` that says it was not
    read. Section 8 replaces it for described files with the rule over the description's form and drops the model
    judge; it stays the named fallback for undescribed ones. The judge port gets the class as `kind`.
    It reads no description (`reads_description` False on the port), so it also judges non-plans nothing described
    (no describer set up, or the describer refused); a judge that reads descriptions still skips them.
  - The default `off` keeps today's behaviour exactly, in no-keys mode too.
  - The describer and judge run only when the classifier is on.
- eu-big's chosen models land as adapters (`app/adapters/triage/<name>.py`) without touching the stage.
- Tests run with fakes (`backend/tests/triage_fakes.py`): a classifier and a describer keyed by the file's
  bytes, and a judge that matches printed words against the project's text.
- Triage is per file entry, so when qa-c's multi-page PDF work (one drawing per drawn page, branch
  `ingest/multi-page`) gives each page its own entry, a page entry is triaged like an image file (amendment 4).
- The `ProjectContext` builder and the stage logic are pure core functions (`app/core/ingest/triage.py`),
  checked by `tests/test_architecture.py` (core imports no adapter).

### 7. No-keys mode and the demo

- No-keys, and triage off (the default): nothing changes. The sample's `photos/site.jpg` stays set aside as "a
  photo, not of a drawing".
- No-keys with `TRIAGE_CLASSIFIER=rules`: `site.jpg` is `not_drawing`, not described ("no description model is set
  up"), an `unrelated_file` issue with no verdict, cost 0.00 USD.
- Demo config with triage on:
  - The sample's `site.jpg` (a synthetic camera photo) becomes `not_drawing` with a description, and is judged
    against flat-a/flat-b's text. It is probably `unsure`, since the photo is synthetic: the demo shows the
    verdict honestly.
  - In the demo upload (`data/demo/demo-project.zip`), its scans and photos are triaged. What they become is
    measured when the classifier lands, not assumed here.
- QA checks the golden demo path both with triage off and with it on.

### 8. Sheet register, description form and relevance by rule (COMMON decisions 8-11, 2026-11-14)

Bogdan made triage a priority (2026-11-14 ~14:40: "MAKE THIS A BIG priority ... Maybe not 1 sentence summary but
longer so that we can use that later, the ai will be able to"). This section adds to sections 2-6 and wins where
they differ. Proposed by tables-fix 2026-11-14 14:20. Accepted by the orchestrator with two additions (the
personal-data rule for `visible_text`; any verdict can be overruled) and by Tudor's fleet's review (#152
c6877112058), whose 8 points are written in below.

**The register (decision 8).** `Triage.register: Register | null`, inside the triage (Tudor's review item 2):

```text
Register = {
  kind: "floor_plan" | "multi_view_sheet" | "site_plan_or_map" | "elevation" | "section" | "detail"
      | "perspective_or_axonometric" | "engineering_non_building" | "cover_or_text_sheet"
      | "photograph" | "not_architecture" | "other",            # the answer key's 12 kinds
  has_floor_plan: bool,                                        # the gate (plan recall >= 99%, decision 2)
  photo_of_sheet: bool,                                        # a camera photo of a sheet
  scale_shown: "bar" | "ratio_text" | "dimensions" | "none" | "unreadable",
  quality: "good" | "fair" | "poor",
  method: str,                                                 # which classifier; equals triage.method
}
```

- It is set by the classifier on the image-like files of section 1, floor plans included (display only: a plan's
  `scale_shown` is never compared with what its reader found; the ingest screens show it on non-plans). It is
  null with a classifier that gives no register (`TRIAGE_CLASSIFIER=rules` has no model). Triage itself is null
  when triage is off, while the file is queued, on vector PDFs, IFC, DXF and SVG, and when the classifier can't
  say (`Unavailable`: read as a plan, with the trace note), so there is no register either.
  - Why null and not filled from what ingest knows: no classifier looks at those files, and before reading ingest
    knows only their format. A register made from the reading (rooms read, so a floor plan) would be a guess shown
    as a fact, and the reading is already on the file (`drawing_id`, `takeoff`). An IFC model is not a sheet, and
    none of the 12 kinds fits it.
- `Triage.class` is derived in core from the register (`class_of` in `app/core/ingest/model.py`; a classifier
  that gives both a register and a class that disagrees with it is refused):
  - `floor_plan` when `has_floor_plan` or `kind` is `floor_plan`. If either says plan, it is read (unsure means
    plan: the key has 14 `floor_plan` rows with no plan flag, and 8 photographs of a plan);
  - else `not_drawing` for `photograph`, `not_architecture`, `cover_or_text_sheet` and `other`;
  - else `other_drawing`.
  - `p_plan` stays the gate's probability.
- `photo_of_sheet`, `scale_shown` and `quality` are shown, not acted on in this version. The rectifier still
  follows the probe's photo flag (measured: 26/30 phone photos). Screens show `register.kind` (Tudor's review
  item 3).

**The description form (decision 10).** `Description` gains four fields. The six it had stay as they are:

```text
Description = {
  text, subject, text_seen, language, model, cost_usd,         # unchanged
  what_it_is: "photograph" | "artwork" | "text_page" | "object" | "music" | "map" | "drawing" | "other",
  shows_building: bool,
  visible_text: str,       # every legible word, as printed, line breaks kept; "" when none; max 2,000 characters
  detail: str,             # a paragraph or more: what it shows, kept for later AI use; max 4,000 characters
}
```

- `drawing` means an architectural or technical drawing that is not a floor plan. The register's `kind` says which.
- `text` is the short form (1-3 sentences) the file row and the issue's `why` show. `detail` is the long form for
  search, answering, relevance and Stoa. The describer writes both in the same call, and `text` sums up `detail`.
  The screen shows `detail` collapsed.
- `text_seen` stays the title-block and caption items (at most 20), taken from `visible_text`. Screens show
  `visible_text`; `detail` may be shown collapsed, labelled as a model's description no person checked.
  `what_it_is` and `shows_building` feed the rule and later AI use; the rule's `why` says in words whether it
  shows a building.
- Personal data (orchestrator, 2026-11-14, verbatim: "printed text kept (project, company, place, room names,
  title block), but personal contact data of private persons (phone numbers, e-mails, home addresses) and names
  of people seen in photos are left out"). This is section 3's rule for `text_seen` (number plates, home
  addresses) widened, and it covers `visible_text` and `detail` alike. Nothing that isn't visible is guessed.
- The four fields are required. No stored description exists to break, since the describer was only `off` before
  this. Cached by the file's sha256, describer name and prompt version, as section 3 says. Tests check the form
  fields, never `detail`.

**Relevance by rule (decision 11, with Tudor's review item 1).** The model relevance judge is dropped. The rule is
a pure core function, `triage.relevance_by_rule(description, context) -> Relevance`, over the form:

- The facts (`ProjectContext`, gaining `project_name`) are the project's name, its file and folder names, and the plan
  text of section 4 (room and flat labels, storeys, table titles, model object names). Title-block text and the
  address join when the drawing model keeps them; it keeps neither yet. `relevance_of` drops the judged file's own
  name from the context, as it already drops its own subject.
- The words matched are those in `visible_text` and `text_seen`: casefolded, accents folded, split on anything
  that isn't a letter. Kept: 4 or more letters, not on a fixed stop list of drawing words (plan, floor, scale,
  section, elevation, drawing, sheet and their fi/sv/de/fr forms). A number alone is never a match.
- `related` only when at least one word is shared: "Related: 'rosa', 'villa', printed on it, are in the project's
  name; it shows no building." `matched_on` lists each shared word and where it matched, at most 5.
- `unsure` when it shows a building but nothing is shared: "Unsure: it shows a building, but none of its printed
  words is in the project's name, file and folder names or plan text." A person decides (`needs_person` issue).
- `unrelated` when it shows no building and nothing is shared: "Unrelated: it shows no building, and none of its
  printed words is …". When nothing is printed, the why says "it has no printed text". This is Bogdan's rule ("not
  relevant when no building and no shared text"); everything in between asks a person.
- With no floor plan in the project the verdict is `unsure`, as section 4 says (checked before any rule).
- `judge` names the rule: "rule on the words printed on it and whether it shows a building, no model".
- `TRIAGE_JUDGE` stays `off | rules`. With `rules`, a described file gets this rule, and an undescribed one gets
  the class rule of section 6 as the named fallback ("rule on the kind of picture, no model (no description to
  read)"): `not_drawing` is `unrelated`, and `other_drawing` is now `unsure` (was `related`; Tudor's review item 1).
- A person can overrule any verdict, rule-made or model-made, described or not (orchestrator, 2026-11-14), so every
  `unrelated_file` issue can be settled: `POST …/relevance` takes any file triage set aside (section 5).
- Still a suggestion a person overrules (section 4). The API shape of `Relevance` is unchanged.
- How many of the full set's 152 random pictures come out not relevant is reported when the describer lands. It is
  not assumed here.

## Alternatives considered

- A new `FileState` value (`not_plan`): it widens the enum Tudor's screens switch on (`STATE_LABEL:
  Record<FileState, …>` in `frontend/src/ingest/ingest.ts:69` fails the type check), and `set_aside` already means
  "kept, not read, here is why".
- Replacing the kind signal with the classifier: the kind signal's photo flag feeds the rectifier and is measured
  (26/30 photos, 0/376 scans). Keeping it as an input costs nothing. Its not-a-drawing rule is the one part triage
  takes over.
- Triage after the readers (judge the reading): a non-plan would be read and paid for first, and a 0-room reading
  can't tell an elevation from a bad scan.
- Describing every file, plans too: it pays for a vision call on every plan for nothing the takeoff uses.
- Relevance on upload, file by file: there is no project context until the plans are read (Bogdan: "after the
  context with everything").
- Deleting unrelated files: the orchestrator ruled it out (COMMON 3 and 4). It stays a suggestion.

## Consequences

- The kinds of the archive sources stop going to the floor-plan readers. That is less noise in the takeoff and the
  issues feed, and less reading time.
- The plan-recall requirement (>= 99%, all CubiCasa val, Swiss PNG plans, phone photos and hand-drawn sheets
  called plans) is a release gate for the classifier adapter, measured by eu-big. Until it passes, the setting
  stays `off` in the demo config.
- No new store (the call is in the project's status), one new route, three new settings, three protocols and
  fakes, one no-model classifier. The issues feed starts producing `unrelated_file`.
- Tudor's fleet gets to show triage on the ingest screen (class, description, relevance with an overrule), the
  `not_plans` count, and the new issue kind.
- Revisit: vector PDFs (elevation sheets drawn as vectors) if QA finds them common.

## Amendments and review answers

Orchestrator, 2026-11-14 13:11 (GO for Part B):

1. The date is fixed (written 13:09). Board thread #152.
2. Class overrule ("read it as a floor plan"): at 99% plan recall about 1 in 100 real plans is set aside with no
   way back. Assess re-reading one file inside a finished project; build `POST …/files/{file_id}/triage
   {class: "floor_plan", by}` if it fits in about 2 hours, after its shape is posted to #152. Assessed as fitting,
   posted on #152 (c6876693460) and built (section 5).
3. Default `off` everywhere; DEMO_ENV turns triage on only after eu-big's classifier passes its gate.
4. Triage is per file entry, robust to the coming multi-page PDF entries.

Tudor's fleet's review, answered by the orchestrator on #152 (c6876449112), all 12 accepted: 1 a call keeps the
issue settled in place; 2 `by` as a sign-off's, `undo` as unsettle; 3 codes `not-allowed`, `no-description`,
`validation`, undo with nothing to undo is 200; 4 `Triage.verdict`, a call to related is no reading; 5 no new
stage; 6 plain words; 7 `Triage.note` and its cases; 8 `unsure` is `needs_person`; 9 `not_plans`; 10 `plans[]`
within the project; 11 costs counted, no personal data in descriptions; 12 the reserved `/triage` route. Each is
written into the sections above.

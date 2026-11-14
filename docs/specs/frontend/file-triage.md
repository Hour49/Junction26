# File triage: not-a-floor-plan files, their description, relevance and a person's call (spec, decision 0010)

Status: draft for frontend-orch's review, 2026-11-14, by fe-ingest. Build: the call (`/relevance`) now, against main
9bf74e4 (PR #161); the "Read it as a floor plan" button once Bogdan's `/triage` PR lands (shape: #152 c6876693460).
API: docs/API.md "File triage (decision 0010)" and "POST …/relevance"; record `docs/decisions/0010-file-triage.md`;
types `frontend/src/api/schema.d.ts` (`Triage`, `Description`, `Relevance`, `Overrule`, `RelevanceRequest`).

Where it lives: this one file, not sections in three specs. It changes two screens of mine (the ingest file rows and
the trace, `ingest.md`; the issues list, `issues.md`, each with a one-line pointer here) and nothing in
`advanced-ingest.md`: triage has no stage of its own, it is a part of the `identify` line that the Advanced view and
the trace already show as is (0010 §2, #152 item 5).

Names from the shared spec (`shared.md`) and the ingest/issues specs: `getProject`, `getTrace`, `previewUrl`,
`formatTime`, `plural`, `StateBadge`, `usePoll`, `kindOf`, `routeOf`, `mockApi`, the typed fixtures of
`src/api/fixtures.ts`.

## Purpose

With triage on, an image that is not a floor plan (an elevation, a section, a site photo, a music score) is kept
but not read. The person needs to see, per file: what triage thinks it is, what is on it, whether it belongs to this
project and why, and to make the call themselves. The screens say it in words, never guess, and never promise more
than the API does: a call to "related" does not read the file (it stays set aside, no drawing).

With triage off (the default) nothing on any screen changes: every element below is drawn only when
`file.triage` is not null, `not_plans` is a number, or an issue's kind is `unrelated_file`.

## Files owned

| File | What |
| --- | --- |
| `src/ingest/triage.ts` (new) | pure: `CLASS_LABEL`, `VERDICT_LABEL`, `isNotPlan(file)`, `rowLine(triage)`, `callLine(triage)`, `canCall(file)`, `callError(error)` |
| `src/ingest/TriageCard.tsx` (new) | the trace's card: class, preview, description, relevance, the call form, the reserved read-as-plan button |
| `src/ingest/ProjectScreen.tsx` | file row line for a triaged file; the `not_plans` line under "Files" |
| `src/ingest/FileTraceScreen.tsx` | renders `TriageCard` under the facts; replaces `file` with a POST's answer |
| `src/ingest/usePoll.ts` | returns `set(data)` too, so a POST's answer replaces the shown data without a reload |
| `src/issues/issues.ts` | `KIND_LABEL.unrelated_file`; `routeOf` link to the trace |
| tests beside each (`triage.test.ts`, `TriageCard.test.tsx`, existing `ProjectScreen`/`FileTraceScreen`/`issues` tests) | |

Asks of fe-shared (`src/api/`): export `Triage`, `Description`, `Relevance`, `Overrule`, `RelevanceRequest` from
`types.ts`; client `postRelevance(projectId, fileId, body: RelevanceRequest): Promise<FileStatus>` (POST
`/api/projects/{pid}/files/{fid}/relevance`); add `project_triaged.json` and `relevance_request.json` to
`fixtures.ts`. Later, with the `/triage` PR: `readAsPlan(projectId, fileId, by): Promise<FileStatus>`.

## Words

`CLASS_LABEL` (closed list, 0010 §2):

| `class` | Words |
| --- | --- |
| `floor_plan` | a floor plan |
| `other_drawing` | another kind of drawing |
| `not_drawing` | not a drawing |

`VERDICT_LABEL` (icon + word, never colour alone):

| `triage.verdict` | Pill | Sentence |
| --- | --- | --- |
| `related` | ✓ Related | Related to this project |
| `unrelated` | ✕ Not related | Not related to this project |
| `unsure` | ? Unsure | Unsure whether it belongs to this project |
| `null` | – Not judged | (the `note`, as sent) |

`description.subject`, `description.text`, `method`, `relevance.why`, `relevance.judge`, `matched_on[]`, `note` and
`description.model` are plain words from the API, shown as they are (0010 §2, #152 item 6). `p_plan` is shown as a
percent ("chance of a floor plan 3 %"), `round(100 × p_plan)`.

## User flow

1. Project screen, file list. A triaged file that is not a plan (`triage.class != floor_plan`) keeps its row (link
   to the trace, badge "set aside", kind, size, time). In place of the `reason` line (it repeats the class with
   `P(plan)` and the method) it shows `rowLine`: "Not a floor plan: <class words> · <subject>" (subject left out
   when `description` is null), then the verdict pill, then " · <by>'s call" when `overruled` is set. A triaged
   file triage called a floor plan shows its row as today (nothing added).
2. Under the "Files" heading, when `not_plans` is a number: "<n> not floor plans: kept, not read" (`plural`; "1 not a
   floor plan: kept, not read"; with 0: "Every image is a floor plan"). Left out while `not_plans` is null or absent
   (running, or triage off).
3. The user opens the file's trace. Under the facts card, the triage card (`section`, `aria-label` "Is it a floor
   plan?"):
   - heading "Not a floor plan: <class words>", then "Chance of a floor plan <p> % (<method>)";
   - the upload itself: `<img src={previewUrl(pid, fid)}>`, alt "<path> as uploaded", "Preview not available" on a
     failed load (a non-plan has no drawing, so `BeforeAfter` is never shown; this is the only picture of it);
   - "What is on it": `description.text`, "Subject: <subject>", and when `text_seen` is not empty a collapsed
     `<details>` "Text printed on it (<n>)" listing each item (and "language: <language>" when set); "Described by
     <model>". When `description` is null: the `note` in its place;
   - "Does it belong to this project?": the verdict pill and sentence; when `relevance` is set its `why`, "Matched
     on: <a>, <b>" (when not empty) and "Judged by <judge>"; when `relevance` is null the `note` (if not already
     shown above);
   - the call (step 4) and, once its route exists, "Read it as a floor plan" (step 6).
4. The call. Shown when `canCall(file)`: `triage` set, `class != floor_plan`, `description` not null (else the API
   answers 422 `no-description`; the note already says why). With no call yet:
   - "Your name" text field (max 100 characters), filled from this browser's saved name, the surveyor's key
     `countersign.surveyorName` (one name across sign-off, double-check and this; a failing `localStorage` leaves it
     empty and the screen working);
   - two buttons "It is related" and "It is not related", both always offered (confirming the judge's verdict is a
     call too: it settles the issue), disabled while the trimmed name is empty or a request is in flight;
   - the line "Your call replaces the suggestion and settles this file's issue. It does not read the file as a
     plan.";
   - a press sends `{verdict, by: <trimmed name>}` (`relevance_request.json` for "It is related" by "Ana"), saves the
     name, and on 200 replaces the trace's `file` with the answer (the card then shows step 5).
5. With a call made (`overruled` set): `callLine`: "<Verdict sentence>: <by>'s call, <formatTime(at)>. The
   judge said: <relevance verdict word>." (the judge part left out when `relevance` is null), and a button "Undo the
   call" sending `{undo: true}` (0010: undo needs nothing else); on 200 the card returns to step 4.
6. Reserved, built when the `/triage` PR lands: "Read it as a floor plan" (secondary button), shown when `triage`
   is set, `class != floor_plan`, `read_as_plan` null and the file is `set_aside`; it uses the same name field.
   It asks `window.confirm("Read <path> as a floor plan? This can't be undone.")`; confirmed, it sends
   `POST …/files/{fid}/triage {class: "floor_plan", by}`, and on 202 replaces `file` with the answer (state
   `queued`): the trace polls again while the file is `queued`/`running` (its existing predicate), and on `ready` the
   existing "Open the drawing" appears. Once `read_as_plan` is set the card reads "<by> had it read as a floor
   plan, <formatTime(at)>" and the button is gone (no undo). The project screen then also polls while any file
   is `queued`/`running` (today only while the project is), and the row's line reads "Read as a floor plan on
   <by>'s call". Until the PR lands the button is not rendered (no disabled placeholder: it would promise a
   capability that does not exist).
7. Issues list: an `unrelated_file` issue is a row like any other: kind "Not a floor plan" (icon ▭), severity group
   from the API (`needs_person` for unsure, else `note`), `why` as sent, place "not on a drawing", plan panel "This
   issue has no place on a drawing.", and one link to the trace `#/p/<pid>/f/<file_id>` (keeps `pack`): "Make a
   call" while `open`, "See the call" when `settled`. After a call the issue keeps its `id` and `n` and reads
   "settled" (Bogdan, #152 item 1).

## API calls

- `GET /api/projects/{pid}` (as today): `files[].triage`, `not_plans`. Fixture `project_triaged.json`.
- `GET /api/projects/{pid}/files/{fid}/trace` (as today): `file.triage`.
- `GET /api/projects/{pid}/files/{fid}/preview.png?width=1600` (as today, `previewUrl`): the triage card's image.
- `POST /api/projects/{pid}/files/{fid}/relevance` (`postRelevance`; fixture `relevance_request.json`): body
  `{verdict: "related"|"unrelated", by}` or `{undo: true}`; 200 → the file's `FileStatus`. Errors, shown under the
  buttons (`role="alert"`), buttons usable again, the shown file unchanged (`callError`):

  | Status, `code` | Shown |
  | --- | --- |
  | 409 `not-allowed` | "The project is still being read: a call can be made once it is done." |
  | 422 `no-description` | "This file was not described, so there is nothing to judge or overrule." |
  | 404 `not-found` | "This file is no longer in the project." (`detail`, `code`) |
  | 422 `validation`, any other | `detail` (`code`) |

- Reserved `POST /api/projects/{pid}/files/{fid}/triage` (`readAsPlan`): body `{class: "floor_plan", by}` → 202
  `FileStatus`. Errors: 409 `not-allowed` "The project is still being read, or this file is being read again
  already."; 422 `not-triaged` "Triage did not set this file aside, so there is nothing to read again."; 404, 422
  `validation`, other: `detail` (`code`).
- `GET /api/projects/{pid}/issues` (as today): kind `unrelated_file`.

Not used: `relevance.plans[]` (the trace has no `drawings` to name them, and `why` already says what matched),
`description.cost_usd` (counted in the file's and project's `cost_usd`, already shown), `description.language`
outside the collapsed text list, `ProjectSummary.not_plans` (screen 5 is fe-golden's, account.md).

## States

| State | Row (screen 2) | Triage card (trace) | Reach it |
| --- | --- | --- | --- |
| Triage off | as today | not drawn | `project.json`, `trace.json` |
| Running, not judged yet | class line, "– Not judged" | description; note "not judged yet: the project is still being read"; call form shown (409 explains if pressed) | variant `triaged-running` |
| Judged, no call | class line, verdict pill | description, relevance, call form | `project_triaged.json` `files[1]` (related) |
| Unsure | "? Unsure" | as above with unsure | variant `triaged-unsure` |
| Called | pill of `verdict` · "Ana's call" | `callLine`, "Undo the call" | `project_triaged.json` `files[2]` |
| Not described | class line, "– Not judged" | note in place of description and relevance; no call form | `project_triaged.json` `files[3]` (refused); variant `triaged-offline` |
| Sending | | both buttons disabled, "Saving your call…" | a pending promise |
| Call failed | | the error line of the table | `mockApi` 409/422/404/500 with `error.json` spread with the `code` |
| Read as a plan (reserved) | "Read as a floor plan on Ana's call" | "Ana had it read as a floor plan, …" | variant `read-as-plan` |

Variants (each starts from the named fixture; only the listed fields change):

| Variant | From | Changes |
| --- | --- | --- |
| `triaged-running` | `project_triaged.json` | `state: "running"`, `not_plans: null`; every triaged file: `relevance: null`, `overruled: null`, `verdict: null`, `note: "not judged yet: the project is still being read"` (`files[3]` keeps its note) |
| `triaged-unsure` | `project_triaged.json` | `files[2].triage`: `overruled: null`, `relevance.verdict: "unsure"`, `relevance.why: "no floor plan in the project to compare with"`, `verdict: "unsure"` |
| `triaged-open` | `project_triaged.json` | `files[2].triage`: `overruled: null`, `verdict: "unrelated"` |
| `triaged-offline` | `project_triaged.json` | `files[3].triage.note: "not described: no description model is set up, so it is not judged"` |
| `not-plans-zero` | `project_triaged.json` | `not_plans: 0` |
| `trace-triaged` | `trace.json` | `file`: a variant's or the fixture's `files[k]`; `stages`: `trace.json`'s up to and including `identify` |
| `read-as-plan` | `project_triaged.json` | `files[2].triage.read_as_plan: {by: "Ana", at: "2026-11-14T08:06:00Z"}` (with the `/triage` PR's types) |
| `issue-unrelated` | `project_issues.json` | `issues[0]` spread with `kind: "unrelated_file"`, `severity: "note"`, `state: "open"`, `drawing_id`, `page`, `box`, `polygon`, `mark_id` null, `file_id: "f3"`, `reason: "unrelated"`, `links.trace` set; settled: the same with `state: "settled"` |

## Layout

Same tokens and cards as the trace (ingest.md "Layout"). The triage card sits between the facts card and the
stages card. The preview is at most 480 px wide on desktop, full width on a phone, aspect from the image. The verdict
pill is a `.v-pill` (related: plain; unrelated: plain; unsure: `v-pill--warn`), always with icon and word. The name
field and the two buttons sit in one row on desktop, stacked on a phone; tap targets at least 44 px at 390, no
horizontal scroll, long subjects and why lines wrap.

## Acceptance criteria

Ingest rows and project

- FT-1: With triage off (`project.json`) the file rows, the "Files" heading and the trace render exactly as before
  (no triage line, no `not_plans` line, no triage card). [component]
- FT-2: `project_triaged.json`: `elevations/south.png` row reads "Not a floor plan: another kind of drawing · the
  south elevation of a two-storey house" and "✓ Related"; its `reason` text is not on the row. [component]
- FT-3: `photos/site.jpg` row reads "Not a floor plan: not a drawing · a building site with a crane", "✓ Related"
  and "Ana's call". `photos/street.jpg` reads "Not a floor plan: not a drawing" and "– Not judged". [component]
- FT-4: `not_plans: 3` shows "3 not floor plans: kept, not read"; `not-plans-zero` shows "Every image is a floor
  plan"; `triaged-running` and `project.json` show no such line. [component]
- FT-5: `rowLine`, `callLine`, `CLASS_LABEL`, `VERDICT_LABEL` map every `class` and `verdict` value (incl. null) to
  words; `canCall` is false for `triage` null, `class` `floor_plan`, or `description` null. [unit]

Trace

- FT-6: `trace-triaged` with `files[1]`: the card shows "Not a floor plan: another kind of drawing", "Chance of a
  floor plan 3 % (fake classifier)", the preview `<img>` with alt "elevations/south.png as uploaded", the description
  text, "Subject: the south elevation of a two-storey house", a closed "Text printed on it (2)" holding "Küche" and
  "Süd", "Described by fake describer", the related sentence, "Related: Küche is on the project's plans.", "Matched
  on: Küche", "Judged by word judge". [component]
- FT-7: A failed preview load shows "Preview not available". [component]
- FT-8: `files[3]` (not described): the note "not described: the model refused" shows once, no description, no
  call form, no buttons. [component]
- FT-9: With a saved name "Ana", "It is related" on `triaged-open`'s `files[2]` sends exactly
  `relevance_request.json` to `POST /api/projects/5e0c1a2b3d52/files/f3/relevance`; the answer (`files[2]` of
  `project_triaged.json`) replaces the card: "Related to this project: Ana's call, 2026-11-14 08:05 UTC. The judge
  said: Not related." and "Undo the call". No GET is made for it. [component]
- FT-10: "It is not related" sends `{verdict: "unrelated", by: "Ana"}`: both buttons are offered even when the
  judge already said unrelated. [component]
- FT-11: The name field is limited to 100 characters, filled from `countersign.surveyorName`; both buttons are
  disabled while it is empty or spaces; the trimmed name is sent and saved; a throwing `localStorage` leaves the
  field empty and the card working. [component]
- FT-12: "Undo the call" sends exactly `{undo: true}`; on 200 (the answer with `overruled: null`) the form is back.
  [component]
- FT-13: 409 `not-allowed`, 422 `no-description`, 404 and 500 each show their line of the table in a
  `role="alert"`, the shown file is unchanged and the buttons are usable again; while a request is pending both
  are disabled and "Saving your call…" shows. [component]
- FT-14: Every pill and the card's state carry a word (no status by colour alone); at 390 every button and the name
  field are at least 44 px tall and nothing scrolls sideways. [e2e]

Issues

- FT-15: `issue-unrelated` shows kind "Not a floor plan" with its icon, "not on a drawing", and one link "Make a
  call" → `#/p/<pid>/f/f3`; settled it reads "See the call", same href; `?pack=` is kept. [unit] [component]
- FT-16: Its row keeps its `n` when its state changes between two loads (same `id`, same position). [unit]

Reserved: read as a floor plan (built when the `/triage` PR lands)

- FT-17: Before that PR the trace renders no "Read it as a floor plan" button in any state. [component]
- FT-18: After it: on a set-aside non-plan with `read_as_plan` null the button shows; cancelling the confirm sends
  nothing; confirming sends `{class: "floor_plan", by: "Ana"}` to `POST …/files/f3/triage`; the 202 answer
  (`state: "queued"`) restarts trace polling, and once the file is `ready` with a `drawing_id`, "Open the drawing"
  shows. [component]
- FT-19: `read-as-plan`: the card reads "Ana had it read as a floor plan, 2026-11-14 08:06 UTC", no button; the row
  reads "Read as a floor plan on Ana's call". 409 `not-allowed` and 422 `not-triaged` show their lines. [component]
- FT-20: The project screen polls while any file is `queued` or `running`, even when the project is `done`.
  [unit]

End to end (fe-golden, no-keys backend with `TRIAGE_CLASSIFIER=rules`)

- FT-21: The sample's `photos/site.jpg` row reads "Not a floor plan: not a drawing" and "– Not judged"; its trace
  shows the note "not described: no description model is set up, so it is not judged" and no call form; the issues
  list has an `unrelated_file` row "Not a floor plan" linking to that trace; cost stays "$0.00". With triage off
  (the default) the golden path is unchanged. [e2e]

## Out of scope

- Naming or linking `relevance.plans[]` on the trace (needs `project.drawings`; the `why` already names the match).
- A call from the file row or the issues row: the row is a link, so the buttons are on the trace only.
- Deleting or hiding a file judged unrelated (0010: never deleted, always a suggestion).
- `ProjectSummary.not_plans` on the workspaces list (fe-golden's screen 5).
- A filter "show only non-plans" on the file list.
- A login behind `by` (the name is typed, as for a sign-off).

## Not in the API

Nothing this spec needs is missing for the call. The read-as-plan route and `Triage.read_as_plan` are announced
(#152 c6876693460), not on main yet: FT-17..20 wait for them.

## Open points

1. **Kind word.** "Not a floor plan" for `unrelated_file` (the kind also covers unsure and not-judged files, so
   "Unrelated file" would claim too much). Say if the API's name should show instead.
2. **No disabled placeholder for read-as-plan.** The orch brief allowed "disabled/hidden"; hidden chosen (a disabled
   button promises a capability that does not exist yet).
3. **409 wording.** `not-allowed` covers "project not done" for `/relevance`; the screen does not fetch the project
   state on the trace to hide the form first (one more request for a rare case; the 409 line explains it).

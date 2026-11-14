# Project chat (spec, frontend, Vellum)
Status: draft, 2026-11-14 12:10, by fe-engineer; 13:10 one project ask (#135). Source: Tudor via frontend-orch (`.agents/briefs/fe-chat.md`):
"after settling all the conflicts it should have a button that sends us straight to a whole new chat with those
documents ingested … the chat should be completely empty not have the drawings already illustrated". API:
docs/API.md `GET /api/projects/{id}`, `POST /api/projects/{project_id}/ask` (Bogdan #135, 13:03).

## Purpose

A whole new, empty chat about every drawing of a project. Reached from the conflicts screen's "Start a new chat"
(conflicts.md) at `#/p/<pid>/chat`. Nothing is drawn until the user asks for it: no plan, no viewer, no marks, no
suggestion buttons. Questions and answers appear as turns; an answer links to its drawing ("Show it on <file>").

## Files owned

- `frontend/src/engineer/ProjectChat.tsx`: the route view `ProjectChat({projectId})`, mounted by the shell (shared.md).
- `frontend/src/engineer/projectAsk.ts`: `askable(drawings)` and `starters(lists)`.
- `frontend/src/api/client.ts`: only `askProject(projectId, question)` (+ its test in `client.test.ts`, the
  `ProjectAnswer` type and the `projectAsk` fixture), handed over by frontend-orch 13:03.
- `frontend/src/engineer/ProjectChat.test.tsx`, `projectAsk.test.ts`.
- Reuses, owned by the same worker: `AskBox`, `AnswerCard` / `Answer` (with `chat`: no plan column, no
  References, a "Show it on <file>" link; refusal headline "I can't answer that from these drawings."),
  `engineer.css` (`.en-*`).

## API calls

- `GET /api/projects/{project_id}` once on open (`getProject`): `name` is the title; `drawings[]` whose `state` is
  `ready` or `flagged` are the askable drawings (N); others (queued, running, text_only, set_aside) are not asked.
- `GET /api/drawings/{drawing_id}?project=<pid>` once per askable drawing, after the project, in parallel and not
  blocking (failures ignored): only `suggestions[]`, for the starter chips (Tudor 12:45). `starters(lists)` picks up to
  3: the first question of each kind (`quantity` up to its first `:` or `|`), a door count, an area and a window
  count first, then the rest in drawing order; fewer when fewer exist; never invented.
- `POST /api/projects/{project_id}/ask` with `{question}` on each question (`askProject` in `src/api/client.ts`),
  one call; the response is the generated `ProjectAnswer`: `{question, parts: [{drawing_id, name, answer}], total,
  total_unit, total_sure, total_note}`. `parts`: answering drawings first, then refused ones; `name` is the
  drawing's file in this project. `total`: only when one drawing answers, or the answering drawings are disjoint IFC
  storeys (the backend decides); `total_unit` its unit; `total_sure` every part in it is sure; `total_note` one plain
  sentence (always present). 404 unknown project, 409 until the project is done: the error turn.

## Layout and states

One centred column (as the engineer page, `.en-page`): the title (`h1`, project name, `.v-title` look: 32 px 700),
the thread (`<section aria-label="Chat">`), the ask box at the bottom (`AskBox`, placeholder "Ask about the
project's drawings").

| State | Shows |
| --- | --- |
| Loading | the shared loading view |
| Error (project 404/500) | the shared `ErrorView` and a link "Back to the project" (`#/p/<pid>`) |
| Empty (Tudor 12:45, "like the chatgpt ui or gemini ui") | ChatGPT/Gemini start page: the project name as a calm centred heading (28 px 600), the ask bar right under it in the upper middle (`padding-top: max(14vh, 40px)`, not stuck to the bottom, max 720 px wide), and directly under the bar up to 3 starter chips (`role="group"` "Suggested questions", centred, wrapping) that ask on click. No "Ask anything about…" line, no drawing |
| No askable drawing | the line "No drawing in this project can be asked yet." under the bar instead of chips; Ask disabled |
| After the first question | the heading, the thread, the ask bar sticky at the bottom (as the engineer page); no chips |
| Asking | the question bubble and "Reading N drawings…"; Ask disabled |
| Answered (one or more parts) | one card: the quantity label (small), the total (`answer-value`, 44 px) in `total_unit` when `total` is not null, a "Sure" badge after it when `total_sure` (as EN-53), `total_note`, then one line per answering part "<name>: <value>" with "Show it on <name>" linking to `#/p/<pid>/d/<drawing_id>/engineer?ask=<question>` (plus `&pack=<id>` when the chat has one), so that drawing opens already answering this question with its marks (engineer.md EN-72; QA R4b-1); no plan, no image |
| Refused by all | one refusal card: "I can't answer that from these drawings.", the first refusal's text and its `can_answer` chips (a click asks the project again) |
| The ask failed (404, 409, 500, network) | the engineer's error turn ("The question could not be answered: <detail>", code, Try again asks again) |

Phone 390: one column, no sideways scroll, the ask box sticks to the bottom (engineer.md EN-71 band).

## Acceptance criteria

Component tests with `mockApi`, `project.json`, `drawing.json` and `project_ask.json` (3 parts: flat-a 2, flat-b 2,
ground-floor refused; no total; the note), variants built from it.

- CH-1 Opening the route requests `GET /api/projects/<pid>` once; while pending the loading view shows; a 404 shows
  the error and "Back to the project".
- CH-2 Empty: the `h1` is the project's name, then the ask bar ("Question", "Ask"), then directly after it the group
  "Suggested questions" with "How many doors are there?", "What is the net floor area of all indoor rooms in m²?",
  "How many windows are there?" (from `drawing.json`'s suggestions); no "Ask anything about" text, no `img`/`figure`.
- CH-3 Asking sends one `POST /api/projects/<pid>/ask` with `{question}` and nothing to `/api/ask`; while pending
  "Reading N drawings…" shows and Ask is disabled.
- CH-4 One drawing answers (`total` 2, `total_unit` count): the total "2", the note, one line "plans/flat-a.pdf: 2"
  with "Show it on plans/flat-a.pdf" linking to that drawing's engineer route, no `figure` or `img` in the turn, no
  refusal text, no "Sure" badge.
- CH-5 `project_ask.json` (two answer, no total): no `answer-value`, its `total_note`, a line and a link each.
- CH-6 All refuse: one refusal card "I can't answer that from these drawings." with the first refusal's text and its
  `can_answer` buttons; a click asks the project again.
- CH-7 The ask fails (500, or 409 while reading): the error turn; Try again asks again.
- CH-8 A project with no askable drawing shows "No drawing in this project can be asked yet." and Ask is disabled.
- CH-9 `askProject` (client unit, `client.test.ts`): posts `{question}` as JSON to `/api/projects/<pid>/ask` and resolves
  `project_ask.json`; a 409 rejects with its `ApiError`.
- CH-13 The total is shown in `total_unit` (an area total "52.27 m²"), with the "Sure" badge (tooltip as EN-53) only
  when `total_sure`.
- CH-11 Clicking a chip asks it of every askable drawing; then the chips are gone and the ask bar comes after the
  thread (the empty layout class is gone).
- CH-12 `starters` (unit): first question per kind, door/area/window first, at most 3, fewer when fewer exist; the
  screen shows 1 chip when only one drawing has one suggestion, none when every drawing request fails (the bar still
  asks).
- CH-10 [browser] 1440 and 390: the empty chat shows the heading, the bar in the upper half and the chips (wrapping
  at 390); after "How many doors
  are there?" on the sample, answer cards and "Show it on" links, no plan; no sideways scroll.

## Opening with a question (`?ask=`)

Added 2026-11-14 13:45 by fe-engineer for #140 (brief `fe-checks-issues.md`): a `refused_answer` issue from a
project ask (`Issue.drawing_id` null) reopens its question here: `#/p/<pid>/chat?ask=<Issue.question>`. Same rules
as engineer.md "Opening at a question or a place": read once on mount, the URL kept, the value trimmed (empty: nothing
asked), asked exactly as typed after `GET /api/projects/{id}` succeeds (one project ask per mount, also under
StrictMode), so the screen goes straight to the thread layout (no empty start page, no starter chips). Not asked
when the project fails to load, or when no drawing is askable (the "No drawing in this project can be asked yet."
line shows, as CH-8). `q` is not read (engineer.md Open point 8).

Shell (fe-shared): the chat route passes `query` to `ProjectChat({projectId, query})` as it does for the workspace
routes (`App.tsx` today passes only `projectId`).

- CH-14 `?ask=How many doors are there?`: after the project loads, one ask with that question (also in
  `<StrictMode>`); the article named by the question shows its card; no "Suggested questions" group and no
  `.en-chat--empty`. [component]
- CH-16 (QA R4b-1, Bogdan #14 c6876295838) Each "Show it on <name>" href is
  `routeHref({name: 'workspace', projectId, drawingId, role: 'engineer', query: {ask: <the turn's question>}})`; with the
  chat opened at `?pack=fi` the query also carries `pack=fi`; never an empty query. [component]
- CH-15 `?ask=` empty or spaces: nothing asked, the empty start page; a project 404 or a project with no askable
  drawing: nothing asked. [component]

## Demo parity (Tudor 16:25, brief `fe-demo-parity.md`)

Added 2026-11-14 16:40 by fe-engineer. Ports the demo's chat (`demo/vellum/chat.js`, `style.css`; PRs #201, #204,
#210 and the follow-up chips) onto the real API. It **replaces** the "Answered" and "After the first question" rows
of "Layout and states" and amends CH-4, CH-5 and CH-11 as noted; everything else above stands. Demo data (its
"combined" house-set answers, hand-made facts per sheet) is not ported: the card shows only what `ProjectAnswer`
gives.

### Answer card (one or more parts answered)

Order of the answering parts (the **references**): parts whose file is not a floor plan first, then the floor
plans, each group in the API's order. "Not a floor plan" = the part's file (`project.files[]` with the same
`drawing_id`) has `triage.class` `other_drawing` or `not_drawing` (a sheet a person had read as a floor plan, decision
0010). No triage, or `floor_plan`: a floor plan. The rows and the references use this one order, so row *n* is
reference *n*.

- **Lead line** above the card (17 px, max 62ch, `.en-lead`): with a `total`, the total in bold in `total_unit` (+
  the "Sure" badge when `total_sure`, CH-13), test id `answer-value`, then `total_note` muted only when
  `refused_note` is null (with refused drawings the note ends with them and there is no field without them: API
  ask 4); without one, `why_no_total` (PR #221; `total_note` when it is null) alone (the backend's sentence
  already says how many drawings answered). `refused_note` is never shown (#204). The quantity label (small) stays above it.
- **Card**: two columns (`minmax(0, 1.4fr) minmax(0, 1fr)`), one column at ≤900 px (figure first).
  - **Left, the current reference** (`<figure aria-label="Reference <i> of <n>">`): the reference's page drawn by the
    shared viewer with that part's answer (`PageViewer` through `Plan`: `file` = the part's `name`, so its name sits
    above the image; `pages`, `marks`, `unit`, `legend` from `answer`; no `credit` line, rule 4). Starts at reference 1.
  - **Arrows on the image's sides**: "Previous reference" / "Next reference", round 44 px buttons over the left and
    right edge, vertically centred (the engineer's `.en-nav` look); they wrap around; shown only with two or more
    references that have a page.
  - **Right**: one row per answering part, "<name>: <value>" (value via `formatValue`), the status pill (the
    engineer's status words, EN-31; "Sure" when `line.sure`), and "Show it on <name>" (CH-16 href, unchanged); then
    "References" (13 px 600) and a numbered list: each reference a button (number badge, the file name mono 600, a
    muted line "<kind words> · <route words>", `kindName` / `routeLabel`), `aria-pressed` on the current one; a click
    shows it on the left. A part with no page (a building model) is listed as plain text with "· no preview" and is
    skipped by the arrows.
- No plan of a refused drawing, no refused drawing's line, no credit or source line on the card (#204). The
  all-refused case keeps its one refusal card (CH-6).

### Follow-up questions (after the first answer)

After the thread and before the ask bar: a group "Follow-up questions" (`role="group"`, the starter chips' look) with up
to 3 questions not asked yet in this chat, from the same drawing suggestions the starters use (`GET
/api/drawings/{id}?project`, already loaded): `followUps(lists, asked)` = every distinct question, the first of
each kind first (door, area, window, then the rest, as `starters`), then the others in drawing order, minus the asked
ones (compared trimmed), first 3. A click asks it. Hidden while the newest turn is a refusal (its own `can_answer`
chips are the choice then, as EN-60) and when none is left; disabled while an ask is pending.

### Criteria

- CH-30 Two answering parts, the second one's file triaged `other_drawing`: rows and references list it first; row
  1 and reference 1 name the same drawing. [unit `orderParts` + component, `project.json` with a derived `files[]`
  triage, `project_ask.json`]
- CH-31 (updated for #221) The lead line: `project_ask.json` (no total) reads its `why_no_total` ("3 drawings
  answered; they may show the same rooms, so the numbers are not added up.") and neither its `refused_note` nor
  `total_note`, no `answer-value`; with `why_no_total` null it reads `total_note`; a derived total with
  `refused_note` set shows the value and no note; a derived total
  2 shows "2" in bold with test id `answer-value`, the Sure badge only when `total_sure` (CH-13 kept). [component]
- CH-32 The figure shows reference 1: `figure` named "Reference 1 of 2", the viewer gets the part's `name`, `pages`,
  `marks` and `legend`, and no credit text shows in the turn. [component, `PageViewer` spy]
- CH-33 Arrows: with 2 references "Next reference" shows reference 2 ("Reference 2 of 2"), "Next" again wraps to 1,
  "Previous reference" from 1 goes to 2; with one reference (or one with a page) no arrows. Each arrow is a `button`,
  44x44 at 390. [component; browser]
- CH-34 References list: numbered buttons in the CH-30 order with the file name and "<kind words> · <route words>";
  the current one `aria-pressed="true"`; clicking reference 2 shows it on the left. A part with empty `pages` is plain
  text with "no preview" and no button. [component]
- CH-35 Rows: "<name>: <value>", the status pill in words, "Show it on <name>" (CH-16 href) per answering part; no
  row, line or picture for a refused part; no "Credit" text anywhere in the turn. [component, `project_ask.json`]
- CH-36 Follow-ups: after an answer to "How many doors are there?", the group "Follow-up questions" shows up to 3
  questions from the drawings' suggestions, none of them the asked one; clicking one asks it; after a refusal the
  group is hidden and the refusal's chips show once; with every suggestion asked, no group. [unit `followUps` +
  component]
- CH-37 Layout: two columns at 1440 (figure left ~1.4 : 1), one column at 390 with the figure first; no sideways
  scroll; the ask bar band still clears the card (EN-71). [unit on the CSS text; browser 1440 and 390]
- CH-38 (preqa parity sweep) The chat column is the demo's 820 px (`.en-chat` `max-width: 868px` with the page's
  24 px gutters); once the thread starts the project-name `h1` stays for screen readers only (`.en-sr`, the demo shows
  no title then). [unit on the CSS text + component]
- CH-4/CH-5 amended: their "one line per drawing" is CH-35's row; the "no figure or img" part is replaced by CH-32.
  CH-11 amended: after the first ask the "Suggested questions" group is gone and "Follow-up questions" (CH-36) takes
  its place after the thread.

### API asks (for Bogdan's fleet, via frontend-orch; nothing is mocked meanwhile)

1. `ProjectAnswer.total_note` mixes why there is no total with which drawings refused ("…; 2 drawings have no reader
   for it."). Screens carry no refused-drawing lines (#204): split it, e.g. `total_note` (the total only) and
   `left_out` (the refused drawings, for the trace). Until then the note is shown as sent (it is the only reason
   given for no total).
2. Answers that combine several sheets (an elevation's storey count with a floor plan, demo #210): the API answers per
   read drawing only; set-aside elevations/sections give no part. Until there is one, no such answer, nothing mocked.
4. (after #221) With a total, `total_note` is "<what the total is over>; <refused drawings>." and `why_no_total`
   is null, so no field says what the total is over without the refused drawings: add one (e.g. `total_over`).
   Until then the screen shows the total without a note when `refused_note` is set.
3. Optional: `ProjectAnswerPart.sheet_class` (the file's triage class) so the order needs no `files[]` lookup.

### Not done here

- The demo's "described" preview answers from a set-aside picture (not in the API; Beatrice's triage owns it).
- Other renderings of a drawing as extra references (`other_renderings`): one reference per answering part.
- Beatrice's #208 (paperclip, `onAttach`, CH-17..21): untouched; AskBox's props stay.
- The credit line under the viewer: `PageViewer` renders `<Credit>` itself (also "none recorded" for null); CH-32's
  "no credit text" needs fe-viewer / fe-shared to take it off screens (rule 4, About page). This screen passes no
  credit.

## Out of scope

- Keeping the chat across reloads; suggestions; showing the plan in the chat.

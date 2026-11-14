# Project chat (spec, frontend, Vellum)
Status: draft, 2026-11-14 12:10, by fe-engineer. Source: Tudor via frontend-orch (`.agents/briefs/fe-chat.md`):
"after settling all the conflicts it should have a button that sends us straight to a whole new chat with those
documents ingested … the chat should be completely empty not have the drawings already illustrated". API:
docs/API.md `GET /api/projects/{id}`, `POST /api/ask`.

## Purpose

A whole new, empty chat about every drawing of a project. Reached from the conflicts screen's "Start a new chat"
(conflicts.md) at `#/p/<pid>/chat`. Nothing is drawn until the user asks for it: no plan, no viewer, no marks, no
suggestion buttons. Questions and answers appear as turns; an answer links to its drawing ("Show it on <file>").

## Files owned

- `frontend/src/engineer/ProjectChat.tsx`: the route view `ProjectChat({projectId})`, mounted by the shell (shared.md).
- `frontend/src/engineer/projectAsk.ts`: `askProject` (below) and `askable(project)`.
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
- `POST /api/ask` per askable drawing, in parallel, on each question: `{drawing_id, question, project_id}`
  (`project_id` always sent, so the answer's `file` is this project's name and the backend logs the ask).
  `// shortcut: fan-out per drawing, replace with the project ask when the backend has it`.

`askProject(projectId, drawings, question)` resolves to exactly the shape of Bogdan's coming
`POST /api/projects/{project_id}/ask` (#14 c6875607088, PR ~12:45, fixture `project_ask.json`), typed locally as
`ProjectAsk` until `schema.d.ts` has it: `{question, parts: [{drawing_id, name, answer}], total, total_note}`.
`parts`: one per drawing whose request succeeded, `name` = the drawing's `file` in this project, answering parts
first, refused after (each in drawing order). `total` (Bogdan's rule, #14 c6875696652, replaces the
sum): the single answering part's numeric value when exactly one drawing answers; with several answering parts null
(drawings may show the same rooms; only the backend can tell disjoint parts), and `total_note` "These drawings may show the same rooms, so the numbers are not added up."; otherwise
`total_note` null. Every request failed: rejects with the first error; no askable
drawing: rejects with "No drawing in this project can be asked yet.". Switching to the backend = replacing the fan-out
body with the one call.

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
| Answered (one or more parts) | one card: the quantity label (small), the total (`answer-value`, 44 px) when `total` is not null, `total_note`, then one line per answering part "<name>: <value>" with "Show it on <name>" linking to `#/p/<pid>/d/<drawing_id>/engineer`; no plan, no image |
| Refused by all | one refusal card: "I can't answer that from these drawings.", the first refusal's text and its `can_answer` chips (a click asks the project again) |
| Every request failed | the engineer's error turn ("The question could not be answered: <detail>", code, Try again re-asks all) |

Phone 390: one column, no sideways scroll, the ask box sticks to the bottom (engineer.md EN-71 band).

## Acceptance criteria

Component tests with `mockApi`, `project.json` (5 drawings: 4 `ready`/`flagged`… as listed there), `answer.json`,
`answer_area.json`, `answer_refused.json`.

- CH-1 Opening the route requests `GET /api/projects/<pid>` once; while pending the loading view shows; a 404 shows
  the error and "Back to the project".
- CH-2 Empty: the `h1` is the project's name, then the ask bar ("Question", "Ask"), then directly after it the group
  "Suggested questions" with "How many doors are there?", "What is the net floor area of all indoor rooms in m²?",
  "How many windows are there?" (from `drawing.json`'s suggestions); no "Ask anything about" text, no `img`/`figure`.
- CH-3 Asking sends one `POST /api/ask` per askable drawing with `{drawing_id, question, project_id}`; while
  pending "Reading N drawings…" shows and Ask is disabled.
- CH-4 One drawing answers (the rest refuse): the total "2", one line "plans/flat-a.pdf: 2" with "Show it on
  plans/flat-a.pdf" linking to that drawing's engineer route, no `figure` or `img` in the turn, no refusal text.
- CH-5 Two drawings answer (2 and 2, or a count and an area): no total, the note "These drawings may show the same rooms, so the numbers are not added up.", a line and a link each.
- CH-6 All refuse: one refusal card "I can't answer that from these drawings." with the refusal's text and its
  `can_answer` buttons; a click asks that question of every askable drawing.
- CH-7 Every request fails (500): the error turn; Try again sends the asks again.
- CH-8 A project with no askable drawing shows "No drawing in this project can be asked yet." and Ask is disabled.
- CH-9 `askProject` (unit): one request per askable drawing with `project_id`; returns the `ProjectAsk` shape with
  parts named by this project's files, answering first, failed requests left out; total only for one answering part, else null with the note;
  nothing answers: every part refused, total null; rejects with the first error when all fail.
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
- CH-15 `?ask=` empty or spaces: nothing asked, the empty start page; a project 404 or a project with no askable
  drawing: nothing asked. [component]

## Out of scope

- A project-wide ask in the backend (one request, one answer across drawings): asked of Bogdan via orch; this
  screen switches to it when it exists.
- Keeping the chat across reloads; suggestions; showing the plan in the chat.

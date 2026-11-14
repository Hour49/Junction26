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
| Answered (one or more parts) | one card: the quantity label (small), the total (`answer-value`, 44 px) in `total_unit` when `total` is not null, a "Sure" badge after it when `total_sure` (as EN-53), `total_note`, then one line per answering part "<name>: <value>" with "Show it on <name>" linking to `#/p/<pid>/d/<drawing_id>/engineer`; no plan, no image |
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

## Out of scope

- Keeping the chat across reloads; suggestions; showing the plan in the chat.

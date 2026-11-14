# UI bugs (2026-11-14, checked against main at 878eba7 + pull)

## 1. "Point at the plan" becomes a pen button in the ask bar

### What the user wants
- No more "Point at the plan" chip above the ask box. Instead a **pen icon inside the ask bar** (next to the
  paperclip in `AskBox`).
- Click the pen → **draw mode on**: the text box is disabled (you cannot type), and you draw on the plan
  (click a room or drag a rectangle). Click the pen again (or Esc) → draw mode off, typing works again, the
  drawn selections stay as chips.
- The pen works **only on plans you can draw on**. If the plan shown is not one of those, the pen is greyed out
  and clicking/hovering it shows a small popup: "You can't draw on this plan. Drawing works only on drawn plans
  (vector PDF) and building-model sheets." (exact words to agree).

### How it works today (frontend)
- `frontend/src/agent/AgentChat.tsx:424-437`: the chip "Point at the plan" toggles `pointing`; disabled only
  when there are no plans at all.
- `AgentChat.tsx:409-422`: `pointing` opens `PlanPointer` as a separate card above the bar, with its own
  "Which plan?" list and its own copy of the page viewer (`PlanPointer.tsx:41-87`, `PageViewer fixMode`).
- `AgentChat.tsx:463-474`: `AskBox` is always typeable; it only has the paperclip (`engineer/AskBox.tsx:32-90`).
- The plan list is `askable(project.drawings)` (`engineer/projectAsk.ts:7`): every ready/flagged drawing,
  **including scans and photos**. So today you can point at a photo, and nothing tells you it will not work.

### Backend: what is drawable is already decided, but not exposed
- `backend/app/adapters/plan_tools.py:134-165` (`plan_page`) refuses a page with `CannotEditError`:
  - building model with no sheet → "this building model has no drawn plan to edit"
  - `route == "raster"` (`pdf_scan`, `png_plan`, `jpeg_plan`, `photo_plan`) → "this plan is a scan/photo:
    its walls are not geometry"
  - no scale → "this drawing has no scale"
  - no room outlines on the page → "the rooms on this page have no outlines"
  - no walls as geometry → "no walls are drawn as geometry on this page"
- A selection on such a page is still accepted by `POST /api/.../chat` (`app/api/chat.py:55`); `describe()`
  (`plan_tools.py:73-98`) just says "(its size is not known)". The user draws, sends, and gets a vague answer.
- `DrawingEntry` (`app/api/views.py:143-155`) gives the frontend `kind` and `route`, but **not** whether the
  page can be drawn on, nor why not. The frontend could guess from `route !== 'raster'`, but scale / outlines /
  walls are only known on the backend.

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 1a | `AgentChat.tsx:424-437` | The pointing control is a chip outside the bar; must be a pen icon in `AskBox`. |
| 1b | `AskBox.tsx` | No draw mode: the textarea and send stay active while drawing. Needs a `drawing` prop that disables input. |
| 1c | `PlanPointer.tsx` | Opens a second viewer + "Which plan?" picker. Draw should happen on the plan already shown (`PlanPane` / `PlanSheet`), on the narrow layout too. |
| 1d | `projectAsk.ts:7` / `AgentChat.tsx:268` | Pen eligibility uses "askable", which includes scans and photos. Needs a "drawable" test. |
| 1e | backend `views.py:143` | No `drawable: bool` + `not_drawable_reason: str | null` on `DrawingEntry` (or per page). Proposed: compute from the same checks as `plan_page`, reuse its reasons. Response-model change → `npm run api:gen` + commit `schema.d.ts` in the same PR (CLAUDE.md gotcha). |
| 1f | backend `chat.py:55` | Selections on a non-drawable page are accepted silently. Either refuse with 422 and the reason, or let `describe()` say clearly "this plan cannot be drawn on: <reason>". |
| 1g | UI copy | Popup text for a non-drawable plan, using the backend reason ("this plan is a photo: its walls are not geometry"). |

### Decision needed (team)
- Interface change (`DrawingEntry.drawable` + reason): needs a decision record in `docs/decisions/` and a board
  `decision` thread before backend and frontend code against it (repo rule).
- Owners: frontend Tudor (`src/agent`, `src/engineer/AskBox.tsx`); backend owner for `views.py` / `plan_tools.py`.

### Tests to add
- Frontend: pen disabled + popup on a `photo_plan` / `pdf_scan` entry; pen on → textarea disabled; pen off →
  chips kept, typing back.
- Backend: `drawable=false` with the right reason for raster, no-scale, no-outlines; `true` for a vector sheet;
  selection on a non-drawable page gets the clear reason (1f).

## 2. Chat on the left, a file list with open/close drawings on the right; no "What I read"

### What the user wants
- Opening the chat: chat on the **left**, drawings on the **right**, from the first screen (empty chat too).
- The right side is a **list of the project's files** (by name). Click a name → its image opens **under that
  name** (accordion). Click the same name again → it closes.
- Remove the **"What I read"** section from the chat.

### How it works today (frontend)
- `frontend/src/agent/AgentChat.tsx:300-337`: the right pane (`PlanPane`) shows **one** drawing at a time;
  default `plans[0]`. Only beside the chat at `(min-width: 1200px)` (`AgentChat.tsx:68`); narrower it is a
  full-screen sheet opened with "Show the plan" (`AgentChat.tsx:438-448`, `PlanSheet` in `PlanPane.tsx:135`).
- `PlanPane.tsx:79-95`: the files are a row of chips above **one** viewer; a chip swaps the drawing. No way to
  close a drawing, no list, the image is not under its name.
- `AgentChat.tsx:482`: `<WhatIRead project={project} />` on the empty chat (`WhatIRead.tsx`, max 3 drawings,
  with takeoff line and reason). Styles in `agent.css` (`.ag-read*`), tests in `WhatIRead.test.tsx` and
  `AgentChat.test.tsx`.

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 2a | `PlanPane.tsx:79-114` | Chip row + one viewer → needs a vertical list of file names, each expandable to its image under it, click again to collapse. |
| 2b | `AgentChat.tsx:300` | One `paneId` state → needs a set of open drawing ids. Decide: default all closed, or the first open? (proposal: first open). |
| 2c | `AgentChat.tsx:287-298` `showSource` | "[n]" / "Show it" must open (expand) that file in the list and scroll to it, with its marks, instead of swapping the one viewer. |
| 2d | `AgentChat.tsx:300-312` | The 3D model button and "Open in workspace" are per pane head → move to each list row. |
| 2e | `drawn` loading | Today drawings load for the pane; with several open, load each on expand only (memory, many PDFs). |
| 2f | `AgentChat.tsx:68` / `PlanSheet` | Under 1200 px there is no right side. Decide: keep the sheet (with the list inside) or a narrower split. |
| 2g | `AgentChat.tsx:482`, `WhatIRead.tsx`, `agent.css .ag-read*` | Remove the "What I read" section shown under the project (zip) name title (`AgentChat.tsx:481` `<h1>{project.name}</h1>`, then `:482`); the title stays. Remove its tests (`WhatIRead.test.tsx`, cases in `AgentChat.test.tsx`). Its `readLine` (rooms/doors/windows) could become a small line under each file name in the new list, if wanted. |
| 2h | list content | Which files: today `askable(project.drawings)` (ready/flagged drawings). Decide if unread/skipped files appear (greyed, no image). |
| 2i | link to bug 1 | The pen (bug 1) draws on an **open** file in this list; with several open, the drawing goes to the one you draw on. |

### Backend
- No change needed: `ProjectView.drawings` (`name`, `kind`, `state`) and `GET /api/drawings/{id}` already give
  the list and each image.

### Tests to add
- Right side shows the list on the empty chat (wide layout); clicking a name shows its viewer under it; second
  click hides it; two can be open.
- "Show it" on an answer opens the right file with marks.
- "What I read" is gone.

## 3. Hover explanations (tooltips) across the whole app, for first-time users

### What the user wants
- The hover explanation in the surveyor's conflict card ("Settled by rule" → dark rounded box: "A rule settled
  this: the printed label over the outline at the sheet's scale. Modify it if you disagree.") is the model.
- The same kind of short explanation on **every** control, label, status or number a first-time user may not
  understand, in **the same style**.

### The reference style (today)
- Markup: `frontend/src/surveyor/ConflictCard.tsx:237-242`: the trigger is focusable (`tabIndex={0}`) and
  linked with `aria-describedby`; the text is `<span role="tooltip" className="cf-tip">`.
- CSS: `frontend/src/surveyor/conflicts.css:153-169`: dark box (`background: var(--v-text)`, text
  `var(--v-surface)`), `border-radius: 12px`, `padding: 8px 12px`, `font-size: 12px`, width 240px, 6px under the
  trigger; shown on `:hover` and `:focus`.
- A second, separate copy exists: `StatusPill` in `frontend/src/engineer/AnswerCard.tsx:122-148`
  (`.en-tip`, JS state). Two tooltip styles already → step 1 below.

### How to do it: a separate agent sweeps the app
This is a whole-app review, so it is a **separate agent's task** (one worker, read-only first), not part of the
bug 1/2 work. Brief for it:
1. **Inventory**: walk every screen (home/upload, project, ingest progress + trace, engineer chat + answer
   cards, agent chat, plan pane / viewer, surveyor takeoff + conflicts, checks, documents, double-check,
   3D model, export, account, about, advanced) in the running app (`npm run dev`, sample project) and in
   `frontend/src/**`.
2. **Find what a first-time user would not understand**: jargon and status words (route, flagged, vector/scan,
   takeoff, settled, conflict, rule pack, double-check…), icon-only buttons, numbers without a "where from",
   disabled buttons without a reason, abbreviations, empty states.
3. **Write the list** to `docs/ui-tooltips.md`: one row per place: screen, `file:line`, the element, proposed
   tooltip text (≤ 2 short sentences, plain English, says what it is and what to do), priority (P1 = blocks a
   first-time user on the golden demo path in `docs/QA.md`; P2 = helpful; P3 = nice). No code changes in this step.
4. Review the list with the team (Tudor owns the frontend), then implement.

### Implementation rules (after the list is approved)
| # | Problem / rule |
|---|---|
| 3a | One shared tooltip component (e.g. `src/shell/Tip.tsx` + one CSS class) with the `.cf-tip` look; replace `.cf-tip` and `.en-tip` with it. Hover **and** keyboard focus, `role="tooltip"`, `aria-describedby`, Escape closes. |
| 3b | It must not be cut off at screen edges (`.cf-tip` is `right: 0` only) and must work on touch (tap to show). |
| 3c | Texts live in one place (e.g. `shell/strings.ts`) so wording stays consistent; `shell/noHtml.test.ts`-style check for plain words. |
| 3d | Disabled buttons get a tooltip with the reason (links to bug 1: the pen's "you can't draw on this plan"). |
| 3e | Tests: the component (hover, focus, Escape), and one test per P1 place that the tip text is present. |
| 3f | Don't over-do it: no tooltip on self-explaining text; at most one per element. |

### Backend
- None for the UI. Where a tip should show the backend's own reason (flags, "not read" reasons, pen), use the
  reason fields the API already returns.

## 4. Multi-drawing answer card: no left/right arrows on the image; References under the image

### What the user wants
- In a chat answer that covers several drawings ("6 drawings answered; they may show the same rooms…"):
  - **Delete the ‹ › arrows** drawn over the plan image.
  - Move the **References** list (1 Drawn plan 1, 2 Drawn plan 2, … 6 Building model 1, "View in 3D") from the
    right column to **under the plan image**, in the left column. Clicking a reference still switches the image.

### Where (frontend only)
- Component: `frontend/src/engineer/ChatAnswer.tsx` (used by the engineer chat `ProjectChat.tsx:144` and the
  agent chat `agent/TurnCard.tsx:222`, so the change shows in both).
- Arrows: `ChatAnswer.tsx:109-134`, the `overlay` passed to `Plan` (`en-nav--prev` / `en-nav--next`, "Previous /
  Next reference"), and `step()` at `ChatAnswer.tsx:43`, which only they use.
- Layout: the card is `.en-chatcard` with the figure `.en-chatfig` (left) and `.en-side` (right) holding the
  per-drawing list `.en-parts` **and** the references `.en-crefsbox` (`ChatAnswer.tsx:138-224`). CSS in
  `engineer/engineer.css:690-740` (+ narrow layout at `:875`).

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 4a | `ChatAnswer.tsx:109-134` | Remove the arrow overlay and the now-unused `step` (`:43`) and `Chevron` if unused. The reference list becomes the only way to switch the image (it already is a button per reference, `aria-pressed`). |
| 4b | `ChatAnswer.tsx:173-224` | Move `.en-crefsbox` out of `.en-side` into the `<figure>` column, right after `<Plan>`. If there is no image (`current` null), keep the list in the left column anyway. |
| 4c | `engineer.css:690-740, 875` | Left column: image then References, stacked. Right column only the per-drawing values (`.en-parts`). Check the narrow layout (`:875`) still stacks image → references → values. |
| 4d | Keyboard | Today ←/→ may only work via the arrow buttons; after removal, the reference buttons must stay tabbable. Optional: arrow keys on the reference list. |
| 4e | Tests | Update tests that click "Previous/Next reference" (only `engineer/ChatAnswer.test.tsx` uses them; checked by grep): they must switch via the reference buttons. Add: no "Next reference" button rendered; "References" is inside the figure column. |

### Backend
- None.

## 5. "View in 3D" becomes a small round "3D" button on the image's top-right corner

### What the user wants
- No big "View in 3D" button. A **small round button with "3D" on it, in the top-right corner of the image**.

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 5a | `ChatAnswer.tsx:208-219` (`.m3-open3d`), `agent/PlanPane.tsx:61-72` | "View in 3D" becomes a **small round button with "3D" on it, in the top-right corner of the image** (overlay on `<Plan>`, like the old arrows were placed). `aria-label="View in 3D: <name>"` and a tooltip in the bug 3 style. Same button in the plan pane (bug 2, per open file). |
| 5b | which model | Today the 3D button sits on the reference that has a model, often a **Building model with no preview** (never the shown image). Decide: the corner button opens the model of the shown drawing if it has one, else the answer's building model (proposal), and is hidden when the answer has no model. |
| 5c | `model3d/model3d.css`, `engineer.css` | Style: round (~32px), the same dark/light look as the app's chips, visible on light and dark plans; does not cover the viewer's own controls. |
| 5d | Tests | Button named "View in 3D: <name>" is in the image corner and opens `ModelDialog`; no "View in 3D" text button left (`ChatModel.test.tsx`, `PlanModel.test.tsx` in `model3d/`). |

### Backend
- None.

## 6. Right column of the answer card shows only the card of the drawing in the image

### What the user wants
- In the multi-drawing answer card, the right column today lists a value card for **every** drawing
  (Drawn plan 1, Drawn plan 2, Plan image 1, …). Show **only the card of the drawing whose image is shown**.
  Picking another reference (bug 4) swaps the image and the card together.

### Where (frontend only)
- `frontend/src/engineer/ChatAnswer.tsx:138-171`: `<ul className="en-parts">` maps over all `parts`. The shown
  image is `current = drawn[at]` (state `at`, set by the reference buttons).

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 6a | `ChatAnswer.tsx:138-171` | Render only the part with `drawing_id === current.drawing_id` (value, pill, "Show it on…", estimate, why, resolver lines). |
| 6b | drawings with no image | Parts with no preview (e.g. Building model 1, `k < 0` at `:178`) can never be "current", so their value would vanish. Decide: clicking such a reference shows its card with a "no preview" placeholder in the image spot (proposal), so every answer stays reachable. |
| 6c | the total | The top line ("6 drawings answered; …" / the total) stays above the card: it is about all drawings. |
| 6d | Tests | `ChatAnswer.test.tsx`: only one "Per drawing" item rendered; switching reference changes it; a no-preview drawing's value still reachable. |

### Backend
- None.

## 7. Confidence explanations hidden by default, shown on click

### What the user wants
- The confidence sentence ("High confidence: on our reference drawings of this kind, 794 of 794 answers were
  exact.") is printed in full under every value today. Hide it; the user clicks to show it (and clicks again to
  hide). The confidence pill ("High confidence") stays visible.

### Where
- Text comes from the backend: `backend/app/core/review/check.py:481` (`level.text`). No backend change.
- Shown always in:
  - `frontend/src/engineer/ChatAnswer.tsx:61` + `:169`: `why(p)` = `check.reason ?? level.text`, a
    `<p className="en-why">` under each drawing's value (the case in the screenshot).
  - `frontend/src/engineer/AnswerCard.tsx:391`: `<p className="en-small">{a.level?.text}</p>` under the
    Confidence bar.
- Already only on hover (native `title`, not the bug 3 style): `ChatAnswer.tsx:14` `LevelPill`,
  `AnswerCard.tsx:382`, `agent/TurnCard.tsx:56`.

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 7a | `ChatAnswer.tsx:169`, `AnswerCard.tsx:391` | Replace the always-shown sentence with a disclosure: a small "Why?" / "How sure?" toggle (or the pill itself as the button), `aria-expanded`, text revealed under it. Closed by default. |
| 7b | `ChatAnswer.tsx:61` | `why()` mixes two things: `check.reason` (why a value was refused or flagged: must stay **visible**, the user needs it) and `level.text` (confidence statistic: goes behind the toggle). Split them. |
| 7c | consistency | Use one shared disclosure component for all confidence texts; the pills' native `title` tooltips move to the bug 3 tooltip. |
| 7d | Tests | Sentence not visible by default; visible after click; hidden after second click; a refusal reason (`check.reason`) still visible without click. |

### Backend
- None.

## 8. Delete the "Show it on <drawing>" link

### What the user wants
- Remove the "Show it on Drawn plan 1" link from each drawing's card in the answer.

### Where
- `frontend/src/engineer/ChatAnswer.tsx:155-167`: `<a className="en-show" href={routeHref(workspace …)}>`.
- CSS: `frontend/src/engineer/engineer.css:723` (`.en-show`, "CH-39").
- Tests that expect it: `engineer/ChatAnswer.test.tsx:152-207`, `engineer/ProjectChat.test.tsx:200`,
  `engineer/engineer.css.test.ts:93`, `e2e/golden-path.spec.ts:204-217` (GP-32 / GP-51 / V6).

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 8a | `ChatAnswer.tsx:155-167` | Delete the link (and `query` / `routeHref` if left unused). |
| 8b | `engineer.css:723` | Delete `.en-show` if nothing else uses it. |
| 8c | lost path | The link was the only way from a chat answer to the full **workspace** for that drawing (golden path step GP-32/GP-51 in `docs/QA.md`). Decide: drop that step, or keep a way in (e.g. "Open in workspace" in the plan pane, `agent/PlanPane.tsx:55`, already exists). Update `docs/QA.md` and the spec (CH-35/CH-39 in `docs/specs/frontend/`) to match. |
| 8d | Tests | Update the tests above: remove the link checks, rewrite the e2e step to reach the workspace the new way (or drop it with 8c), add one test that no "Show it on" link is rendered. |

### Backend
- None.

## 9. Make the right-hand drawing card ("Drawn plan 1: …") smaller

### What the user wants
- The per-drawing card on the right of the answer (name, value, confidence pill) takes too much room. Make it
  smaller so the image gets the space.

### Where (frontend only)
- Grid: `frontend/src/engineer/engineer.css:693-697`: `.en-chatcard` columns `1.4fr / 1fr` (the right column
  is ~42% of the card).
- Right column: `.en-side` `engineer.css:94-99` (padding 20px 22px, gap 16px).
- Card rows: `.en-parts` / `.en-parts li` `engineer.css:793-814` (font 15px, `flex: 1 1 200px` on the name).
- Narrow layout: `engineer.css:875`.

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 9a | `engineer.css:695` | Narrow the right column, e.g. `minmax(0, 2fr) minmax(220px, 1fr)` or a fixed ~260px; image column grows. |
| 9b | `engineer.css:94-99, 793-814` | Tighter card: smaller padding/gap, value 14px, name 13px muted, pill on its own line if needed. |
| 9c | with bugs 4, 6, 7, 8 | After those, the right column holds just one drawing's value + pill (+ "Why?" toggle). Size it for that content; do this after 4/6/7/8 land. |
| 9d | Tests | `engineer.css.test.ts` checks for the new column width; screenshot check in `npm run e2e` (`frontend/screenshots/`) at 1280 and 390 px. |

### Backend
- None.

## 10. Delete the "Workspaces" button in the header

### What the user wants
- Remove the "Workspaces" pill from the top bar.
- Assumption (to confirm): this is the header pill, not "Open in workspace" in the plan pane
  (`agent/PlanPane.tsx:55`). If it is the plan-pane link, note that bug 8c proposes it as the remaining way
  into the workspace.

### Where (frontend only)
- `frontend/src/shell/Header.tsx:89-95`: `<a className="header-pill workspaces-link" href="#/workspaces">Workspaces</a>`.
- The page it opens: `#/workspaces` → `account` route (`shell/route.ts:35, 62`), `account/AccountScreen.tsx`
  ("Your workspaces": every project on the server, stats and history).
- Other links to that page: `ingest/HomeScreen.tsx:11` ("Earlier uploads are in Workspaces").
- Style note: `export/export.css:1` (Export is styled as a sibling of this pill).
- Tests: `App.test.tsx`, `shell/views.test.tsx`, `ingest/HomeScreen.test.tsx`, `ingest/ProjectScreen.test.tsx`,
  `surveyor/SurveyorScreen.test.tsx`, `export/ExportButton.test.tsx`, `e2e/account.spec.ts`.

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 10a | `Header.tsx:89-95` | Delete the pill. Check the Export pill and header layout still line up (`export.css`). |
| 10b | lost path | Without it, the only way to earlier projects is the home page's "Earlier uploads are in Workspaces" link. Decide: keep the Workspaces page reachable from home only (proposal), or remove the page too (then delete the route, `AccountScreen`, its tests and `e2e/account.spec.ts`). |
| 10c | wording | If the page stays, the home link still says "Workspaces": keep or rename. |
| 10d | Tests | Remove header-pill checks from the tests above; add one test that the header has no "Workspaces" link. |

### Backend
- None.

## 11. Delete the project dropdown in the header (redundant)

### What the user wants
- Remove the header's project dropdown ("sample-project.zip ▾" → "Choose a project" with every upload and
  its time). It duplicates the Workspaces page.

### Where (frontend only)
- `frontend/src/shell/Header.tsx:78-87`: `<ProjectPicker projectId=… pack=… />`.
- `frontend/src/shell/ProjectPicker.tsx` (whole file: `GET /api/projects`, `<select aria-label="Project">`,
  keeps the rule pack when switching).
- Tests: `src/App.test.tsx`, `e2e/checks-issues.spec.ts` (select the project via the dropdown).

### Problems to fix
| # | Where | Problem |
|---|---|---|
| 11a | `Header.tsx:78-87`, `ProjectPicker.tsx` | Delete the picker and the file; check header layout (country picker, Export) still lines up. |
| 11b | **with bug 10** | Bug 10 removes the Workspaces pill, this removes the dropdown: the header would have **no way to change project**. Only the home page link "Earlier uploads are in Workspaces" (`ingest/HomeScreen.tsx:11`) is left, and only from home. Decide one way in (proposal: keep the Workspaces pill, i.e. drop or change bug 10, since the dropdown is the redundant one; or make the logo/home link the way back). |
| 11c | project name | The dropdown was also where the current project's name showed in the header. The chat keeps it as the page title (`agent/AgentChat.tsx:481`); check the other screens (surveyor, checks, documents) still show which project is open. |
| 11d | Tests | Rewrite `App.test.tsx` and `e2e/checks-issues.spec.ts` steps that pick a project in the dropdown to open it by URL or via Workspaces; add one test that the header has no "Project" select. |

### Backend
- None (`GET /api/projects` stays: the Workspaces page uses it).

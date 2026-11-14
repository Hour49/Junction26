# UI tooltips: inventory (bug 3, step 1)

Read-only sweep of `frontend/src/**` on branch `fe/ui-bugs` (2026-11-15). No code changed. Paths are relative to
`frontend/src/`; line numbers were read after the shadcn migration (#400) and move when the file is edited.
Skipped on purpose (other workers are changing them): the answer card's arrows / References / 3D / Show-it /
confidence text, the header Workspaces pill and project dropdown, "Point at the plan", "What I read".

Priority: **P1** = blocks a first-time user on the golden path in `docs/QA.md` §1 (home, sample, file trace, engineer,
ask, refusal, surveyor); **P2** = helpful; **P3** = nice to have. Tip text is at most two short sentences.

## Tips that exist today

| Where | How | Note |
| --- | --- | --- |
| `surveyor/ConflictCard.tsx:237-242` pill + `surveyor/conflicts.css:153-169` | `.cf-tip`, CSS only, `:hover`/`:focus` on `.cf-pill` (`tabIndex=0`, `aria-describedby`) | The model look: dark box, 12px, 240px, radius 12. Anchored `right: 0` only, so it can be cut off at the left edge; no touch support. |
| `engineer/AnswerCard.tsx:122-148` `StatusPill` + `engineer/engineer.css:313-327` | `.en-tip`, React state on hover/focus, text from `engineer/format.ts:31-44` (`statusTip`) | Second copy of the same idea. |
| `title=` on plain elements | `agent/TurnCard.tsx:56`, `engineer/ChatAnswer.tsx:15`, `engineer/AnswerCard.tsx:325,393` (level text), `surveyor/ConflictCard.tsx:313`, `surveyor/TakeoffTable.tsx:48`, `engineer/Resolver.tsx:12`, `documents/IssueCard.tsx:303` (resolver model), `ingest/FileTraceScreen.tsx:81` (sha256), `engineer/AskBox.tsx:88`, `export/ExportButton.tsx:81`, `model3d/ModelView.tsx:99`, `engineer/DrawingHeader.tsx:38` / `agent/AgentChat.tsx:508` / `agent/TurnCard.tsx:239` (suggested question), `agent/multi/ServiceTabs.tsx:97,111`, `advanced/visuals.tsx:276` | Native browser tooltips: slow, unstyled, never on touch or keyboard focus. These are the first to move to the shared tip. |
| `ingest/IngestFinished.tsx:101-111` | Visible reason text under the disabled "Start a new chat" (`aria-describedby`) | Good pattern; keep it visible, do not hide it in a tip. |

## Proposed way to build it

Use `components/ui/tooltip.tsx` (Radix: hover, keyboard focus, Escape, collision-aware so it flips away from screen
edges, tap on touch with `open`/`onOpenChange` if needed). One wrapper `shell/Tip.tsx`:
`<Tip text={tips.x}>{trigger}</Tip>`, which wraps the trigger in `TooltipTrigger asChild` and sets the look with
class names on `TooltipContent`:

- `w-60 max-w-[240px] rounded-xl bg-foreground px-3 py-2 text-xs text-background` (dark box, 12px, 240px, radius 12px,
  the "Settled by rule" look). Drop the arrow, or keep the default one; `sideOffset={6}`.
- Mount one `TooltipProvider` (delay 150ms, so tips don't flash while moving the mouse) at the app root.
- Texts in one file (`shell/tips.ts`), as bug 3c asks.
- Non-focusable triggers (pills, labels, numbers) get `tabIndex={0}` inside `Tip`. Disabled buttons do not fire
  hover events: wrap them in a `<span tabIndex={0}>` so the "why disabled" tip still shows (bug 3d).
- Icon-only buttons already have `aria-label`; `Tip` shows the same words, so do not add a second label.
- Then delete `.cf-tip`, `.en-tip` and the state in `StatusPill`, and replace the `title=` rows above.
- Radix tooltips are not shown on touch by default; on phones use a tap-to-toggle `Popover` (`components/ui/popover.tsx`)
  with the same classes for the P1 rows.

## Constraints for the implementation step (Tudor's decision, board #404)

- Build every tip from the shadcn components in `components/ui/` (`Tooltip`, `Popover`, `Button`, `Badge`), with
  Tailwind classes only. No new hand-written CSS; the old `.cf-tip` / `.en-tip` rules go away with their users.
- `agent/` and `engineer/` rows can be done in the fe/ui-bugs PR. Rows in `surveyor/`, `checks/`, `doublecheck/`,
  `viewer/`, `model3d/`, `ingest/` and `account/` are being converted by Tudor's workers: do not edit those
  directories. Hand those rows to them, or add them after their conversion lands. The shared `shell/Tip.tsx` and
  `shell/tips.ts` are outside those directories.
- `canDraw()` stays one function (it will switch to `drawable` / `not_drawable_reason` on `DrawingEntry` once
  Bogdan's schema change lands); a "can't draw on this plan" tip should read its reason from there.

## The list

### Home / upload

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Home | `ingest/UploadBox.tsx:160-169` | "Try the sample project" | A small made-up flat with 11 files. Click it to see Vellum work end to end. | P1 |
| Home | `ingest/UploadBox.tsx:171` | "The sample starts from scratch each time." (plain text) | (no tip: already clear) | n/a |
| Home | `ingest/UploadBox.tsx:205-211` | Format chips ("IFC models", "DXF", "PDF, drawn or scanned", "SVG") | IFC and DXF are CAD/BIM files; drawn PDFs are read exactly, scanned PDFs and photos are read by AI. | P2 |
| Home | `ingest/UploadBox.tsx:139-148,160-169` | Disabled buttons while an upload runs | Wait for the current upload to finish. | P3 |
| Header | `shell/InfoBar.tsx:33-37` | Badge "Running offline: no API keys, no models" | No AI key is set, so Vellum uses built-in readers only. Scans and photos may stay unread. | P1 |
| Header | `shell/InfoBar.tsx:38-40` | "What runs" | Which reader handles each kind of file right now. | P2 |

### Header (project pages)

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Header | `shell/Header.tsx:27` | Tab "Ingest" | The project's files and how each was read. | P2 |
| Header | `shell/Header.tsx:28` | Tab "Chat" | Ask questions across all drawings of the project. | P2 |
| Header | `shell/Header.tsx:29,68-72` | Tab "Documents" and its number badge | Every file and drawing, and the issues that need your answer. The number is how many issues are waiting. | P1 |
| Header | `shell/CountryPicker.tsx:88-93` | Country pill ("No checks" / country) | Picks the building rules the project is pre-checked against. It is a pre-check, not a certificate. | P1 |
| Header | `export/ExportButton.tsx:78-95` | "Export" (icon only under 720px) | Download everything Vellum read as one CSV file. | P2 |

### Ingest progress (project screen)

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Project | `ingest/ProjectScreen.tsx:151-157` | "Simple / Advanced" switch | Simple shows progress and results. Advanced shows every step and the log. | P2 |
| Project | `ingest/ProgressCard.tsx:56-63` | Percent ring | Share of files that have finished every step. | P3 |
| Project | `ingest/ProgressCard.tsx:68` | "Elapsed" | Time since the upload was received. | P3 |
| Project | `ingest/ProgressCard.tsx:72-74` | "Files through" | Files that finished reading, out of all files found. | P2 |
| Project | `ingest/ProgressCard.tsx:76-78` | "Drawings ready" | Drawings you can ask questions about. A file can hold one or more drawings. | P1 |
| Project | `ingest/ProgressCard.tsx:80-83` | "Set aside" | Files Vellum skipped because they are not drawings, such as photos of people or spreadsheets. Open Documents to see why. | P1 |
| Project | `ingest/ProgressCard.tsx:97` + `ingest/ingest.ts:101-141` | Step names: Unpack, Identify, Route, Normalise, Extract, Second count, Takeoff, Store, Index | Each step name explains itself with its `hint` (already in the data). Show it on hover, not only while that step is running. | P2 |
| Project | `ingest/ProgressCard.tsx:94` | Step icons ✓ ◌ ○ | Done, working, waiting. | P3 |
| Project | `ingest/ingest.ts:72-75` + `ingest/ProjectScreen.tsx:46` and `documents/DocumentLists.tsx:102` (StateBadge) | File state words "ready", "flagged", "text only", "set aside" | ready: read and usable. flagged: read, but two methods disagree or something looks off; check it. text only: only its text was read, nothing measured. set aside: not a drawing, skipped. | P1 |
| Project | `ingest/IngestFinished.tsx:101-111` | Disabled "Start a new chat" | Already explained in text under it. Keep the text; add the count of conflicts left. | P2 |
| Project | `ingest/IngestFinished.tsx:119-124` | "Open the workspace" | Opens the first drawing with its plan and a question box. | P2 |
| Project | `ingest/IngestFinished.tsx:31` | "Conflicts are below." | A conflict means two methods measured the same thing and got different numbers. | P2 |

### File trace and triage

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Trace | `ingest/FileTraceScreen.tsx:75` | "reused: read before, not recomputed" | This exact file was read before, so Vellum reused the result. | P2 |
| Trace | `ingest/FileTraceScreen.tsx:77-82` | Facts list (sha256 etc.; `title` only on sha256) | sha256: a fingerprint of the file. Same file, same fingerprint. | P3 |
| Trace | `ingest/FileTraceScreen.tsx:110` | "How it was read: N stages" | The steps this file went through, with time and what each did. | P1 |
| Trace | `ingest/FileTraceScreen.tsx:121` + `ingest/ingest.ts:21-33` | Stage names: Hash, Identify, Group, Route, Cache, Normalise, Extract, Second count, Takeoff, Store | One short line each. Route: which reader fits this file. Normalise: straighten the page and fix the scale. Second count: measure the same quantities a second way. Takeoff: add up the quantities. Store: save the drawing model. | P1 |
| Trace | `ingest/FileTraceScreen.tsx:130` | "Cost: $x" | What the AI readers charged for this stage. | P3 |
| Trace | `ingest/FileTraceScreen.tsx:140` | "What it ends as: N quantities" | The measured counts and areas that came out of this file. | P2 |
| Trace | `ingest/FileTraceScreen.tsx:68-72` | "Open the drawing" | Opens the plan with a question box. | P2 |
| Triage | `ingest/TriageCard.tsx:57,112` | "Chance of a floor plan 87% (method)" | How sure the first check is that this file is a floor plan. The method says how it guessed. | P2 |
| Triage | `ingest/TriageCard.tsx:165` | "Your call" | Say whether this file belongs to the project. Your answer replaces the guess. | P2 |
| Triage | `ingest/TriageCard.tsx:184-210` | "It is related / It is not related / Read it as a floor plan" | Disabled until you type your name (reason: it is recorded with your call). | P2 |
| Triage | `ingest/TriageCard.tsx:160` | "Undo the call" | Goes back to the automatic decision. | P3 |

### Engineer page and chat

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Engineer | `engineer/EngineerPage.tsx:172` + `engineer/DrawingHeader.tsx:10-17` | "How it was read" line | How this drawing was read: exact CAD/vector, or AI vision for scans and photos. Click for the details. | P1 |
| Engineer | `engineer/DrawingHeader.tsx:33-44` | Suggested question chips | Questions Vellum knows it can answer for this drawing. Click one to ask it. | P1 |
| Engineer | `engineer/DrawingHeader.tsx:62-66` | "No ready questions" / "no reader for this kind of sheet" | Vellum has no reader for this kind of sheet in this setup, so nothing was counted. | P2 |
| Engineer | `engineer/AskBox.tsx:63` | Question input | Ask about counts, areas or where something is. Vellum answers from the drawing only. | P2 |
| Engineer | `engineer/AskBox.tsx:85-90` | Photo button (icon) | Add a photo of a plan (png or jpeg) to ask about it. | P2 |
| Engineer | `engineer/AskBox.tsx:108` | Send button (icon, `aria-label="Ask"`), disabled when empty/too long | Disabled: type a question first. | P1 |
| Engineer | `engineer/AskBox.tsx:105-106` | "N asked · 12 / 200" | Questions asked here and characters used. | P3 |
| Engineer | `engineer/Plan.tsx:75,83,124,129` | Previous / next drawing arrows (icon only) | Go to the previous or next drawing of this project. | P2 |
| Plan | `viewer/PageViewer.tsx:460,474` | Page arrows | Previous or next page of this sheet. Disabled on the first or last page. | P2 |
| Plan | `viewer/PageViewer.tsx:487,498,512` | Zoom out, Zoom in, Fit | Disabled at the smallest or largest zoom. Fit shows the whole sheet. | P3 |
| Plan | `viewer/PageViewer.tsx:469` | "Page 1 of 2 · N marks" | Marks are the doors, rooms and other things Vellum found on this page. | P2 |
| Plan | `viewer/PageViewer.tsx:801` | Numbered mark on the plan | One thing Vellum counted. The number matches the list of marks. | P1 |
| Plan | `viewer/PageViewer.tsx:519-520` | "Click or drag where a mark is missing" | Adds a mark Vellum missed. Only while you are fixing a count. | P2 |
| Plan | `viewer/SourceFigure.tsx:265,277,315` | Previous / next source, Minimize / Expand the drawing | Move between sources, or shrink the picture. | P3 |
| Engineer | `engineer/ModelProof.tsx:18-24` | "Model objects" table: Class, Storey, GlobalId | Class: the kind of object (wall, door). Storey: the floor. GlobalId: the object's unique id in the IFC model. | P2 |
| Engineer | `engineer/ModelProof.tsx:43-48` | "Objects per storey" | How many objects of each class sit on each floor. | P3 |

### Answer card details (not the ignored parts)

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Answer | `engineer/AnswerCard.tsx:122-148` | Status pill (signed / agree / conflict / estimate / edited / one method) | Use the existing `statusTip` texts via the shared Tip. | P1 |
| Answer | `engineer/AnswerCard.tsx:325` | "Partial" pill (`title`) | Only part of the project was read, so this answer may be incomplete. | P2 |
| Answer | `engineer/AnswerCard.tsx:410` | "This drawing was flagged" box | Vellum read this drawing but something looks off. Check the answer against the plan. | P1 |
| Answer | `engineer/AnswerCard.tsx:494,501-503` | "Checks" label and "Second reader's score 0.91 (not a probability)" | Checks: how the number was verified. Score: how much a second, independent reader agrees; higher is better. | P1 |
| Answer | `engineer/AnswerCard.tsx:506-508` | "Counting rule: ... door_count" | The written rule Vellum used to count. The small id is for engineers. | P2 |
| Answer | `engineer/ChecksPanel.tsx:14,33,36` | "by room outlines × sheet scale", "Second method ... agrees", "Estimated by one method" | A method is one way of measuring. Two methods agreeing is stronger than one. | P2 |
| Answer | `engineer/ChatAnswer.tsx:151` | "Signed off" pill | A surveyor checked this value and signed it. | P2 |
| Chat | `agent/AgentChat.tsx:502-520` | Follow-up question chips | Suggested next questions. | P3 |
| Chat | `agent/TurnCard.tsx:56` | Confidence pill (title) | (belongs to the ignored confidence text) | n/a |

### Agent chat and plan pane

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Agent chat | `agent/AgentChat.tsx:448` | "Show the plan" (narrow screens) | Opens the plan the answer is about. | P3 |
| Agent chat | `agent/AgentChat.tsx:456` | Remove chip (icon) | Stop pointing at this plan. | P3 |
| Agent chat | `agent/AgentChat.tsx:432` | Disabled "Point at the plan" | (ignored: owned by another worker) | n/a |
| Plan pane | `agent/PlanPane.tsx:59,71,76` | "Open in workspace", "View in 3D", "Close" | Open the drawing in its own page / see it as a 3D model / close the plan. | P3 |
| Agent | `agent/EditCard.tsx:207`, `agent/services_change/ServicesChangePlan.tsx:76` | Plan toggle ("Before / After", storeys) | Switch between the current plan and the proposed change. | P2 |
| Agent | `agent/multi/ServiceTabs.tsx:97,111,248` | Discipline tabs, "Proposed place" | One tab per discipline (e.g. electrical, water). A proposed place is where Vellum suggests the change; it is a suggestion, not a design. | P2 |
| Agent | `agent/LawSection.tsx:173-234` | "Building rules", "The AI also found in the law" | Rules checked from the chosen country's building code. The second list is extra clauses the AI found; check them yourself. | P2 |

### Surveyor and conflicts

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Surveyor | `surveyor/ConflictCard.tsx:236-243` | Pill ("Settled by rule" etc.) | (existing tip; move to shared Tip) | P1 |
| Surveyor | `surveyor/ConflictCard.tsx:229` | "Conflict 1 of 2 · decided by rule" | Two methods gave different numbers. A rule or a person picks the one to use. | P1 |
| Surveyor | `surveyor/ConflictCard.tsx:277-287` | Choice buttons (disabled when busy, signed, or not choosing) | Disabled: someone signed this off, or it is saving. Undo the sign-off to change it. | P1 |
| Surveyor | `surveyor/ConflictCard.tsx:313` | "Picked by {who}" (title=model) | Which reader picked it. Hover shows the model name. | P3 |
| Surveyor | `surveyor/ProjectReviewSide.tsx:97,124,130` | "Drawings (5)", "Conflicts (2)", "Settle the conflicts" | Counts of drawings and unresolved disagreements in this project. | P2 |
| Takeoff | `surveyor/SurveyorScreen.tsx:226` | "Takeoff: {drawing}" | A takeoff is the list of everything counted or measured on this drawing. | P1 |
| Takeoff | `surveyor/TakeoffTable.tsx:69-71` | Columns "Quantity / Value / State" | Value: the number used. State: whether it was checked, in conflict, or signed off. | P1 |
| Takeoff | `surveyor/TakeoffTable.tsx:78,91` | "To review" / "All other quantities" | To review: values that need a person. All other: already agreed. | P2 |
| Takeoff | `surveyor/TakeoffTable.tsx:48` | "Picked by rule/model" | (see ConflictCard row) | P3 |
| Takeoff | `surveyor/TakeoffTable.tsx:38-41` | Struck-through old value | The value before a review edit. | P3 |
| Takeoff | `surveyor/SurveyorScreen.tsx:195` | "Show rows with value 0" | Also list things Vellum looked for and found none of. | P3 |
| Takeoff | `surveyor/SurveyorScreen.tsx:243` | "Export CSV" | Download this drawing's quantities as a spreadsheet file. | P3 |
| Takeoff | `surveyor/SurveyorScreen.tsx:249-255` | "Reset all edits" (danger) | Undo every edit and sign-off on this drawing. Asks you to confirm. | P2 |
| Takeoff | `surveyor/SurveyorScreen.tsx:259` | "N of M quantities signed off" + bar | Signed off = a person checked it and accepted the value. | P2 |
| Detail | `surveyor/QuantityDetail.tsx:61` | "First method / Second method" | Two independent ways of measuring the same thing. | P1 |
| Detail | `surveyor/QuantityDetail.tsx:70-71` | "A: 22.40 m² by room outlines × sheet scale · in use" | "In use" is the value currently counted in the total. | P2 |
| Detail | `surveyor/QuantityDetail.tsx:93,100-121` | "Keep A", "Settle at", "Settle" (disabled unless allowed) | Disabled: type a value and your name first, or the sign-off is locked. | P1 |
| Detail | `surveyor/QuantityDetail.tsx:130` | "Counting rule: ..." | The written rule behind this count. | P2 |
| Detail | `surveyor/QuantityDetail.tsx:143,152,157` | Add / Remove marks, "Reset this quantity" | Add a mark Vellum missed, take one away, or undo all changes to this quantity. Disabled while signed off. | P2 |
| Detail | `surveyor/QuantityDetail.tsx:164,193,182` | "Signing as", "Sign off 30.00", "Undo sign-off" | Sign off: you confirm this value is correct. It shows to engineers as checked. Undo lets you edit again. | P1 |
| Marks | `surveyor/MarkList.tsx:23,54` | Mark list, per-mark action (disabled when locked) | Disabled: undo the sign-off to edit marks. | P2 |
| Marks | `surveyor/MarkList.tsx:65-72` | "unlocated" counts, "A room's area is unknown" | Counted in the table but not found on the sheet, so no mark is drawn. | P2 |

### Checks (building-code pre-check)

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Checks | `checks/ChecksScreen.tsx:151` | "Pre-check: {pack}" | A first pass against the country's rules. It is not a permit or a certificate. | P2 |
| Checks | `checks/ChecksScreen.tsx:329-332` | Columns "Passed / Failed / Cannot tell" | Places that meet the rule, break it, or could not be judged because something was not read. | P2 |
| Checks | `checks/ChecksScreen.tsx:341-346` | "Does not apply to these drawings", "Cannot tell on N drawings: nothing could be read" | The rule is about something these drawings do not show, or nothing could be read. | P2 |
| Checks | `checks/ChecksScreen.tsx:244` | Result word on each card (STATUS_WORD) | Pass, fail, or cannot tell. | P2 |
| Checks | `checks/ChecksScreen.tsx:256` | "Read the clause (opens the source)" | Opens the legal text this check comes from. | P3 |
| Checks | `checks/ChecksScreen.tsx:269,272,274` | "Show on the drawing", "Not located on the drawing", "Open in the surveyor" | Jump to the place on the plan / this check has no place on the plan / open the numbers behind it. | P2 |
| Checks | `checks/ChecksScreen.tsx:363` | "Export issues and plans" | Download the issues and annotated plans. | P3 |

### Documents and issues

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Documents | `documents/DocumentsScreen.tsx:112-113` | "N files ingested, N drawings read from them" | A file can hold several drawings, or none. | P3 |
| Documents | `documents/DocumentsScreen.tsx:122` | "Building-code checks" | Pre-check the drawings against the country's rules. | P2 |
| Documents | `documents/DocumentsScreen.tsx:128-134` | "Issues" + "Notes are for your information" | An issue is something Vellum could not decide alone. Answer it, or ignore notes. | P1 |
| Documents | `documents/DocumentsScreen.tsx:144` | "Export" | Download the issues list. | P3 |
| Documents | `documents/DocumentLists.tsx:22` | Triage verdict badge (`verdictOf(...).pill`) | Whether the file looks like a floor plan, and who decided. | P2 |
| Documents | `documents/DocumentLists.tsx:51-52` | Kind and route ("PDF vector · exact geometry") | Kind: file type. Route: which reader handles it. | P2 |
| Documents | `documents/DocumentLists.tsx:60` | "Open" | Open this drawing in the workspace. | P3 |
| Issue | `documents/IssueCard.tsx:127,138` | "It belongs to this project" / "It does not belong" | Disabled until you give your name (reason: your name is stored with your answer). | P2 |
| Issue | `documents/IssueCard.tsx:270` | "Use my answer" (disabled) | Type your name and an answer first. | P2 |
| Issue | `documents/IssueCard.tsx:303-306` | "Picked by X" / "X could not tell" | Which reader looked at the conflict, and what it decided. | P3 |
| Issue | `documents/IssueCard.tsx:352` | Status badge `pill.word` | Open means it waits for you. Answered means you or a rule settled it. | P2 |
| Issue | `documents/IssueCard.tsx:374-379` | "View in 3D" | Show the objects in the 3D model. | P3 |

### Double-check

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Double-check | `doublecheck/DoubleCheck.tsx:218-219` | "Please double-check" / "Fixing" | Two readers disagree about some marks, so a person should look. Fixing means you are editing the marks now. | P1 |
| Double-check | `doublecheck/DoubleCheck.tsx:179` | "Checked by a person" | A person signed this answer off. | P2 |
| Double-check | `doublecheck/DoubleCheck.tsx:294-296` | "reader: says" lines | What each reader saw at this spot. | P2 |
| Double-check | `doublecheck/DoubleCheck.tsx:307,309` | "Reject mark" / "Restore mark" | Reject: do not count this mark. Restore: count it again. | P2 |
| Double-check | `doublecheck/DoubleCheck.tsx:321,433` | "Add it here", "Add one" | Count something a reader saw but Vellum did not. | P2 |
| Double-check | `doublecheck/DoubleCheck.tsx:407,418` | "Looks right" / "Fix it" | Looks right: sign off the number as shown. Fix it: edit the marks first. | P1 |
| Double-check | `doublecheck/DoubleCheck.tsx:354,357` | "Confirm" (disabled until the name is filled) | Type your name first; it is saved with your sign-off. | P2 |

### 3D model

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| 3D | `model3d/ModelView.tsx:122-134` | Toolbar icons ⟲ ⟳ + − ⌂ | Rotate left, rotate right, zoom in, zoom out, reset view (same words as the aria-labels; replace `title`). | P2 |
| 3D | `model3d/ModelView.tsx:158,174` | Legend and "ROLE: count" | Colours show which parts the answer is about. | P3 |
| 3D | `model3d/ModelView.tsx:181-183` | "N of M elements are not in the 3D view" | Some objects have no 3D shape in the model. | P3 |
| 3D | `model3d/ModelView.tsx:211-214` | "Show in 3D" + "N elements" | Opens the model. Elements are the walls, doors and other objects in it. | P3 |

### Account, About, Advanced

| Screen | file:line | Element | Proposed tip | Pri |
| --- | --- | --- | --- | --- |
| Account | `account/AccountScreen.tsx:62` | "Your workspaces" | A workspace is one uploaded project and everything read from it. | P2 |
| Account | `account/AccountScreen.tsx:231` | Stat labels | Say where each number comes from (project, drawings, sign-offs). | P3 |
| Account | `account/AccountScreen.tsx:257-270` | "History" glyphs | Icons mark what happened: upload, question, sign-off. | P3 |
| About | `shell/AboutScreen.tsx:66` | "Drawing credits" | Who made each sample drawing and its licence. | P3 |
| Advanced | `advanced/AdvancedIngest.tsx:191` | Step rail | Click a step to see what happened in it. | P3 |
| Advanced | `advanced/AdvancedIngest.tsx:232` | "By route" counts | Files grouped by how they were read (exact geometry, scan reader...). | P2 |
| Advanced | `advanced/AdvancedIngest.tsx:247` | "Skip {path} {reason}" | This file was left out and why. | P3 |
| Advanced | `advanced/visuals.tsx:78,168,344` | "Files in this upload", "What was found", "Measured twice" | Measured twice = quantities counted with a second method as a check. | P3 |

## Counts

P1: 31 places. P2: about 60. P3: about 40. The P1 set covers: home/sample, offline strip, Documents badge, country
pill, the progress stats and file-state words, the trace's stages, the engineer page's "how it was read" and suggested
questions, the send button, marks, the answer card's status and checks, the surveyor takeoff and conflict card, and
sign-off.

## Notes for the implementer

- Many P1 texts exist already in data: step `hint` (`ingest/ingest.ts:101-141`), `statusTip` (`engineer/format.ts`),
  the conflict tip. Reuse them so wording stays in one place.
- "Disabled with a reason" places (Send, Settle, Sign off, Confirm, Use my answer, Choose-conflict buttons, mark
  actions while signed off, page arrows) should wrap the button in a focusable `<span>`; give the reason, not a
  description of the button.
- Do not tip text that already explains itself (the sample caption, "Back to the project", the Retry buttons).
- Words to keep out of tips: sha256, route, normalise, takeoff, IFC GlobalId (explain them or leave them to P3).

# Page viewer (spec, frontend v1)
Status: draft, 2026-11-14, by fe-spec-viewer.  Story: #33.  API: docs/API.md (v1).

## Purpose

The page viewer shows one page of a drawing with the evidence of a number drawn on it: numbered marks on counted
items, shaded rooms in a sum, rejected, added and left-out items, and where two disagreeing methods read their
values. The engineer view uses it to show why an answer is what it is; the surveyor view uses it to select, reject
and add marks. It shows nothing it can't back with API data, and a mark's state never depends on colour alone.

The viewer does not fetch JSON and owns no app state. The screen hands it the pages and marks it already has
(from `POST /api/ask`, `GET /api/drawings/{id}` or `GET /api/drawings/{id}/takeoff`). The viewer reports clicks
back to the screen. Its only requests are the page images.

Field names and fixtures are those of `docs/API.md` and `backend/tests/fixtures/api_v1/` on main after PR #63
(5092dc3). The viewer never shows the answer's confidence (Open point 1).

## Files owned

- `frontend/src/viewer/PageViewer.tsx`: the component the screens use (page switcher, zoom, legend, caption).
- `frontend/src/viewer/PageFrame.tsx`: one page image in the page frame with its mark layer, loading and error
  state. Exported so the ingest trace can show `preview.png` without marks (Open point 5).
- `frontend/src/viewer/MarkLayer.tsx`: the SVG shapes and the HTML number badges.
- `frontend/src/viewer/marks.ts`: pure functions: `pickWidth`, `startPage`, `markLook`, `pickBox`, `drawOrder`,
  `safeColour`, `normalisedNote`.
- `frontend/src/viewer/viewer.css`
- Tests: `frontend/src/viewer/marks.test.ts` [unit], `frontend/src/viewer/PageViewer.test.tsx` [component].
  [e2e] criteria are built by the e2e worker (golden-path.md). The viewer build worker writes no e2e file.

### Props

Types are imported from `frontend/src/api` (shared.md "Types"): `Page` = `PageView`, `Mark` = `MarkView`,
`Conflict` = `QuantityConflict`, `LegendEntry` = `NonNullable<AnswerView["proof"]>["legend"][number]` (shared.md
names no type for it), `Box` = `MarkView["box"]`. These are local aliases in `PageViewer.tsx`, not new exports.

```ts
interface PageViewerProps {
  file: string;                       // drawing's `file`, shown as the caption (text, never HTML)
  pages: Page[];                      // drawing.pages or answer.pages
  marks: Mark[];                      // every page's marks; the viewer filters by `mark.page`
  credit: string | null;              // GET /api/drawings/{id} `credit`, rendered with the shell's <Credit>
  unit?: string | null;               // row's (or answer's) `unit`; badges show mark values unless "count" or null
  unlocated?: Record<string, number>; // takeoff row's `unlocated` (the ask answer has it in `legend[].note`)
  legend?: LegendEntry[] | null;      // answer.proof.legend: colour per label, `note` lines
  conflict?: Conflict | null;         // row's `conflict`: where each method read its value
  selected?: string | null;           // mark id the screen has selected
  highlighted?: string | null;        // mark id hovered or focused in the screen's own list
  onSelect?: (markId: string | null) => void;
  onHover?: (markId: string | null) => void;
  onPick?: (page: number, box: Box) => void; // set only while the surveyor is adding a mark
}
```

`PageFrame` takes `{ url: string; width: number; height: number; alt: string; children?: ReactNode }`. `url`
has no `?width=`: the frame adds it.

## User flow

1. The screen renders `PageViewer` with an answer or a takeoff row. The viewer opens on the page of the first
   mark with a number `n`. With no such mark it opens on the first mark's page, and with no marks on `pages[0]`.
2. While the PNG loads, the frame already has the page's aspect ratio (`pages[].width / height`), says
   "Loading page 1…" and draws the marks over the blank frame.
3. The image appears. Each mark is an outline or shaded region with a badge. Directly under the page is the
   credit, then a legend that names, in words, each mark state on this page, then the file name.
4. On a drawing with several pages the user moves between them with the page switcher, which says how many marks
   each page has.
5. The user hovers over or focuses a badge. The viewer reports it (`onHover`) so the screen can light up its list
   row. The screen hovers a row (`highlighted`), and the viewer outlines that mark.
6. The user clicks or taps a badge or a shape, or presses Enter or Space on a focused badge. The viewer calls
   `onSelect(id)`. When the screen passes the id back as `selected`, the viewer shows the mark selected, says in
   one line under the page what it is, switches to its page and scrolls it into view. Escape calls
   `onSelect(null)`.
7. The user zooms with `+`, `−` and "Fit" (100 %, 200 %, 400 %) and pans by scrolling, or by dragging on a touch
   screen.
8. (Surveyor, adding.) While `onPick` is set, a click on the page outside a badge calls `onPick(page, box)` with a
   small square around the point. The surveyor screen sends the `add` and passes the new takeoff back in.

## API calls

The viewer makes no JSON call. It reads the following fields from data the screen passes in.

**`GET /api/drawings/{drawing_id}/pages/{n}.png?width=<400|1600|3200>`** (API.md "Drawings"). The `<img src>` is
`page.url + "?width=" + w` (the same string as shared.md's `pageUrl(drawingId, n, w)`; `w` is a
`PageWidth`). `w = pickWidth(cssWidth, devicePixelRatio, zoom)` is the smallest of 400, 1600 and
3200 that is at least `cssWidth × dpr × zoom`, and 3200 when none is. `cssWidth` is the frame's width at zoom 1,
measured once on mount (ResizeObserver). The width is only raised, never lowered, so a resize does not fetch the
page again. The response is immutable and cached, so a page shown once loads from the browser cache.

- Called: when a page is shown, and again at a larger width when zoom needs it.
- On an image `error` event the viewer fetches the same URL once with `fetch`. A non-2xx answer is parsed as
  `{detail, code}` (`error.json`) and shown. A network failure shows "network error".

Fields read (fixtures in `backend/tests/fixtures/api_v1/`):

| Field | Drives | Fixture |
| --- | --- | --- |
| `pages[].page`, `.url` | page switcher numbers; image URL | `drawing.json`, `answer.json` |
| `pages[].width`, `.height` | frame aspect ratio, `pickBox` square (unit `pt`/`px` ignored) | `drawing.json` |
| `pages[].normalised` | one caption line saying what was done to the image (`normalisedNote`) | `project.json` f2 (shape) |
| `credit` | the shell's `<Credit>` (shared.md) directly under the page: "Credit: <credit>", or "Credit: none recorded for this file" when null | `drawing.json` (null) |
| `file` | caption | `drawing.json`, `answer.json` |
| `marks[].id` | key for `selected`, `highlighted`, `onSelect` | `answer.json` |
| `marks[].n` | badge number; null → no number | `answer.json`, `takeoff.json` |
| `marks[].page` | which page draws it; switcher counts | `answer.json` |
| `marks[].box` | outline, or badge position when there is a polygon | `answer.json` (doors) |
| `marks[].polygon` | shaded region (null → the box) | `answer_area.json`, `takeoff.json` |
| `marks[].state` | look and words (table below) | `answer.json` (counted); others derived (see criteria) |
| `unit` (row or answer) | whether badges show values, and their unit | `answer_area.json` (`m2`), `answer.json` (`count`) |
| `marks[].value` | badge value when `unit` is not `count` | `answer_area.json` |
| `marks[].label` | colour lookup in `legend`, badge `aria-label`, selection line | `answer.json`, `answer_area.json` |
| `marks[].reason` | selection line and `aria-label` of an excluded mark, and of a counted one restored from excluded | derived |
| takeoff row `unlocated` | one legend line per class: "<k> <class> counted without a mark" | `takeoff.json` (`{}`), derived |
| `proof.legend[].label`, `.colour` | outline and fill colour per label | `answer_area.json`, `answer_confidence.json` |
| `proof.legend[].note` | a text line in the legend (items counted without a mark) | derived (null in fixtures) |
| `conflict.values[].method`, `.value`, `.unit`, `.page`, `.box` | reading tags A, B… | `takeoff.json` row `area:room|name=1.01` |

### How each mark is drawn

Shapes are drawn in an SVG laid over the image with `viewBox="0 0 1 1"` and `preserveAspectRatio="none"`. Every
stroke has `vector-effect="non-scaling-stroke"`, so it keeps its pixel width. A stretched SVG would distort text
and circles, so badges are HTML elements placed in percent, as in API.md's recipe. Each badge sits at its mark's
box centre and is a 24 × 24 CSS px `<button>` with a white background, ink text and a 2 px border in the mark's
colour, so its contrast does not depend on the class colour. The colour of a mark follows the backend's
`evidence.png` (`evidence_render.py`): when `legend` has exactly one entry, every mark takes that entry's colour
(a room count's legend is one `room` entry while its marks carry the room labels); otherwise it is the entry
whose `label` equals `mark.label`, else the accent colour. An excluded mark is always grey. A colour that is not
`#rrggbb` also gets the accent (`safeColour`). (QA R1-3-2.)

| `state` | Shape | Badge text | Words (legend, `aria-label`) |
| --- | --- | --- | --- |
| `counted` | solid 2 px outline in the colour; polygon also filled in the colour at 25 % opacity | `n` (plus value, see below) | "counted" |
| `added` | dashed 2 px outline (6 3) in the colour | `+n` | "added by a surveyor" |
| `rejected` | dotted 2 px outline (2 3) in the colour, no fill, crossed corner to corner | `×` | "rejected by a surveyor" |
| `excluded` | dashed grey outline, grey diagonal hatch fill | `–` | "left out by the rule: <reason>" |
| conflict reading | dashed 2 px outline in the warning colour, not a button | `A`, `B`… in order of `conflict.values` | "<letter>: <method> read <value> <unit>" |

- When `unit` is set and not `count`, a mark with a `value` shows it in its badge as `n · 22.40 m²`, formatted
  by `formatValue(value, unit)` from `src/api/format.ts` (shared.md): exactly 2 decimals, units m² m³ m ft² ft
  (`22.40 m²`). The badge then grows to fit its text.
- Polygons are drawn largest box area first, so a room inside another room stays on top and can be clicked
  (`drawOrder`).
- Highlighted (`highlighted` or hover): the outline is 4 px and the badge has a 3 px ink ring. Selected
  (`selected`): the badge is ink with white text, `aria-pressed="true"`, and the outline is 4 px.
- The badge `aria-label` is "Mark <n>: <label>, <words>". A mark with no number is "<label>, <words>". A null
  label reads "item".
- A mark whose `page` is not in `pages`, or whose box is outside 0..1, is not drawn. The legend says
  "<k> mark(s) could not be placed", so nothing disappears silently.

## States

| State | What the viewer shows | Reach it on purpose |
| --- | --- | --- |
| Loading | frame at the page's aspect ratio, light grey, text "Loading page <n>…", `aria-busy="true"`; marks already drawn | component: render before firing `load`; e2e: delay the PNG route |
| Loaded | the page image, marks, legend, caption | `drawing.json` + `answer.json`, fire `load` |
| Page failed | the frame stays at its aspect ratio with the marks. The text reads "Page <n> could not be loaded: <detail> (<code>)" or "…: network error", with a "Try again" button that sets the `src` again | component: fire `error`, fetch mocked to 404 with `error.json`; e2e: route the PNG to 404 with `error.json` |
| No pages | no frame and no switcher. The text reads "This drawing has no page to show: it is a building model." | `answer_model.json` (`pages: []`) |
| No marks | the page with no overlay and no legend. The screen says why (refusal, nothing asked yet) | `answer_refused.json` (`marks: []`), `drawing.json` alone |
| Refusal | same as no marks. The refusal text is the engineer screen's | `answer_refused.json` |
| Set aside | not reached: a set-aside file has no drawing, so the viewer is never opened on it | n/a |
| No-keys | nothing of its own. The shell's "running offline" banner shows above it. A `hello` drawing has no marks, so it shows as "No marks" | `info.json` (`no_keys: true`) |
| Adding (surveyor) | crosshair cursor over the page. Badges still select | `onPick` set |
| Multi-page | switcher "Page <i> of <k> · <m> marks", previous and next buttons, disabled at the ends | `drawing.json` page copied as page 2 |

## Layout

The mock's viewer card (`demo/`, `viewerHTML`: caption, stage, legend) is the model.

- **Desktop 1440x900**: the viewer fills the workspace's middle column (the engineer and surveyor specs set its
  width). Top row: the page switcher (when there are several pages) on the left, zoom `−` / percent / `+` /
  "Fit" on the right. Then the scroll box with the frame, at most 70 vh high, page fitted to the width at
  zoom 1. Directly under it the credit line (shell `<Credit>`), then the legend (one item per state present,
  then each `legend` entry's colour swatch and label, then `note` lines), the selection line, then the caption:
  file name in mono and the `normalised` note.
- **Phone 390x844**: the viewer is full width inside the 16 px gutters (358 px) and the scroll box is at most
  60 vh. Switcher and zoom buttons are at least 44 × 44 px. The legend and caption wrap and never scroll
  sideways. Panning at zoom > 100 % is native touch scrolling in the scroll box. Badges stay 24 px at every zoom.
- No horizontal page scroll at either size, at any zoom: only the scroll box scrolls.

## Acceptance criteria

Fixtures are the files in `backend/tests/fixtures/api_v1/`, imported read-only. A "derived" mark is a fixture
mark copied with only the named fields changed (e.g. `answer.json` m2 with `state: "rejected", n: null`).

Page and frame

- **VW-1** The image `src` is `/api/drawings/adeefbbcc17559fc/pages/1.png?width=1600` for `answer.json` in a
  frame 800 CSS px wide at dpr 1. [component, `answer.json`, mocked width]
- **VW-2** `pickWidth` gives 400 for (300, 1, 1), 1600 for (800, 2, 1), 3200 for (900, 2, 1), 3200 for
  (900, 1, 4), and never another number. [unit]
- **VW-3** In an 800 px frame at dpr 1, zooming to 200 % keeps `width=1600`, and zooming to 400 % changes `src`
  to `width=3200`. Zooming back to 100 % keeps 3200. [component]
- **VW-4** Before the image's `load` event the frame's aspect ratio is 600 / 400, it reads "Loading page 1…"
  with `aria-busy="true"`, and both door badges are already in the DOM. [component, `answer.json`]
- **VW-5** After `load`, the loading text is gone and `aria-busy` is not "true". [component, `answer.json`]
- **VW-6** On the image's `error` event the viewer fetches the same URL. When the response is 404 with
  `error.json`, the frame reads "Page 1 could not be loaded: no drawing 0123456789abcdef (not-found)". Clicking
  "Try again" sets the `src` again. [component, `error.json`; e2e: PNG route answered 404]
- **VW-7** When that fetch rejects (network), the frame reads "Page 1 could not be loaded: network error".
  [component]
- **VW-8** With `pages: []` there is no `img`, and the viewer reads "This drawing has no page to show: it is a
  building model." [component, `answer_model.json`]
- **VW-9** With `marks: []` the page shows with no badge, no SVG shape and no legend. [component,
  `answer_refused.json`]
- **VW-10** The `img` `alt` is "Page 1 of plans/flat-a.pdf". [component, `drawing.json`]

Marks

- **VW-11** For `answer.json` there are two badges, reading "1" and "2". Badge 1's centre is at
  `left: 50%`, `top: 25%` of the frame (box centre of m1, rounded to 0.1 %). [component, `answer.json`]
- **VW-12** Each mark with a `polygon` is drawn as an SVG `polygon` whose `points` are the fixture's pairs. A
  mark without one is drawn as an SVG `rect` from its `box`. [component, `answer_area.json`, `answer.json`]
- **VW-13** The overlay SVG has `viewBox="0 0 1 1"` and `preserveAspectRatio="none"`, and every shape has
  `vector-effect="non-scaling-stroke"`. [component]
- **VW-14** With `unit="m2"` badge 1 of `answer_area.json` reads "1 · 22.40 m²". With `unit="count"` or
  `unit={null}` the badges of `answer.json` hold no value. [component]
- **VW-15** A derived `rejected` mark (`answer.json` m2, `state: "rejected", n: null`) has badge text "×", a
  dotted outline and two crossing lines, and `aria-label` "door, rejected by a surveyor". [component]
- **VW-16** A derived `added` mark (`id: "a1", n: 3, state: "added", label: null, ref: null, polygon: null`) has
  badge text "+3", a dashed outline, and `aria-label` "Mark 3: item, added by a surveyor". [component]
- **VW-17** A derived `excluded` mark (`answer_area.json` m2 with `id: "x1", n: null, state: "excluded",
  label: "Balkon", reason: "outdoor room"`) has badge text "–", a hatch fill and `aria-label` "Balkon, left out
  by the rule: outdoor room". [component]
- **VW-18** `markLook(state)` gives a distinct pair of (badge text form, line style) for each of `counted`,
  `added`, `rejected`, `excluded`. With all colours set to the same value, the four looks are still
  distinguishable by text and line style. [unit]
- **VW-19** With `conflict` from `takeoff.json` row `area:room|name=1.01`, two non-button tags "A" and "B" are
  drawn at the two `values[].box` centres. The legend reads "A: polygon_x_scale read 22.40 m²" and
  "B: printed_label read 30.00 m²". [component, `takeoff.json`]
- **VW-20** A conflict value with `box: null` (derived) draws no tag but is still listed in the legend.
  [component]
- **VW-21** With `legend` from `answer_area.json`, the Küche polygon's stroke is `#d62728` and the Reduit
  polygon's is `#1f77b4`. Without `legend`, both use the accent colour. With a one-entry legend
  (derived: `[{label: "room", colour: "#1f77b4", …}]`), both polygons and both badge borders are `#1f77b4`
  although no mark is labelled `room` (R1-3-2). [component, `answer_area.json`]
- **VW-22** `safeColour` returns the input for `#d62728` and the accent for `red`, `#d6272`,
  `url(x)` and `#d62728;x`. [unit]
- **VW-23** Badges have a white background, ink text and a border in the mark's colour, whatever the colour.
  [component, `answer_area.json` legend]
- **VW-24** For takeoff row `area:room|indoor` (m1 Küche contains m2 Reduit), Reduit's polygon comes after
  Küche's in the DOM, and a click at Reduit's box centre selects `m2`. [component, `takeoff.json`; unit
  `drawOrder`]
- **VW-25** A mark on page 3 of a one-page drawing, or with a box value outside 0..1, is not drawn. The legend
  reads "1 mark(s) could not be placed". [component, derived]
- **VW-26** Labels, reasons, method names, file names and the credit render as text. A derived label
  `<img src=x onerror=alert(1)>` shows as literal text and adds no `img` element. [component]

Legend and caption

- **VW-27** The legend names, in words, exactly the states present on the shown page: `answer.json` gives
  "counted" only, and the VW-15 set gives "counted" and "rejected by a surveyor". [component]
- **VW-28** A `legend` entry with `note: "2 counted without a mark (second reader)"` (derived from
  `answer_confidence.json`) shows that note as text in the legend. With `unlocated: {door: 2}` (derived from
  `takeoff.json` row `door`) the legend reads "2 door counted without a mark". With `{}` no such line shows.
  [component]
- **VW-29** Directly under the page image, with `credit: "Plan © Example, CC BY 4.0"` (derived from
  `drawing.json`) the viewer shows "Credit: Plan © Example, CC BY 4.0". With `credit: null` it shows "Credit:
  none recorded for this file" (shell `<Credit>`, SH-40). The file name is shown either way. [component,
  `drawing.json`]
- **VW-30** `normalisedNote` gives "" for null and for
  `{exif: null, rotated: 0, deskew_deg: 0, rectified: false}`. For `{exif: 6, rotated: 90, deskew_deg: 1.5,
  rectified: true}` it gives "shown upright: EXIF turn applied, turned 90°, deskewed 1.5°, perspective
  corrected". The caption shows a non-empty note. [unit; component]

Pages

- **VW-31** `startPage` gives the page of the first mark with a number `n`. With none it gives the first mark's
  page, and with no marks `pages[0].page`. [unit]
- **VW-32** With two pages (page 2 derived from `drawing.json`) and the `answer.json` marks on page 1, the
  switcher reads "Page 1 of 2 · 2 marks". "Previous" is disabled. "Next" shows page 2 with `src` `…/pages/2.png?…`,
  no badges, and "Page 2 of 2 · 0 marks". [component]
- **VW-33** With one page the switcher is not rendered. [component, `drawing.json`]
- **VW-34** Setting `selected` to a mark on page 2 while page 1 is shown switches to page 2. Setting
  `highlighted` to it does not switch. [component, derived]

Selection, highlight, keyboard

- **VW-35** Clicking badge 2 of `answer.json` calls `onSelect("m2")` once. Clicking the polygon of a mark calls
  `onSelect` with its id. [component]
- **VW-36** Tab focuses the badges in mark order. Enter and Space on a focused badge call `onSelect(id)`.
  Escape inside the viewer calls `onSelect(null)`. [component]
- **VW-37** With `selected="m1"`, badge 1 has `aria-pressed="true"` and the others `"false"`. The selection line
  reads "1 · door · counted". For the VW-17 mark selected it reads "– · Balkon · left out by the rule: outdoor
  room". A derived `counted` mark with `reason: "outdoor room"` (restored from excluded) reads
  "1 · Balkon · counted (the rule left it out: outdoor room)". No confidence, score or probability text appears
  anywhere in the viewer for `answer_confidence.json`. [component]
- **VW-38** With `highlighted="m2"`, mark m2's shape has a 4 px stroke and its badge has the highlight ring
  class. Shapes of other marks keep 2 px. [component]
- **VW-39** Pointer enter and focus on badge 1 call `onHover("m1")`. Pointer leave and blur call
  `onHover(null)`. [component]
- **VW-40** In the engineer and surveyor flows, hovering a list row outlines the matching mark, and clicking a
  mark selects the matching row. [e2e, golden path on the sample; built by the e2e worker]

Zoom, adding, layout

- **VW-41** "+" goes 100 → 200 → 400 % and is disabled at 400. "−" goes back down and is disabled at 100.
  "Fit" returns to 100 %. The percent is shown as text. At 200 % the frame is twice the scroll box's width and
  the scroll box scrolls. [component]
- **VW-42** With `onPick` set, a click at the frame's centre on a 600 × 400 page calls `onPick(1, box)` where
  `box` is `[0.485, 0.4775, 0.515, 0.5225]` (square 3 % of the page width, y scaled by width / height). A click
  near an edge gives a box shifted inside 0..1, same size. A click on a badge selects it and does not pick.
  [unit `pickBox`; component]
- **VW-43** Without `onPick`, a click on the page outside any mark calls nothing. [component]
- **VW-44** At 390x844 and 1440x900, with `answer_area.json` at zoom 100 % and 400 %, the document has no
  horizontal scroll (`scrollWidth <= innerWidth`). Switcher and zoom buttons are at least 44 × 44 px at 390. A
  screenshot of each is taken and looked at. [e2e, in the engineer flow]

## Out of scope

- Pinch zoom, wheel zoom and drag-to-pan with the mouse. Zoom is three button steps and panning is native
  scrolling. Upgrade only if the demo shows a need.
- Drawing a building model (`proof.objects`, `proof.storeys`) and the schedule's table or row highlight
  (`proof.schedule`). The engineer spec lists them as text. Schedule marks with a box are still drawn as marks.
- `proof.arithmetic` and the answer's confidence (`confidence`, `proof.confidence`, `line.confidence`): the
  engineer screen owns them. The viewer shows no confidence in any form.
- Before/after of a normalised photo: the ingest trace can use `PageFrame` on `preview.png` (Open point 5).
- `GET /api/drawings/{id}/evidence.png`: the server's own drawing of the proof, as a share picture or fallback.
  The viewer draws the proof itself; a link to the picture is the engineer screen's.
- Editing a room's outline or label, adding marks to an area (API.md "What is not in v1"), a per-item amber
  contested mark (API.md: the frontend doesn't build one; conflict readings are drawn as tags A, B instead).
- Thumbnails in lists: `pickWidth` gives 400 for a small frame, so a screen gets a thumbnail by rendering
  `PageFrame` small.

## Open points

1. **Confidence shape, pending the next backend PR (Bogdan, board #14).** The answer confidence becomes an object
   `confidence: {signal, score, calibrated: false}`: `score` is a raw model choice score, not a probability, and
   API.md's "probability" wording and the "Probability this answer is right" line go. Today's fixtures still have
   the number (`answer_confidence.json` 0.87). The viewer neither takes nor shows it in either shape (VW-37), so
   the change does not touch it. The engineer spec owns how the new object is shown (never as a probability or
   percent).
2. **No fixture has a `rejected`, `added` or `excluded` mark, a `note`, a credit or a second page.** The criteria
   derive them from fixture marks with named overrides until real ones land: asked on board #14.
3. **The ask answer has no `credit`.** The engineer screen must take it from `GET /api/drawings/{id}`, which it
   already calls for `suggestions`. Recommendation: keep it that way. Otherwise add `credit` to the answer.
4. **Takeoff rows have no `legend`.** On the surveyor screen every mark gets the accent colour, while the engineer
   screen's door is red. That is fine for one class per row. Recommendation: no change for v1.
5. **Trace preview.** ingest.md keeps its own `BeforeAfter`. Per round-1 decision 4, its "after" image carries the
   shell `<Credit>` and the upload preview carries none. `PageFrame` takes any URL with a size, so ingest may reuse
   it for the frame, loading and error states. That is optional and changes nothing here.
6. **Number format: decided** (round-1 decision 2). The viewer imports `formatValue` from `src/api/format.ts`
   (shared.md) and has no formatter of its own.
7. **Add-mark box size** (3 % of the page width) is a viewer choice. `review_requests.json`'s example add is a
   0.03 square, which agrees. The surveyor spec may override it by building its own box from the point; the
   recommendation is to keep it here.
8. **engineer.md alignment.** Its OP 5 (conflict boxes on the page) is answered by the `conflict` prop (tags A,
   B), and its OP 7 by the props above. The highlight prop is `highlighted`, the callbacks are `onSelect` and
   `onHover`, and value formatting is the shared `formatValue`. Its EN-23 "Probability right: 87%" conflicts with the
   board #14 change (OP 1). That is for the engineer spec to fix, not the viewer.

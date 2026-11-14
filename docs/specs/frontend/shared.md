# Shared parts: shell, API client, info bar, common views (spec, frontend v1)

Status: Vellum round (2026-11-14, by fe-shared): "Design tokens" and "Vellum look" supersede the old Layout
where they differ. Earlier: round 1 fixes applied.  Story: #33.  API: docs/API.md (v1).

## Purpose

Every screen sits inside one app shell: a header with the product name, the project picker and the links between
Ingest, Engineer and Surveyor; a strip that says the app runs offline and which readers are active; a hash router.
Every screen talks to the backend through one typed client in `frontend/src/api/` and shows its loading and error
states with the same two components. It also owns the typed fixtures module and the fetch mock that every
screen's tests use. The tooling around it comes from the scaffold PR.

## Design tokens (Vellum)

Taken from the designs (`Main`, `Ingest`, `Conflicts`, `Account`, `Workspace`, `Ingest*` `.dc.html`, Tudor's
"Vellum redesign" canvas). `src/shell/shell.css` defines them on `:root`; every screen's CSS uses only these, no
hard-coded colour. The first fifteen names are the fixed ones of the common brief; the five after them are added
because the designs use those colours on every screen (pill and button fills, status pill backgrounds).

| Token | Value | Where the designs use it |
| --- | --- | --- |
| `--v-bg` | `#f5f5f7` | page background |
| `--v-surface` | `#ffffff` | cards, drop zone, the header |
| `--v-text` | `#1d1d1f` | text; the logo tile's background |
| `--v-muted` | `#6e6e73` | secondary text, captions, chevrons |
| `--v-line` | `#d2d2d7` | hairlines, input borders, the dashed drop border is `#c3cbc7` (use `--v-line`) |
| `--v-accent` | `#3d5a4f` | primary button, links, focus ring, selected state |
| `--v-accent-strong` | `#2a3f37` | link hover, primary button hover/pressed |
| `--v-warn` | `#8a4b00` | text of a "needs you" / conflict pill or verdict |
| `--v-warn-soft` | `#fff3e0` | background of the same |
| `--v-ok` | `#1f6b3b` | text of a "ready" / "approved" / "agree" pill |
| `--v-danger` | `#a1302a` | text of an error or "low" pill |
| `--v-radius` | `24px` | card radius (the drop card is `28px`: `calc(var(--v-radius) + 4px)`) |
| `--v-shadow` | `0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.06)` | card shadow |
| `--v-font` | `-apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif` | everything; no web font is loaded |
| `--v-text-2` | `#48484a` | tag pill text, body text on soft fills |
| `--v-ok-soft` | `#e8f5ec` | background of an ok pill |
| `--v-danger-soft` | `#fdecea` | background of an error pill |
| `--v-accent-soft` | `#e6eeea` | icon tiles, selected rows, chips (`#dfe8e4` in the designs folds into it) |
| `--v-fill` | `#f0f1f0` | secondary button; tag pills (`#f2f2f5` folds into it) |

Header (round-2 QA, 11:35): opaque `var(--v-surface)` with a hairline `box-shadow: 0 1px 0 rgba(0,0,0,0.06)`. The
designs' glass (`rgba(255,255,255,0.72)` + blur) let scrolled engineer content show through and collide with the
header's buttons, so it is not used.

`--v-header-h` (on `:root`, not a colour): what the sticky header covers at the top of the viewport, `76px` on
desktop (row padding 14 + 14 and the 48 px pills) and `0px` at ≤720 px, where the header is not sticky. Any other
sticky element uses `top: var(--v-header-h)`.

## Vellum look (header, page frame, base styles, routes)

### Header (`src/shell/Header.tsx`, one for every screen; screens draw none)

As in every design's `<header>`, without the avatar (common brief: not built). The country picker is built (CHANGE
11:05, Tudor) and changes nothing but its own shown name (see "Pending fields (mocked)").

- Sticky at the top (`z-index: 10`, above every screen layer; engineer.css goes up to 5), opaque (above), inner row `max-width: 1120px` (`1280px` on the account
  and workspace routes, as Account and Workspace have it), `margin: 0 auto`, `padding: 14px 24px`, flex, `gap: 12px`,
  items centred.
- Left: one link to `#/` whose accessible name is "Vellum": the logo `src/shell/vellum-logo.png` (the canvas asset
  `cd1b18eadc2a9e1d35620953447eb25e.png`, committed by this worker) as `<img alt="" width="44" height="44">` in a
  44 px tile (`border-radius: 12px; background: var(--v-text); padding: 6px`), then the name "Vellum"
  (`26px`, line-height 1, `letter-spacing: -0.025em`, weight 700, colour `--v-text`, no underline).
- The view links (`<nav aria-label="Views">`, as today, e2e clicks "Engineer" and "Surveyor"): a segmented
  control (`.v-segmented`, below) after the name. Which links show:

  | Route | Links (current one marked) |
  | --- | --- |
  | home, account, not-found | none |
  | project, file | Ingest (current), Conflicts, Chat |
  | conflicts | Ingest, Conflicts (current), Chat |
  | chat | Ingest, Conflicts, Chat (current) |
  | workspace | Ingest, Conflicts, Chat, Surveyor (Surveyor current on the surveyor route; on the engineer route none: no Engineer tab, Tudor 12:46 "remove the engineer tab") |

  The chat is project-level, so Chat shows wherever a project is in the route (frontend-orch 13:06); Surveyor only
  on drawing routes. Hrefs: Ingest `#/p/<pid>`, Conflicts `#/p/<pid>/conflicts`, Chat `#/p/<pid>/chat`, Surveyor as SH-13 (keeps
  `?q=`). The engineer route itself stays (the chat's "Show it on <file>" and drawing links go there); only its tab is
  gone.
- Right (`margin-left: auto`): the project picker, the country picker, then a "Workspaces" link to `#/workspaces`.
  All three are pills as
  the design's header controls: `background: var(--v-fill)`, `border-radius: 980px`, `min-height: 48px`,
  `padding: 4px 16px`, `16px`, weight 600, colour `--v-text`. The picker keeps its R1-5-4 sizing (`flex: 0 1 320px;
  min-width: 0; max-width: 100%`). "Workspaces" has `aria-current="page"` on `#/workspaces`.
- Country picker (`src/shell/CountryPicker.tsx`, as the designs' `cty` popover): a button named
  "Country rules: <name>" with `aria-expanded`, showing the flag (inline SVG, `aria-hidden`), the name and a chevron;
  it carries `data-pending="country-rules"`. Open, a popover below it (right-aligned, `width: 300px`, max
  `calc(100vw - 32px)`, `--v-surface`, radius 18px, padding 8px, a shadow) is a `role="group"` named "Building rules
  the agent follows" with that heading line, one button per country (flag, name, the law name under it in
  `--v-muted`, a check on the chosen one, `aria-pressed`) and the closing line "Rules are not applied yet." (the
  designs' "Answers and plan edits are checked against these rules" would be a false claim). Choosing a country
  sets the shown name and closes the popover; nothing else happens: no request, no rule, no storage (a reload shows
  the first country again). Escape or a click outside closes it; Escape returns focus to the button. The countries
  come from `src/shell/pending.ts` (below), Finland first.
- Under the header row, the info strip as today (offline text, "What runs"; SH-15 to SH-20 unchanged), restyled:
  `13px`, `--v-warn` on `--v-warn-soft` for the offline sentence, the strip itself transparent, same max-width as
  the header row.
- Phone (≤720 px): the row wraps: logo + name + "Workspaces" on the first line, the project picker (growing) and
  the country picker on the second, the view links full width (equal segments, each ≥44 px high) on the third. No horizontal scroll at
  390 px (R1-5-4 still holds). The header is not sticky there (`position: static`, `--v-header-h: 0px`): its three
  rows (about 190 px) would cover a quarter of a 390x844 screen; it scrolls away with the page.

### Pending fields (mocked)

Superseded in the checks round (#139): the picker lists the real `rule_packs` and `src/shell/pending.ts` is deleted
(see "Checks and issues"). Kept below for the record.

CHANGE 11:05 (Tudor): fields the API lacks get a mock, not nothing. The shell has one: the building rules of the
country picker. `src/shell/pending.ts` exports `PENDING_COUNTRY_RULES` tagged
`// PENDING(Info.country_rules): mock until the backend adds it (#14)`: Finland ("Building Act 751/2023") and
Switzerland ("Cantonal building law, SIA norms"), each `{id, name, law}`. The picker reads the real field first:
`(info as {country_rules?: CountryRule[]}).country_rules ?? PENDING_COUNTRY_RULES` (with `info` from `useInfo`,
the mock also while info is loading or failed). The element carries `data-pending="country-rules"`, no visible
"mock" label.

### Page frame (`<main id="main">`, `src/App.tsx`)

`main` is full width with no padding of its own; each screen wraps its content in one `.v-page` element, sized as
its design:

| Class | `max-width` | Padding (desktop / ≤720 px) | Design |
| --- | --- | --- | --- |
| `.v-page` | 1120px | `72px 24px 80px` / `40px 16px 56px` | Main (screen 1) |
| `.v-page--narrow` | 820px | `48px 24px 72px` / `24px 16px 56px` | Ingest, Conflicts (2, 3) |
| `.v-page--mid` | 1040px | `40px 24px 72px` / `24px 16px 56px` | Advanced (9-12) |
| `.v-page--wide` | 1280px | `40px 24px 72px` / `24px 16px 56px` | Account, Workspace (4, 5) |

All are `margin: 0 auto`, flex column, `gap: 24px`. `main` keeps `min-width: 0; overflow-wrap: anywhere` (R1-5-4).

### Base styles (`src/shell/shell.css`, global; screens use the classes, not copies)

- `body`: `margin: 0; background: var(--v-bg); color: var(--v-text); font: 16px/1.5 var(--v-font);
  -webkit-font-smoothing: antialiased`. `a`: `--v-accent`, hover `--v-accent-strong`.
- Type: `.v-hero` 64px/1.05, 700, `-0.025em`, `max-width: 16ch` (40px at ≤720 px); `.v-title` (page `h1`)
  44px/1.1, 700, `-0.02em` (32px at ≤720 px); `.v-h2` 34px/1.1, 700, `-0.02em`; `.v-h3` 24px/1.25, 600, `-0.01em`;
  `.v-caption` 13px `--v-muted`.
- Card `.v-card`: `background: var(--v-surface); border-radius: var(--v-radius); box-shadow: var(--v-shadow);
  padding: 24px` (20px at ≤720 px). `.v-card--hero` (the drop card): radius `calc(var(--v-radius) + 4px)`,
  padding `48px 32px`.
- Buttons `.v-btn` (primary): `font: inherit; 15px; weight 600; color: #fff` (on accent only), `background:
  var(--v-accent); border: 0; border-radius: 980px; padding: 12px 22px; min-height: 44px; cursor: pointer`; hover
  `--v-accent-strong`; `[disabled]` opacity 0.5, no pointer. `.v-btn--secondary`: `--v-fill` background,
  `--v-text`, weight 500. `.v-btn--round`: 44 px circle (icon buttons, with an `aria-label`).
- Press feedback `.v-press`: `transition: transform 100ms ease-out, box-shadow 160ms ease-out`; `:active`
  `transform: scale(0.97)`.
- Pills `.v-pill`: `12px`, weight 500, `--v-text-2` on `--v-fill`, `border-radius: 980px; padding: 5px 11px`.
  Tones: `.v-pill--ok` (`--v-ok` on `--v-ok-soft`), `.v-pill--warn` (`--v-warn` on `--v-warn-soft`),
  `.v-pill--danger` (`--v-danger` on `--v-danger-soft`), `.v-pill--accent` (`--v-accent-strong` on
  `--v-accent-soft`). A pill always carries its state in words; colour only repeats it.
- Segmented control `.v-segmented` (Ingest's Simple/Advanced, the header's view links): track `--v-fill`,
  `border-radius: 10px; padding: 3px; gap: 2px`; items `14px`, weight 500, `--v-text-2`, `border-radius: 8px;
  padding: 8px 16px; min-height: 36px` (44 px at ≤720 px); the item with `aria-current="page"` or
  `aria-pressed="true"`: weight 600, `--v-text` on `--v-surface`, `box-shadow: 0 1px 3px rgba(0,0,0,0.12)`.
- Focus: every focusable element (`a, button, select, input, textarea, summary, [tabindex]`) shows
  `outline: 2px solid var(--v-accent); outline-offset: 2px` on `:focus-visible`; nothing sets `outline: none`
  without a replacement, except `main` (SH-58). (The designs draw no focus ring; this one is ours.)
- Reduced motion: under `prefers-reduced-motion: reduce` every transition and animation is off
  (`transition: none !important; animation: none !important` on `*`), and `.v-press:active` does not scale.
- Old names: the round-1 mock tokens (`--paper`, `--panel`, `--ink`, `--mute`, `--line`, `--line-soft`,
  `--accent`, `--accent-soft`, `--ok`, `--ok-soft`, `--warn`, `--warn-soft`, `--blue`, `--blue-soft`, `--mono`,
  `--sans`) stay defined as aliases of the `--v-*` tokens, so a screen not yet restyled still matches; they are
  removed once no CSS uses them (Open points 13).
- Shared views restyled: `ErrorView` and `NotFound` are `.v-card`s (`ErrorView`'s code line `--v-muted`, its
  heading `--v-danger` for errors, `--v-text` for not-found); `Loading` is `--v-muted` text; `Credit` `13px`
  `--v-muted`.

### Routes (fixed by the common brief)

| Route name | Hash | Mounted component and props |
| --- | --- | --- |
| `home` | `#/` | `HomeScreen()` |
| `account` | `#/workspaces` | `AccountScreen()` from `src/account/AccountScreen.tsx` (`ComponentType<Record<string, never>>`) |
| `project` | `#/p/<pid>` (`?view=advanced` kept in `query`) | `ProjectScreen({projectId})`; it reads and writes `?view` itself with `useHash`, `parseRoute` and `routeHref` from `src/shell/route.ts` |
| `conflicts` | `#/p/<pid>/conflicts` | `ConflictsScreen({projectId})` from `src/surveyor/ConflictsScreen.tsx` |
| `chat` | `#/p/<pid>/chat` | `ProjectChat({projectId})` from `src/engineer/ProjectChat.tsx` (fe-engineer; chat.md, fe-chat brief 12:06) |
| `file` | `#/p/<pid>/f/<fid>` | `FileTraceScreen({projectId, fileId})` |
| `checks` | `#/p/<pid>/checks` (`?pack=<id>`) | `ChecksScreen({projectId, pack})` from `src/checks/ChecksScreen.tsx` (fe-scaffold, checks.md); `pack: string \| null` from `?pack` |
| `issues` | `#/p/<pid>/issues` (`?pack=<id>` optional) | `IssuesScreen({projectId, pack})` from `src/issues/IssuesScreen.tsx` (fe-ingest, issues.md); `pack?: string` from `?pack` |
| `workspace` | `#/p/<pid>/d/<did>/engineer` / `surveyor` | `EngineerPage` / `SurveyorScreen({projectId, drawingId, query})` |

`parseRoute` returns `{name: 'account', query}`, `{name: 'conflicts', projectId, query}` and `{name: 'chat',
projectId, query}`; ids keep their
patterns, one trailing `/` is accepted, anything else is not-found. `routePath` gives `/workspaces` and
`/p/<pid>/conflicts` and `/p/<pid>/chat`; each screen is keyed by its path (a `?view` or `?q` change does not
remount). `App`'s `Screens` gains `AccountScreen`, `ConflictsScreen` and `ProjectChat`.

## Checks and issues (round 3: #139 building-code pre-check, #140 located issues; fe-checks-issues 13:26)

Backend contract: board decision #142 (records 0009-building-code-checks.md, 0008-located-issues.md). Since #147
(issues) and #150 (#139 checks; c6876636649) every shape is a `schema.d.ts` re-export and the fixtures are the
backend's; the hand-typed block and the hand-made `src/api/testing.ts` are gone. Product rules (#142, binding): the pack `note` is shown
verbatim; "cannot tell" is never shown as pass or fail; nothing is invented.

### API client additions (`src/api/client.ts`)

| Function | Request | Returns |
| --- | --- | --- |
| `getDrawingChecks(drawingId, {pack, project?, signal?})` | `GET /api/drawings/{drawing_id}/checks?pack=<id>[&project=<pid>]` | `DrawingChecks` `{drawing_id, file, file_id, pack, note, status, rules: RuleCheck[]}` |
| `getProjectChecks(projectId, {pack, signal?})` | `GET /api/projects/{project_id}/checks?pack=<id>` | `ProjectChecks` `{project_id, pack, note, status, drawings: DrawingChecks[]}` |
| `getIssues(projectId, {pack?, signal?})` | `GET /api/projects/{project_id}/issues[?pack=<id>]` | `IssueList` `{project_id, pack, issues: Issue[]}` |
| `issuesCsvUrl(projectId, pack?)` | URL only: `/api/projects/{project_id}/issues.csv[?pack=<id>]` | `string` |
| `issuesZipUrl(projectId, pack?)` | URL only: `/api/projects/{project_id}/issues.zip[?pack=<id>]` (CHANGE 13:22: `issues.csv` with an `n` column + one PNG per drawing page with the issues drawn and numbered) | `string` |

- `pack` is required by type on both checks functions (the backend answers 404 without a known pack); query values
  go through `encodeURIComponent` like every other URL builder (D3). Errors are `ApiError` as everywhere (404 unknown
  project/pack, 409 issues before the project is done).
- The rule packs need no request: they arrive with `GET /api/info` (`Info.rule_packs`), which `InfoProvider` already
  loads once. Screens read them with `useInfo()` and `rulePacksOf(info)` (`src/api/format.ts`: `info?.rule_packs ?? []`). (The brief's `getRulePacks` is this; Open point 17.)
- Re-exports (`src/api/types.ts`): `Clause`, `Rule` (= `RuleView`), `RulePack` (= `RulePackView`, adds
  `fail_means`), `CheckMark` (adds `quantity`, `mark_id`), `CheckResult` (status `pass | fail | cannot_tell`),
  `RuleCheck`, `DrawingChecks` and `ProjectChecks` (status may also be `not_applicable`; `CheckStatus` is that wider
  union), `Rule.applies_to` an object (room types, element classes). `Issue` and `IssueList`
  (= `Schemas['ProjectIssues']`) since #147: `IssueKind` adds `unrelated_file`; `check`
  is a string `<pack>:<CheckResult.id>`; `file_id` is nullable; `file` is this project's path; `links` are API paths,
  screens build `#/p/…` routes from the ids; issues come ordered by severity, drawing in project order, page, box top
  (the screen keeps that order). Bogdan accepted all our #142 asks (c6876010899); the per-mark fields (mark id, status, value) are typed as
  the records 0009/0008 name them. Errors: an unknown pack is a 404 with code `unknown-pack` (distinct from an unknown
  project); the 409 code is the one the record names.
- Fixtures: the backend's, in `src/api/fixtures.ts`: `drawingChecks` (`checks.json`), `projectChecks`
  (`project_checks.json`), `projectIssues` (`project_issues.json`), and `rulePackFi` (the `fi` pack of `info.json`,
  which lists `ch-zh` and `fi`).

### Country picker (real; replaces the mock)

- Shown only on routes with a project (project, file, conflicts, chat, checks, issues, workspace) and only when
  `rulePacksOf(info)` is not empty; while info loads, after an info error, with no packs, and on home, account and
  not-found it is not rendered (there is nothing to choose and no project to check).
- The button: flag (inline SVG for `FI` and `CH` by the pack's ISO `country`, none for others), the chosen pack's
  `country_name`, chevron; accessible name "Country rules: <country_name>", or "Country rules: none" with no pack
  (no pack is preselected and "no pack" is a valid choice, 13:44). No `data-pending`.
- The button stays on one line at every width (QA 13:30: "No checks" wrapped at 1440): `white-space: nowrap`; it does
  not shrink (`.country` `flex: 0 0 auto`; the project picker, already ellipsised, gives way first: shrinking both
  cut "No checks" to "No ch…"), it is at most 240px wide and a long `country_name` ends in an ellipsis; flag and
  chevron never shrink.
- The popover (group "Building rules the agent follows"): first "No checks" (pressed when the route has no `?pack`),
  then one button per pack (flag, `country_name`, under it the pack `name` · `version` in `--v-muted`, check on the
  chosen one, `aria-pressed`). Its closing line is the chosen pack's `note`, verbatim ("A pre-check of a few rules, not a
  compliance certificate."); with no pack: "Choose a country to pre-check its building rules."
- Choosing a pack writes `?pack=<id>` into the current route's hash (other query keys such as `q` and `view` kept) with
  a history entry and closes the popover; "No checks" removes `pack`. Nothing is stored and no request is sent by the
  picker itself (the screens fetch with the pack). A `?pack` naming no listed pack shows as "none" (the screens get
  its 404).
- `src/shell/pending.ts` (`PENDING_COUNTRY_RULES`) is deleted; `grep -rn "PENDING(Info" frontend/src` finds nothing.

### The pack in the URL (`src/shell/route.ts`)

- `packOf(route): string | null` reads `route.query.get('pack')`; `withPack(hash, pack)` returns the hash with
  `pack` set (or removed when null), other query keys kept (encoded as `routeHref`). Every link between project
  routes keeps the pack: the header's view links and the project picker (switching project keeps the country) use
  it; screens that link to another project route (conflicts → chat, chat → engineer, issues → drawing, …) use
  `withPack` (their owners; issues.md, checks.md, conflicts.md, chat.md say so).
- `routePath` ignores the query, so choosing a pack does not remount the screen; `ChecksScreen` and `IssuesScreen`
  get the new `pack` prop.

### Header tabs (supersede the Header table above for project routes)

| Route | Tabs, in this order (current one marked) |
| --- | --- |
| project, file | Ingest (current), Conflicts, Checks*, Issues, Chat |
| conflicts | Ingest, Conflicts (current), Checks*, Issues, Chat |
| checks | Ingest, Conflicts, Checks (current), Issues, Chat |
| issues | Ingest, Conflicts, Checks*, Issues (current), Chat |
| chat | Ingest, Conflicts, Checks*, Issues, Chat (current) |
| workspace | Ingest, Conflicts, Checks*, Issues, Chat, Surveyor (current on the surveyor route; none on engineer) |

\* Checks only while the chosen `?pack` names a pack in `rulePacksOf(info)` (QA R5-c-4: not for an unknown pack,
not while info loads or after an info error); on `#/p/<pid>/checks` it always shows, current, so the page has its
tab. Hrefs: `#/p/<pid>`, `/conflicts`, `/checks`, `/issues`, `/chat`, the drawing's surveyor route (keeps
`?q`); every one carries `?pack=<id>` when a pack is chosen.

- Width: up to six tabs no longer fit the one-row header between 721 and ~1100 px, so the compact header (three rows,
  not sticky, `--v-header-h: 0px`; "Vellum look") applies up to 1100 px instead of 720 px. At ≤1100 px the tabs fill
  the third row and wrap to a second line of the control when they do not fit (each ≥44 px high); no horizontal
  page scroll at 390, 768 and 1024.

## Files owned

Tooling: built by the scaffold PR (branch `frontend/scaffold`, worker fe-scaffold), not by this spec's build worker.
It owns `frontend/package.json`, the lockfile, `.nvmrc`, tsconfig, `vite.config.ts`, the eslint and prettier config,
`index.html`, `check.sh`, `README.md`, `scripts/` and the bare `src/main.tsx` / `src/App.tsx`. Facts this spec relies
on:

- Node 24. CI's generic `node` job (`.github/workflows/ci.yml`) pins 24 and runs `npm ci`, `tsc --noEmit`,
  `npm run lint` (eslint + `prettier --check`), `npm test`, `npm run build` and `npm audit` in every folder with a
  `package.json`; there is no separate frontend CI job.
- `npm run api:gen` / `npm run api:check`: `src/api/schema.d.ts` generated by openapi-typescript from
  `docs/api/openapi-v1.json` (the backend's contract lock, landing), or until it lands from the OpenAPI document
  dumped from `backend/` with uv. Only `schema.d.ts` is committed; no copy of the OpenAPI document in `frontend/`.
- Alias `@fixtures` → `../backend/tests/fixtures/api_v1` (Vite and vitest).
- Proxy: `/api` → env `BACKEND_URL` (default `http://127.0.0.1:8000`), for both dev and preview; ports dev 5173,
  preview 4173, `strictPort`.

This spec's build worker owns `frontend/src/api/`, `frontend/src/shell/` and `frontend/src/test/`, and replaces the
scaffold's bare `frontend/src/App.tsx` with the shell (still mounted by the scaffold's `main.tsx`).

API client, `frontend/src/api/`:

- `client.ts`: every endpoint function and URL builder below; `index.ts` re-exports `client.ts`, `errors.ts`,
  `types.ts`, `format.ts`.
- `errors.ts`: `ApiError` and `ErrorBody`.
- `schema.d.ts`: generated by `npm run api:gen` (scaffold's script), never edited by hand.
- `types.ts`: named re-exports of the generated schemas (list below).
- `format.ts`: `formatValue` and `formatTime` (below), used by viewer, engineer, surveyor and ingest.
- `fixtures.ts`: every file of `backend/tests/fixtures/api_v1/` imported and exported under its type (list below).

Shell, `frontend/src/shell/`:

- `frontend/src/App.tsx` (replaced: providers, header, info bar, the route's screen),
  `route.ts` (`parseRoute`, `routeHref`, `useRoute`), `Header.tsx`, `ProjectPicker.tsx`, `CountryPicker.tsx`,
  `pending.ts` (the mocked country rules; deleted in the checks round), `InfoBar.tsx`,
  `info.tsx` (`InfoProvider`, `useInfo`), `limits.ts` (`uploadTooLarge`), `Loading.tsx`, `ErrorView.tsx`,
  `NotFound.tsx`, `Credit.tsx`, `strings.ts` (`PRODUCT_NAME = "Vellum"`, the reader names), `shell.css`
  (tokens, base styles), `vellum-logo.png` (the canvas logo asset).

Test helpers: `frontend/src/test/mockApi.ts`, `frontend/src/test/setup.ts` (Testing Library's jest-dom matchers,
fetch mock reset after each test).

Tests: `*.test.ts(x)` next to each file above. [e2e] criteria are built by the e2e worker (golden-path.md).

## User flow

1. The user opens the app at `#/` (or any deep link). The header shows "Vellum", the project picker and,
   below it, the info strip "Checking the server…" until `GET /api/info` answers; then "Running offline: no API
   keys, no models" with a "What runs" disclosure. The route's screen fills the rest.
2. The user picks a project in the picker: the hash becomes `#/p/<project_id>` and the ingest screen shows it.
3. On a drawing route (`#/p/<pid>/d/<did>/engineer` or `/surveyor`) the header shows three links, Ingest, Engineer,
   Surveyor; the current one is marked. Clicking Surveyor while on Engineer changes the hash to the same drawing's
   surveyor route; Ingest goes to `#/p/<pid>`.
4. The user opens "What runs": each reader port with its reader; a `hello` reader reads "not read".
5. The user types an unknown hash (`#/nope`, or an id with the wrong pattern): the not-found view says nothing is
   there and links back to the start.
6. The backend stops: the strip says "The server did not answer" with the `detail` and `code` and a Retry button;
   the screens show their own error views, built from the shared `ErrorView`.

## API calls

The shell calls two endpoints itself; the client covers every endpoint of API.md (table after them).

**`GET /api/info`** (API.md "GET /api/info"). Once when the app starts, and again on Retry in the info strip. Fields:

- `no_keys`: true → the strip shows "Running offline: no API keys, no models" on every route. false → no offline
  text, the strip shows only the "What runs" disclosure.
- `readers` (port → reader name): listed in "What runs" in the order the object gives, port labels from
  `strings.ts`: `bim` "BIM model", `cad` "CAD (DXF)", `vector` "Vector PDF", `raster` "Scans and photos",
  `tables` "Tables and schedules", `second_counter` "Second count", `rectifier` "Photo rectifier",
  `question_parser` "Questions", `answer_prior` "Answer prior", `decisions_kind` "photo/sheet check" (its value `True`/`False` reads "on"/"off", #14); a port not in
  that list shows its key as is. Each value shows as `readerName(value)` (see "Formatting"): a plain label, never
  the raw id. The list is information only: no reader value changes what any screen offers.
- `limits`: exposed through `useInfo().info.limits`. Ingest refuses an upload over `upload_mb` with
  `uploadTooLarge`; engineer caps the question at `question_chars`. The shell itself shows no limit.
- Fixture: `backend/tests/fixtures/api_v1/info.json` (ten ports; `cad` and `raster` are `hello`; `no_keys: true`).
  Every fixture named in this spec is in that folder.

**`GET /api/projects`** (API.md "GET /api/projects"). When the shell mounts, and again whenever the route names a
project id that the loaded list does not hold (a project just uploaded). Fields: `projects[].id` (option value),
`name` and `created_at` (option label `<name> · <formatTime(created_at)>`), newest first as the API gives them.
`state`, `files`, `drawings` are not shown in the picker (the ingest screen shows them). Fixture:
`project_list.json`.

**The client** (`frontend/src/api/client.ts`). Every function takes an optional last argument `opts` with
`signal?: AbortSignal` (and the query flags listed), builds a relative URL, and resolves with the parsed JSON typed
as below or rejects with `ApiError`. Path ids go through `encodeURIComponent`; query strings are built with
`URLSearchParams`; a boolean flag is sent as `true`/`false` only when the caller passes it.

| Function | Request | Resolves |
| --- | --- | --- |
| `getInfo(opts?)` | `GET /api/info` | `Info` |
| `uploadProject(file: File, opts?)` | `POST /api/projects?name=<file.name>`, body the `File`, header `Content-Type: application/octet-stream` | `Started` |
| `startSample(opts?: {fresh?: boolean, signal?})` | `POST /api/projects/sample[?fresh=true\|false]`, no body | `Started` |
| `listProjects(opts?)` | `GET /api/projects` | `ProjectList` |
| `getProject(projectId, opts?)` | `GET /api/projects/{project_id}` | `ProjectView` |
| `getTrace(projectId, fileId, opts?)` | `GET /api/projects/{project_id}/files/{file_id}/trace` | `FileTrace` |
| `getProjectQuestions(projectId, opts?)` | `GET /api/projects/{project_id}/questions` (#121) | `ProjectQuestions` (`{project_id, questions: AskedQuestion[]}`, newest first; each `{question, answer, unit, drawing_id, at, refused}`) |
| `getProjectTrace(projectId, opts?)` | `GET /api/projects/{project_id}/trace` (#120) | `ProjectTrace` (`{project_id, files: FileTrace[]}`, files in upload order) |
| `getProjectReview(projectId, opts?)` | `GET /api/projects/{project_id}/review` | `ProjectReview` |
| `getDrawing(drawingId, opts?: {project?: string, signal?})` | `GET /api/drawings/{drawing_id}[?project=<project_id>]` (a screen inside a project passes it, so `file` and `reader.source` are that project's names; API.md "GET /api/drawings/{drawing_id}?project=") | `DrawingView` |
| `getModel(drawingId, opts?)` | `GET /api/drawings/{drawing_id}/model` | `Record<string, unknown>` (extraction_v1; not typed in OpenAPI) |
| `askQuestion(body: AskRequest, opts?)` | `POST /api/ask`, JSON body sent as given (`project_id` optional in `AskRequest`; the caller sets it from the route) | `AnswerView` |
| `getTakeoff(drawingId, opts?: {zeros?, project?, signal?})` | `GET /api/drawings/{drawing_id}/takeoff[?zeros=][&project=]` | `Takeoff` |
| `postReview(drawingId, edit: Edit, opts?: {zeros?, project?, signal?})` | `POST /api/drawings/{drawing_id}/review[?zeros=][&project=]`, JSON body | `Takeoff` |
| `postSignoff(drawingId, body: SignOffRequest, opts?: {zeros?, project?, signal?})` | `POST /api/drawings/{drawing_id}/signoff[?zeros=][&project=]`, JSON body | `Takeoff` |
| `postRelevance(projectId, fileId, body: RelevanceRequest, opts?: {signal?})` | `POST /api/projects/{project_id}/files/{file_id}/relevance`, JSON body (0010, file-triage.md) | `FileStatus` |
| `readAsPlan(projectId, fileId, by, opts?: {signal?})` | `POST /api/projects/{project_id}/files/{file_id}/triage`, JSON body `{class: 'floor_plan', by}` (#166, 202) | `FileStatus` (queued) |

URL builders (no request; for `<img src>` and `<a href download>`):

| Function | Returns |
| --- | --- |
| `pageUrl(drawingId, page: number, width: PageWidth = 1600)` | `/api/drawings/{drawing_id}/pages/{page}.png?width={width}` |
| `previewUrl(projectId, fileId, width: PageWidth = 1600)` | `/api/projects/{project_id}/files/{file_id}/preview.png?width={width}` |
| `takeoffCsvUrl(drawingId, opts?: {zeros?, project?})` | `/api/drawings/{drawing_id}/takeoff.csv[?zeros=][&project=]` |
| `evidenceUrl(drawingId, question: string, opts: {width?: PageWidth, project?: string} = {})` | `/api/drawings/{drawing_id}/evidence.png?question={question}&width={width, default 1600}[&project={project_id}]` (API.md "GET …/evidence.png"; `question` encoded by `encodeURIComponent`; `project` from a screen inside a project, so the picture carries that project's review edits and sign-offs, backend #90) |

`PageWidth = 400 | 1600 | 3200` (API.md: thumbnail, view, zoom), so another width does not type-check. The width is
always in the URL, the default included, so the browser cache sees one URL per image. Which width to load for a
display size is the viewer spec's rule.

JSON bodies are sent with `Content-Type: application/json`. Takeoff keys travel in JSON bodies (`quantity`), never
in a path, so the client encodes none; a key that goes into a hash route (`?q=`) is encoded by `routeHref` (below).

**Formatting** (`frontend/src/api/format.ts`; one rule for every screen, asked for by viewer.md, engineer.md and
surveyor.md):

- `formatValue(value: number, unit: string | null): string`: unit `count` or null → the integer
  (`String(Math.round(value))`), no unit text; any other unit → exactly 2 decimals (`value.toFixed(2)`), `.` as
  decimal point, no grouping, then the unit: `m` " m", `m2` " m²", `m3` " m³", `ft` " ft", `ft2` " ft²", any other
  unit " <unit>" as is. Examples: `2, "count"` → `2`; `52.27, "m2"` → `52.27 m²`; `22.401, "m2"` → `22.40 m²`;
  `30.0, "m2"` → `30.00 m²`. A null value or a string answer (schedule) is the caller's (shown as text, as is).
- `readerName(id: string | null | undefined): string`: a reader id (API values in `/api/info` `readers` and
  `DrawingView.reader`) as a plain label: `composite` "image reader", `pdf` "PDF vector reader", `ifc` "IFC model",
  `templates` "question templates", `hello` "not read", `dev` "best estimate from dev answers", `r3` "photo
  rectifier", `gemini` "Gemini", `off` and `False` "off", `True` "on", `none` "none", null and undefined "no reader" (a sentence like "none read …" would mislead); any other
  id as is (as text). QA R2 qa-3.
- `methodName(id: string | null | undefined): string`: a measuring-method id (backend `MeasureMethod`, e.g. a
  conflict's `values[].method`) as a plain label, in the backend's own words (`app/core/review/proof.py`
  `METHODS`) without the article: `printed_label` "printed room areas", `polygon_x_scale` "room outlines × sheet
  scale", `plan_drawing` "sheet", `parser` "sheet text", `detector` "detector", `ifc_model` "IFC model",
  `schedule` "schedule", `printed_total` "printed total", `summed_rooms` "sum of rooms", `scale_text` "printed
  scale", `scale_bar` "scale bar", `dimension_lines` "dimension lines", `annotation` "annotation", `other` "other
  method"; null and undefined "no method"; any other id as is (as text). QA R3.
- `formatTime(iso: string): string`: `YYYY-MM-DD HH:MM UTC`, read in UTC whatever the browser's zone
  (`2026-11-14T08:00:00+00:00` → `2026-11-14 08:00 UTC`). Used for `created_at`, `signed.at`, `settled.at`.
- Cost, latency, score and status words stay in the screens' own `format.ts` / `words.ts` (engineer, surveyor),
  which import these two for values and times.

**Errors.** `ApiError extends Error` with `status: number`, `code: string`, `detail: string`, `errors?: unknown[]`,
and `message = "<detail> (<code>)"`. Parsed from every non-2xx response:

- body is JSON with string `detail` and `code` (API.md "Errors", fixture `error.json`): those, plus `errors` when
  present (422 `validation`);
- any other body (not JSON, an HTML proxy page, JSON without those fields): `code` `http-<status>`, `detail`
  `the server answered <status>`;
- `fetch` itself rejects (server down, no network): `status` 0, `code` `network`, `detail`
  `cannot reach the server`;
- an aborted request (the caller's `signal`) rejects with the browser's `AbortError` unchanged, not an `ApiError`,
  so screens can ignore it.

`ErrorBody` is written by hand in `errors.ts` (`{detail: string; code: string; errors?: unknown[]}`): the backend
does not declare it in `/openapi.json` (Open points).

**Types.** `types.ts` re-exports `components["schemas"][...]` from `schema.d.ts` under the same names: `Info`,
`Limits`, `Started`, `ProjectList`, `ProjectSummary`, `ProjectView`, `FileStatus`, `DrawingEntry`, `Rendering`,
`FileTrace`, `ProjectTrace`, `ProjectQuestions`, `AskedQuestion`, `StageTrace`, `ProjectReview`, `DrawingReview`, `ConflictEntry`, `DrawingView`, `PageView`,
`Normalised`, `Reader`, `Suggestion`, `AskRequest`, `AnswerView`, `Refusal`, `MarkView`, `Row`, `Scope`,
`RuleText`, `QuantityConflict`, `Settled`, `SignOff`, `Proof`, `Takeoff`, `Edit`, `SignOffRequest`. These are the
schema names `/openapi.json` has on main 5092dc3 (checked 2026-11-14 by dumping it); screens import from `src/api`,
never from `schema.d.ts`. When the coming confidence object lands (Open points), its schema name is added here.

**Type generation** (ENGINEERING §5; the scripts are the scaffold PR's): `schema.d.ts` comes from
`docs/api/openapi-v1.json`, or until that lands from `create_app().openapi()` dumped in `backend/` with uv (checked
on main 5092dc3: it runs offline, starts no server, needs no key and writes no file). `api:check` regenerates into a
temp file and fails, naming `src/api/schema.d.ts`, when it differs from the committed one.

**Fixtures.** `src/api/fixtures.ts` imports each `@fixtures/<file>.json` and exports it typed, one camelCase name per
file: `info: Info`, `projectStarted: Started`, `projectList: ProjectList`, `project: ProjectView`, `trace:
FileTrace`, `projectTrace: ProjectTrace`, `projectQuestions: ProjectQuestions`, `projectReview: ProjectReview`, `drawing: DrawingView`, `askRequest: AskRequest`, `answer`,
`answerArea`, `answerConfidence`, `answerModel`, `answerRefused: AnswerView`, `takeoff: Takeoff`, `reviewRequests:
Edit[]`, `signoffRequest: SignOffRequest`, `error: ErrorBody`. (A JSON import widens string unions, so each is cast
`as unknown as <Type>`; the backend's fixture test is what keeps the files true to the models.) Tests never write a
response shape a fixture already has.

**Fetch mock.** `src/test/mockApi.ts` exports `mockApi(routes)`: `routes` maps `"<METHOD> <path>"` (path without
query) to a JSON body (answered 200, 202 for the two POSTs that start a project), to `{status, body}` (an error or
another status), or to a function `(request: Request) => body | {status, body}`. It stubs `globalThis.fetch`,
records every request (`mockApi(...).calls`: method, URL with query, parsed JSON body or the raw body), and answers a
request no route matches with a thrown error naming it, so a test fails on an unexpected call. A second helper,
`never()`, returns a promise that does not settle, for loading states.

## States

| State | What shows | How to reach it on purpose |
| --- | --- | --- |
| Info loading | Strip: "Checking the server…" (`role="status"`). Screens render already; they do not wait for info. | `mockApi` answers `GET /api/info` with `never()`; in the browser, throttle the network. |
| Info error | Strip: "The server did not answer: `<detail>` (`<code>`)" and a Retry button that calls `GET /api/info` again. | Mock `{status: 500, body: error fixture}` or a rejected fetch; in the browser, stop the backend. |
| No-keys | Strip: "Running offline: no API keys, no models", on every route, the not-found view included. | `info.json` (`no_keys: true`); the backend today always says so. |
| Keys present | Strip without the offline text, "What runs" still there. | `info.json` with `no_keys` set to false in the test. |
| Hello reader | "What runs" lists the port as "not read". | `info.json` (`cad`, `raster` are `hello`). |
| Projects loading | Picker disabled, one option "Loading projects…". | `GET /api/projects` → `never()`. |
| Projects empty | Picker disabled, one option "No projects yet". | `{projects: []}`. |
| Projects error | Picker replaced by "Projects: `<detail>` (`<code>`)" and a Retry button. | Mock 500 / network error. |
| No project in route | Picker shows the placeholder option "Choose a project" selected; no view links. | `#/`. |
| Not found | `NotFound`: heading "Page not found", text "Nothing at `<hash>`" (as text), link "Go to the start" (`#/`). No request is made for it. | `#/nope`, `#/p/XYZ`, `#/p/<pid>/d/<did>` (no role). |
| Screen loading | `Loading` with the screen's label, e.g. "Loading the project…" (`role="status"`, `aria-live="polite"`). | per screen spec. |
| Screen error | `ErrorView`: heading, `detail`, "code: `<code>`", HTTP status when not 0, Retry when the screen passes `onRetry` and the error is not a 404; for a 404 (`status` 404) no Retry (asking again finds nothing) and a link "Back to workspaces" to `#/workspaces` (the project list; `#/` lists none since the Vellum round). `role="alert"`. | per screen spec; `error.json` for a 404. |

Refusal and set-aside are screen states (engineer, ingest): `ErrorView` is not used for them, since they come with
200.

## Layout

Reference: the mock (`demo/index.html`) has no global header; its workspace has the "Back to the chat" / "Send to
surveyor" buttons. The header replaces those with one place for the role switch. Colours and type follow the mock's
`style.css` tokens.

- **Desktop 1440x900.** One header row, 56 px: "Vellum" (link to `#/`) left; the project picker (max 320 px
  wide, shrinks with the header) next to it; the view links Ingest · Engineer · Surveyor centred (only on project, file and drawing routes);
  nothing on the right. Under it the info strip, one line, 32 px: offline text left, "What runs" right; open, it
  drops a two-column list (port, reader) under the strip, pushing content down (not over it). The route's screen
  fills the rest, max width 1440, no horizontal scroll.
- **Phone 390x844.** Header in rows: "Vellum"; the picker full width and never wider (a long project name is cut
  off in the closed select and shown in full in its open list, R1-5-4); the view links as three equal
  tabs full width, each at least 44 px high. The strip under them wraps the full offline text (no shortened form),
  and "What runs" is a full-width disclosure under it. No horizontal scroll
  at 390 px with the longest fixture name.
- The current view link has `aria-current="page"` and is bold with a 2 px underline, so it never relies on colour
  alone. Offline is said in words, not by a coloured dot.
- `<main id="main" tabindex="-1">` holds the screen; on a route change focus moves to it and the page scrolls to the
  top.
- `Credit` (props `{credit: string | null}`, from `GET /api/drawings/{id}` `credit`) renders one line of small
  text under every page of the drawing (API.md: "the licence credit to show under every page"): `Credit: <credit>`,
  as text, when it is a string, with "Credit:" exactly once (a field that already starts with "Credit:", any case,
  has that prefix stripped first) (a Stoa dataset file or a Commons demo photo, recognised by content); `Credit: none
  recorded for this file` when it is null (a user's own drawing, the synthetic sample): the line is always there,
  so a missing credit is visible, never silent. The viewer places it
  directly under each page image (viewer spec owns the placement); any screen that shows a drawing's page shows it.
  A long credit wraps; it is never cut off.

## Acceptance criteria

Router

- SH-1 `parseRoute` maps `""`, `"#"`, `"#/"` to home; `#/p/5e0c1a2b3d4f` to project; `#/p/5e0c1a2b3d4f/f/f3` to
  file; `#/p/5e0c1a2b3d4f/d/adeefbbcc17559fc/engineer` and `/surveyor` to workspace with that role. [unit]
- SH-2 `parseRoute` returns not-found for an id off its pattern (project 12 hex, file `f<digits>`, drawing 16 hex),
  a workspace route without a role, and any other path; one trailing `/` is accepted. [unit]
- SH-3 A `?` part after the path parses into `query` (`URLSearchParams`); `routeHref` builds the hash back, and the
  key `area:room|name=küche` round-trips through `routeHref` → `parseRoute` unchanged (the hash holds it
  percent-encoded). [unit]
- SH-4 Changing `location.hash` renders the matching screen without a reload; the browser Back button returns to the
  previous screen. [component] [e2e]
- SH-5 Unknown route `#/nope` shows "Page not found", the text "Nothing at #/nope" and a "Go to the start" link to
  `#/`; no request other than info and projects is sent. [component]
- SH-6 On a route change, focus is on `main#main`. [component]

Header and project picker

- SH-7 The header shows "Vellum" (round 2; was "Countersign") as a link to `#/` on every route, not-found included. [component]
- SH-8 The picker lists `project_list.json`'s project with the label `sample-project.zip · <date>` where the date
  is `2026-11-14 08:00 UTC`, whatever the browser's time zone. [component, `project_list.json`]
- SH-9 On `#/p/5e0c1a2b3d4f` that option is selected; choosing another option sets the hash to `#/p/<its id>`.
  [component]
- SH-10 On a route whose project id is not in the loaded list, `GET /api/projects` is sent again (exactly once per
  such id). [component]
- SH-11 Loading, empty and error states of the picker show as in States; Retry sends `GET /api/projects` again.
  [component]
- SH-12 A project name `<img src=x onerror=alert(1)>` shows as that literal text in the picker, and no `img`
  element is created. [component]
- SH-13 On a drawing route the view links Ingest, Conflicts, Chat, Surveyor point to `#/p/<pid>`,
  `#/p/<pid>/conflicts`, `#/p/<pid>/chat`, `#/p/<pid>/d/<did>/surveyor`; any `?q=` on the current route is kept on
  the Surveyor link. No link is named "Engineer" (Tudor 12:46).
  [component]
- SH-14 (superseded in the Vellum round by SH-56) The current view link has `aria-current="page"`, the others do not; on project and file routes only Ingest
  shows, current; on home and not-found no view links show. [component]

Info strip

- SH-15 `GET /api/info` is sent once when the app starts, not again on route changes. [component]
- SH-16 With `info.json`, "Running offline: no API keys, no models" is visible on home, project, file, workspace and
  not-found routes. [component] [e2e on the no-keys backend]
- SH-17 With `no_keys: false` the offline text is absent and "What runs" is present. [component]
- SH-18 "What runs" lists all ten ports of `info.json` with their labels; `CAD (DXF)` and `Scans and photos` read
  "not read", `Vector PDF` reads "PDF vector reader", `Photo rectifier` reads "none", `photo/sheet check` reads
  "off" (and "on" for `True`), `Questions` reads "question templates"; a port key not in the label list shows as is. [component, `info.json`]
- SH-19 While info is pending the strip shows "Checking the server…" with `role="status"`, and the route's screen is
  already rendered. [component]
- SH-20 Info 500 with `error.json`'s body shows "The server did not answer: no drawing 0123456789abcdef
  (not-found)"; Retry sends `GET /api/info` again and, on success, shows the offline text. [component]
- SH-21 `useInfo()` gives the screens `info.limits` (`upload_mb` 200, `question_chars` 2000 with `info.json`) and
  `null` before info has loaded. [component]
- SH-22 `uploadTooLarge(size, limits)` returns null for `200 * 2**20` bytes and a sentence naming both sizes in MB
  for one byte more. [unit]

API client

- SH-23 Each read function sends the method and path of its table row and resolves with the fixture body:
  `getInfo` (`info.json`), `listProjects`, `getProject`, `getTrace`, `getProjectTrace` (`project_trace.json`), `getProjectQuestions` (`project_questions.json`),
  `getProjectReview`, `getDrawing`, `getTakeoff`.
  [unit, `mockApi`, each named fixture]
- SH-24 `uploadProject(new File([bytes], "my plan #1.zip"))` sends `POST /api/projects?name=my%20plan%20%231.zip`
  with the file as body and `Content-Type: application/octet-stream`, and resolves with `project_started.json`.
  [unit]
- SH-25 `startSample()` sends `POST /api/projects/sample` with no query; `startSample({fresh: true})` sends
  `?fresh=true`; neither sends a body. [unit]
- SH-26 `askQuestion(askRequest)` sends `POST /api/ask` with the JSON body of `ask_request.json` and
  `Content-Type: application/json`, and resolves with `answer.json`; with `answer_refused.json` it resolves (200),
  it does not reject. [unit]
- SH-27 `postReview` sends each body of `review_requests.json` unchanged as JSON, `postSignoff` sends
  `signoff_request.json`, and both resolve with `takeoff.json`. [unit]
- SH-28 `getTakeoff(id)` sends no query; `getTakeoff(id, {zeros: true})` sends `?zeros=true`; the same holds for
  `postReview`, `postSignoff` and `takeoffCsvUrl`. [unit]
- SH-29 `pageUrl(drawing.id, 1)` equals `drawing.json`'s `pages[0].url + "?width=1600"`; `pageUrl(id, 2, 3200)` ends
  in `/pages/2.png?width=3200`; `pageUrl(id, 1, 800)` is a type error (checked by `tsc --noEmit` with
  `@ts-expect-error`). [unit]
- SH-30 `previewUrl("5e0c1a2b3d4f", "f2", 400)` is `/api/projects/5e0c1a2b3d4f/files/f2/preview.png?width=400`;
  `evidenceUrl("adeefbbcc17559fc", "How many doors are there?")` is
  `/api/drawings/adeefbbcc17559fc/evidence.png?question=How%20many%20doors%20are%20there%3F&width=1600`; with
  `{project: "5e0c1a2b3d4f"}` the same URL ends in `&width=1600&project=5e0c1a2b3d4f`, and with `{width: 400}` in
  `&width=400`. [unit]
- SH-31 A 404 with `error.json`'s body rejects with `ApiError` `status` 404, `code` `not-found`, `detail` "no drawing
  0123456789abcdef", `message` "no drawing 0123456789abcdef (not-found)". [unit]
- SH-32 A 422 body with `errors` keeps them in `ApiError.errors`. [unit]
- SH-33 A 502 with an HTML body rejects with `code` `http-502`, `detail` "the server answered 502". [unit]
- SH-34 A fetch that rejects gives `ApiError` `status` 0, `code` `network`; an aborted request rejects with an
  `AbortError`, not an `ApiError`. [unit]
- SH-35 Every function passes the caller's `signal` to `fetch`. [unit]

Generated types

- SH-36 `npm run api:check` exits 0 on a fresh checkout, and exits 1 naming `src/api/schema.d.ts` after its source
  gains a field or after `schema.d.ts` is edited by hand. [script, run once by the build worker]
- SH-37 `types.ts` exports every name of the Types list; `tsc --noEmit` passes. [type check]

Common views and text rule

- SH-38 `Loading` renders its label with `role="status"`. [component]
- SH-39 `ErrorView` with an `ApiError` shows its `detail`, "code: `<code>`" and the status; with `onRetry` a Retry
  button that calls it, except for a 404 (see SH-48); with a non-`ApiError` it shows the error's
  message and "code: client". It has `role="alert"`. [component]
- SH-40 `Credit` shows "Credit: none recorded for this file" for `drawing.json` (`credit: null`) and
  "Credit: `<text>`" for a string, the string as literal text (a credit `<b>x</b>` shows the tags). [component,
  `drawing.json`]
- SH-41 `eslint` fails on any `dangerouslySetInnerHTML` attribute or `.innerHTML` assignment in `src/`
  (`no-restricted-syntax`, in the scaffold's eslint config; this worker adds it there if the scaffold lacks it).
  [lint, proven by one fixture file in the lint test]

Layout

- SH-42 (superseded in the Vellum round by SH-60) At 390x844 the header, strip and a not-found page have no horizontal scroll, each view link is at least 44
  px high, and the current link is marked by `aria-current` and underline; same at 1440x900 on one row.
  [e2e screenshot, looked at]

Formatting

- SH-43 `formatValue` gives the four examples of "Formatting", `1.5, "ft2"` → `1.50 ft²` and `3, null` → `3`; `formatTime` gives
  `2026-11-14 08:00 UTC` for `project_list.json`'s `created_at` with the process time zone set to
  `Europe/Helsinki`. [unit]

Project scope (QA R1 batch 2: a drawing is shared by content across projects)

- SH-44 `getDrawing(id, {project: "5e0c1a2b3d4f"})` sends `GET /api/drawings/<id>?project=5e0c1a2b3d4f`;
  `getDrawing(id)` sends no query; both resolve with `drawing.json`. [unit, R1-PS-1]
- SH-45 `askQuestion({...askRequest, project_id: "5e0c1a2b3d4f"})` sends that body unchanged (with `project_id`);
  without `project_id` the body has none. [unit, R1-PS-2]
- SH-46 `getTakeoff`, `postReview`, `postSignoff` and `takeoffCsvUrl` with `{project: "5e0c1a2b3d4f"}` add
  `project=5e0c1a2b3d4f` to the query (after `zeros` when both are given); without `project` there is none
  (backend PR #74, R1-4-4: the takeoff's `file` names are that project's). [unit, R1-PS-3]

QA round 2 (qa-3 notes)

- SH-47 `readerName` gives each label of "Formatting" (`composite`, `pdf`, `ifc`, `templates`, `hello`, `none`,
  null and undefined "no reader", `False`) and an unknown id as is; "What runs" shows `readerName` of each value. [unit, component,
  R2-qa-3-1]
- SH-48 `ErrorView` for a 404 (an `ApiError` with `status` 404, whatever its `code`) shows no Retry even when the
  screen passes `onRetry`, and a "Back to workspaces" link to `#/workspaces` (pre-QA 12:02; was "Back to projects" to `#/`); any other error keeps Retry and has no such link.
  Ingest's project screen answered 404 shows it. [component, R2-qa-3-2]

QA round 3

- SH-49 `methodName` gives each label of "Formatting" for all fourteen `MeasureMethod` ids, "no method" for null
  and undefined, and an unknown id as is. [unit, R3-method]
- SH-50 `Credit` with "Credit: Plan © Example, CC BY 4.0" and with "Plan © Example, CC BY 4.0" both read
  "Credit: Plan © Example, CC BY 4.0" (also for a lower-case "credit:" prefix); null still reads "Credit: none
  recorded for this file". [component, R3-credit]

Vellum round (round 2)

- SH-51 `src/shell/shell.css` defines on `:root` every token of "Design tokens" with exactly its value (20 names).
  [unit: parse the CSS]
- SH-52 No CSS file in `src/shell/` uses a hex, `rgb(` or `hsl(` colour outside the `:root` token block, except
  the header glass `rgba(255,255,255,0.72)`, the hairline `rgba(0,0,0,0.06)` and the segmented item shadow.
  [unit: parse the CSS]
- SH-53 `parseRoute`: `#/workspaces` (and `#/workspaces/`) → `account`; `#/p/5e0c1a2b3d4f/conflicts` →
  `conflicts` with that `projectId`; `#/workspaces/x`, `#/p/XYZ/conflicts` and `#/p/5e0c1a2b3d4f/conflicts/x` →
  not-found; `#/p/5e0c1a2b3d4f?view=advanced` → `project` with `query.get('view') === 'advanced'`; `routeHref`
  round-trips all three. [unit]
- SH-54 `App` mounts `AccountScreen` (no props) on `#/workspaces` and `ConflictsScreen` with `projectId` on
  `#/p/<pid>/conflicts`; changing only `?view=advanced` on a project route does not remount `ProjectScreen`.
  [component, stub screens]
- SH-55 The header has one link named "Vellum" to `#/` holding the logo image (`alt=""`, `src` the bundled
  `vellum-logo.png`) and the text "Vellum"; a "Workspaces" link to `#/workspaces` with `aria-current="page"` only
  on that route; the project picker; the country picker; no user name or avatar. [component]
- SH-56 The view links per route are those of the Header table (none on home, account and not-found; Ingest,
  Conflicts and Chat on project, file, conflicts and chat; Ingest, Conflicts, Chat, Surveyor on workspace), with the
  hrefs given, and at most the current one has `aria-current="page"` (Chat on chat; none on the engineer route). Supersedes SH-14. [component]
- SH-57 Base classes exist in `shell.css` with the designs' values: `.v-card` (radius `var(--v-radius)`, shadow
  `var(--v-shadow)`), `.v-btn` (accent background, `border-radius: 980px`, `min-height: 44px`),
  `.v-btn--secondary` (`--v-fill`), `.v-pill` and its four tones, `.v-segmented`, `.v-page` and its three widths,
  `.v-title`, `.v-hero`. [unit: parse the CSS]
- SH-58 Focus and motion: `:focus-visible` on `a, button, select, input, textarea, summary, [tabindex]` sets
  `outline: 2px solid var(--v-accent)` with `outline-offset: 2px`; the only rule in `src/shell/` that sets `outline:
  none` is for `main[tabindex='-1']` (`:focus`, `:focus-visible`): App moves focus there on a route change, and it is
  not a control, so it draws no ring around the page (pre-QA 12:00);
  a `prefers-reduced-motion: reduce` block turns off transitions and animations for `*`. (The reduced-transparency
  block went with the glass, SH-62.) [unit: parse the CSS]
- SH-59 `body` uses `--v-bg`, `--v-text` and `font: 16px/1.5 var(--v-font)`; no stylesheet or font is loaded from
  another origin (`index.html` and `src/**/*.css` hold no `http` URL). [unit]
- SH-62 (round-2 QA) `.app-header` is sticky at `top: 0` with `background: var(--v-surface)` (no `rgba`
  background) and no `backdrop-filter`, and `z-index` ≥ 10; `:root` has `--v-header-h: 76px`; at ≤720 px the header is
  `position: static` and `--v-header-h` is `0px`. In the browser: at 1440 the header is 76 px high and scrolled
  engineer content does not show through it; at 390 the header scrolls away. [unit: parse the CSS; live check]
- SH-64 (fe-chat) `parseRoute('#/p/5e0c1a2b3d4f/chat')` (and with a trailing `/`) → `chat` with that `projectId`;
  `#/p/XYZ/chat` and `#/p/5e0c1a2b3d4f/chat/x` → not-found; `routeHref` round-trips it. `App` mounts `ProjectChat`
  with `projectId` on it; the header shows Ingest, Conflicts and Chat there, Chat marked current. [unit + component]
- SH-65 (checks) `getDrawingChecks('adeefbbcc17559fc', {pack: 'fi', project: '5e0c1a2b3d4f'})` sends
  `GET /api/drawings/adeefbbcc17559fc/checks?pack=fi&project=5e0c1a2b3d4f`; `getProjectChecks(pid, {pack: 'fi'})`,
  `getIssues(pid)` and `getIssues(pid, {pack: 'fi'})` send their table rows; each resolves with its backend fixture
  and passes the caller's signal; `issuesCsvUrl`/`issuesZipUrl` give the URLs with and without `?pack=`; a pack id
  with a space is percent-encoded (`%20`). [unit, mockApi]
- SH-66 (checks) `parseRoute`: `#/p/<pid>/checks` → `checks`, `#/p/<pid>/issues` → `issues` (trailing `/` accepted;
  `#/p/XYZ/checks`, `#/p/<pid>/issues/x` not-found); `packOf` reads `?pack`; `withPack('#/p/<pid>/d/<did>/surveyor?q=a',
  'fi')` keeps `q` and adds `pack`, `withPack(…, null)` removes it; `routeHref` round-trips both routes with `?pack`.
  [unit]
- SH-67 (checks) `App` mounts `ChecksScreen` with `{projectId, pack: 'fi'}` on `#/p/<pid>/checks?pack=fi` and `pack:
  null` without it, `IssuesScreen` with `{projectId, pack}`; changing only `?pack` does not remount. [component]
- SH-68 (checks) The header tabs per route are those of "Header tabs" (Checks only with a pack, or on the checks
  route), in that order, each href carrying `?pack=fi` when the route has it (Surveyor also `?q`), exactly the
  current one marked (none on the engineer route); the project picker's choice keeps `?pack`. [component]
- SH-69 (checks) Country picker: not rendered while info loads, with `rule_packs` absent or empty, or on home,
  account and not-found; with `info.json` (packs `ch-zh`, `fi`) on a project route: button "Country rules: none", popover "No checks"
  (pressed) and the pack (`country_name`, `name · version`), closing line "Choose a country…"; choosing the pack sets
  `?pack=fi` (keeping `?q`), renames the button "Country rules: Finland", and the closing line is the note verbatim;
  "No checks" removes `pack`; no request is sent by the picker; no `data-pending`; `src/shell/pending.ts` does not
  exist. Supersedes SH-61. [component]
- SH-70 (checks) At 390x844, 768x1024, 1024x768 and 1440x900 on a drawing route with a pack (six tabs): no horizontal
  page scroll, every tab ≥44 px high below 1100 px; the header is sticky only above 1100 px (`--v-header-h` 76px
  there, 0px below). [unit: parse the CSS; e2e fe-golden]
- SH-71 (follow-up) The country button never wraps: `.country-button` has `white-space: nowrap`, `.country` does
  not shrink (`flex: 0 0 auto`) and caps at `max-width: 240px`, `.country-name` ends in an ellipsis (`overflow: hidden`,
  `text-overflow: ellipsis`); at 1440x900, 1024x768 and 390x844 it is one line high. [unit: parse the CSS; browser]
- SH-72 (QA R5-c-4) With packs `[fi]` in info: `?pack=fi` shows the Checks tab once info has loaded; `?pack=xx`
  (not listed) shows none, its other tabs still carry `?pack=xx`; while info loads `?pack=fi` shows none; on
  `#/p/<pid>/checks?pack=xx` Checks shows, current. [component]
- SH-73 (triage) `postRelevance('5e0c1a2b3d52', 'f2', relevance_request.json)` sends `POST
  /api/projects/5e0c1a2b3d52/files/f2/relevance` with the fixture as the JSON body and resolves with the `FileStatus`;
  `types.ts` exports `Triage`, `Description`, `Relevance`, `Overrule`, `RelevanceRequest`; `fixtures.ts` exports
  `projectTriaged` and `relevanceRequest`. [unit, mockApi]
- SH-74 (triage) `readAsPlan('5e0c1a2b3d52', 'f2', 'Ana')` sends `POST /api/projects/5e0c1a2b3d52/files/f2/triage`
  with `triage_request.json` as the body and resolves with the 202's `triage_started.json`; `fixtures.ts` exports
  `triageRequest`, `triageStarted`, `fileReadAsPlan`; `types.ts` exports `TriageRequest`, `ReadAsPlan`. [unit, mockApi]
- SH-63 `index.html`'s `<title>` equals `PRODUCT_NAME` ("Vellum"). [unit]
- SH-61 The country picker: a button "Country rules: Finland" with `data-pending="country-rules"` and
  `aria-expanded="false"`; clicking opens the group "Building rules the agent follows" with Finland
  (`aria-pressed="true"`) and Switzerland and the line "Rules are not applied yet."; choosing Switzerland renames the
  button "Country rules: Switzerland", closes the group and sends no request; Escape closes it and focuses the
  button. With `country_rules` in `/api/info` those are listed instead of the mock. [component]
- SH-60 At 390x844 and 1440x900 on home, a project, the conflicts route, a workspace and `#/workspaces`: no
  horizontal scroll, the logo and "Vellum" visible, view links ≥44 px high on the phone; screenshots looked at.
  Supersedes SH-42. [e2e, fe-golden]

## Out of scope

- The screens themselves (home with upload and project list, project status, trace, engineer, surveyor, viewer):
  their specs. The shell only mounts them.
- `GET /health` (outside `/api`, not proxied): no client function.
- Showing any `confidence` value: the engineer spec's (Open points 10 gives the coming shape).
- Upload progress (fetch has no upload progress; the upload is to localhost or a hotspot), retries with backoff,
  request caching or a state library: plain `fetch` and React state.
- Polling helpers: ingest owns its 500 ms poll.
- Dark mode, i18n, auth (API has none), a service worker or offline caching.
- A workspace route without a role (`#/p/<pid>/d/<did>`) is not-found, not a redirect.
- The e2e CI job and the Playwright config: golden-path spec.

## Open points

1. **Screen components the shell mounts: final** (round 1, decision 8). `HomeScreen()`, `ProjectScreen({projectId})`,
   `FileTraceScreen({projectId, fileId})` in `src/ingest/`; `EngineerPage({projectId, drawingId, query})` in
   `src/engineer/EngineerPage.tsx`; `SurveyorScreen({projectId, drawingId, query})` in
   `src/surveyor/SurveyorScreen.tsx`; `query: URLSearchParams`. Each is mounted with `key` = the route's path
   without the query, so a new drawing or role starts fresh and a `?q=` change does not remount.
2. **`?q=` on workspace routes: settled.** The router keeps a `?q=` after the hash path, decodes it into `query`
   (SH-3) and the role links keep it (SH-13). Writing it is the screens' job: surveyor replaces it without a history
   entry (`history.replaceState` with `routeHref`); engineer's "Send to surveyor" links to it via `routeHref`.
3. **`ErrorBody` is not in the OpenAPI document.** FastAPI lists only its default `HTTPValidationError`.
   Recommendation: keep the three-field type hand-written in `errors.ts` (SH-31 tests it against `error.json`).
4. Settled (round 1, decision 1): CI runs through the generic `node` job; how `api:check` runs is the scaffold PR's.
5. **`evidence.png` draws "the answer's probability".** API.md says the image shows the answer's probability under
   the page. With the confidence change (point 10) that line must go from the image too. Decided (round 1, decision
   5): until the backend drops it, a screen offers `evidenceUrl` only for answers with `confidence` null.
6. **Fixture ids are fixed stand-ins** (`5e0c1a2b3d4f`, `adeefbbcc17559fc`, created 08:00, every `ms` 12.5), not
   what a live run gives: unit tests read values from the fixture objects, e2e tests never hard-code them. Import
   path: `@fixtures/<file>.json` via the alias, or the typed `src/api/fixtures.ts`. Missing fixtures (states no file
   shows): asked on board #14; derived fixtures until then.
7. Settled (round 1, decision 4): the "after" image of ingest's `BeforeAfter` gets `<Credit>` with `credit` from
   `GET /api/drawings/{drawing_id}`; none under the upload preview.
8. Settled (round 1, decision 4): a null `credit` shows "Credit: none recorded for this file" on every screen.
9. Settled (round 1, decision 2): `formatValue` uses 2 decimals and lives here; engineer and surveyor import it.
10. **Confidence becomes an object (pending the next backend PR, board #14).** Today `AnswerView.confidence`,
    `proof.confidence` and `line.confidence` are a number described as a probability (`answer_confidence.json`).
    Agreed change: `confidence` becomes `{signal, score, calibrated: false}`, where `score` is a raw model choice
    score, not a probability, and the "Probability this answer is right" line goes. This spec owns no display of
    it. For the client: regenerate with `npm run api:gen` when that PR lands, add the new schema's name to
    `types.ts`, and `fixtures.answerConfidence` follows the updated fixture. Rule for every screen (engineer owns
    the display): never label or format `score` as a probability or a percentage.
11. **Product name.** "Vellum" (Vellum round; was the mock's "Countersign"): one constant, `PRODUCT_NAME` in
    `strings.ts`, and the `<title>` of `index.html` (SH-63 keeps them equal).
12. Removed (round 1, decision 1): Node 24 is the scaffold's and CI's.
13. **Old token names.** The round-1 names (`--ink`, `--paper`…) stay as aliases of the `--v-*` tokens during the
    restyle. Recommendation: once every screen is restyled, a tree-wide test like SH-52 over `src/**/*.css` and the
    aliases removed (one PR, after QA).
14. **Five added tokens** (`--v-text-2`, `--v-ok-soft`, `--v-danger-soft`, `--v-accent-soft`, `--v-fill`): the
    common brief fixes fifteen names, but the designs use these five fills on every screen (pills, secondary
    buttons, icon tiles). Recommendation: accept them; otherwise screens would hard-code those colours.
15. **The view links stay** in the header (as a segmented control) although the designs' header has none: the
    golden-path e2e clicks "Engineer" and "Surveyor", and they are the only way between the ingest, conflicts and
    workspace screens of one project. Conflicts is added to them.
16. **Not in the API** (header): the country picker's building rules (`Info.country_rules`), mocked in
    `src/shell/pending.ts` (CHANGE 11:05), for Bogdan's backend to add. The avatar stays out by decision.
    Superseded by #139: the real `Info.rule_packs` (checks round).
17. **`getRulePacks`** (checks brief): not a request. `/api/info` already carries `rule_packs` and is loaded once by
    `InfoProvider`; a second fetch would duplicate it. Screens use `useInfo()` + `rulePacksOf(info)`. If the
    orchestrator wants the name `getRulePacks`, it can be that helper.
18. **`ProjectChecks` shape**: #142 says "the same per drawing" without naming the wrapper. Typed as
    `{project_id, pack, note, drawings: DrawingChecks[]}`; to confirm against record 0009 when the PR lands.
22. **`ProjectSummary.issues_open`** (13:44, null until done): a Workspaces list pill is the account screen's
    (account.md), not in this spec; whoever owns src/account then can add "<n> issues open" like "to review".
19. **Picker off project routes**: not rendered on home, account and not-found (no project to check, and the pack
    lives on project routes). Alternative: show it disabled there. Recommendation: hidden.
20. **Compact header up to 1100 px** (was 720): six tabs plus the pickers do not fit one row below ~1100 px. The
    alternative (a horizontally scrolling tab strip) hides tabs. Recommendation: the 1100 px breakpoint.
21. **`IssuesScreen` prop** is `pack?: string` and `ChecksScreen`'s is `pack: string | null`, as the brief fixes them;
    the shell passes `undefined` / `null` for no pack.

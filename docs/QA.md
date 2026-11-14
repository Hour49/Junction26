# QA plan

How we check the project before every merge to main and before the pitch. Written before the project was picked:
fill in the golden path (§1) as soon as the demo is sketched. The QA and fix brief templates for agent workers are in
[TEAM-AGENTS.md §10.3a](TEAM-AGENTS.md#103a-qa-brief-and-fix-brief) and aren't repeated here. Engineering rules:
[ENGINEERING.md](ENGINEERING.md).

## 1. Golden demo path

The exact flow we show the judges, as numbered steps, with what the screen must show after each. It is the demo
script, the end-to-end test and the smoke test in one. Keep it to what the 3-minute pitch and the 2-minute peer-review
demo show.

| # | Action | Expected (what the screen shows) | Runs on fakes? |
| --- | --- | --- | --- |
| 1 | Open the app at `http://127.0.0.1:4173/#/` | Home: drop zone, "Choose a file", "Try the sample project", earlier projects; the strip "Running offline: no API keys, no models" | yes |
| 2 | Click "Try the sample project" | `#/p/<id>`: "sample-project.zip", files finish one by one, then "Done", "11 of 11 files finished", cost $0.00; every file row has its state in words (no keys: 3 ready, 4 flagged, 2 set aside, 2 text only; with keys the raster reader reads the two scans: 5 ready, 2 flagged, 2 set aside, 2 text only); 5 drawings | yes |
| 3 | Click the file `plans/flat-b.pdf` | Its trace: "flagged", "1 conflict between the two methods (room_area) ...", stages unpack to write, `second_count` "5 quantities measured twice, 1 conflict" | yes |
| 4 | Click "Open the drawing" | Engineer: "plans/flat-b.pdf", how it was read, page 1 of the plan, suggested questions | yes |
| 5 | Click "How many doors are there?" | `2`, "door count", marks 1 and 2 on the doors, the counting rule, "One method", cost $0 | yes |
| 6 | Ask "What is the net floor area of room 1.01?" | `30.00 m²`, the kitchen shaded, "Methods disagree": "22.40 m² by room outlines × sheet scale", "30.00 m² by printed room areas", and the rule that kept 30.00 | yes |
| 7 | Ask "What colour is the roof?" | "I can't answer that from this drawing.", the reason in words (no code shown), questions it can answer; no number | yes |
| 8 | Click "Surveyor" | The project's conflicts: "area of room (name 1.01)" and "area of room (name Küche)", each "plans/flat-b.pdf", "22.40 m² vs 30.00 m²", "decided by rule" | yes |

Steps after the QA blitz (surveyor settle, sign-off, verified answer, CSV export) are in
[golden-path.md](specs/frontend/golden-path.md) "User flow", steps 8-12.

- Demo data: the synthetic sample archive (`cd backend && uv run python scripts/make_sample_archive.py`, writes
  `data/samples/sample-project.zip`, gitignored). No partner data.
- Start command: `cd backend && uv run uvicorn app.main:create_app --factory`, then
  `cd frontend && npm ci && npm run build && npm run preview`; open `http://127.0.0.1:4173/#/`.
- Offline fallback: the same commands with no keys in `backend/.env`; every step works and the strip reads "Running
  offline: no API keys, no models".
- Demo machine and its owner: `<name>` (one owner at a time)

An automated end-to-end test runs this path on the fakes in CI (Playwright for a web UI). Run it against the real
services by hand before each demo build.

## 2. Smoke checklist

Before every merge to main and before the pitch. About 10 minutes. Every box is checked by running something, not by
reading code.

- [ ] The check command (ENGINEERING.md §6) is green locally, and CI is green on the PR.
- [ ] A fresh clone in a temp dir starts the app by following the README steps alone. No step depends on a file
      that isn't in the repo or on the current directory.
- [ ] The golden path (§1) works end to end on the production build with the real services.
- [ ] The same with no keys: the app falls back to the fakes and says so.
- [ ] No errors in the browser console or the server log during the run.
- [ ] Screenshots of each golden-path screen at 390x844 and 1440x900, each one opened and looked at.
- [ ] Nothing secret or private in the diff: the pre-commit hook and the CI secret scan passed; no partner data,
      personal data or home paths.
- [ ] `docs/KNOWN.md` is up to date (§4).

## 3. UI checks

- Test the production build (build plus preview, or the deployed URL), never the dev server: dev mode hides failures
  that only happen in the build.
- Take screenshots at 390x844 (phone) and 1440x900 (desktop), and open each one. Judge them as a designer would:
  alignment, overflow, cut-off text, contrast, tap targets. "It rendered" is not a pass.
- Every screen has an empty, a loading and an error state, and each is reached once on purpose (no data, a throttled
  network, the service down or offline mode).
- Status is never shown by colour alone. Stale or mocked data is labelled as such.
- Before designing screens, write down the 3-5 rules that follow from what the user needs (e.g. "the next action is
  always visible", "every answer shows its source"), and check the screens against them.
- No template look: no stock gradient hero, no placeholder copy, no emoji headings.

## 4. Known issues: `docs/KNOWN.md`

One file lists what we already know, so testers don't re-report it and fixers don't re-investigate it. Create it with
the first known issue. Testers read it before each round. Two lists, one line per entry:

```markdown
## Known issues
- K3 · major · <owner> · Upload over 10 MB times out with no error message (Sat 21:10)

## Intended, not bugs
- Login is one fixed demo account; there is no sign-up.
```

Known-issue fields: id, severity (blocker / major / minor), owner, one-line description, when found. An entry is
removed when its fix is merged; the issue or PR keeps the history. "Intended, not bugs" lists behaviour that looks
wrong but was chosen, which stops false reports.

## 5. Finding template

One entry per bug, in the QA report (`.agents/qa/<area>.md`) or as a GitHub issue with the
[bug template](../.github/ISSUE_TEMPLATE/bug.md) (the issue number is then the id):

```text
id:        <area>-<n>          e.g. upload-3
severity:  blocker | major | minor
where:     <URL or screen>, build or commit <sha>
steps:     1. ...  2. ...  3. ...
expected:  <what should happen>
actual:    <what happens>
evidence:  <screenshot path, log line, request and response>
repro:     <path of the repro script>
```

Severity: **blocker** breaks the golden path or loses data; **major** a visible feature is wrong or a state is
missing; **minor** cosmetic, or off the demo path. A tester's guess at the cause is labelled as a guess.

## 6. Repro scripts

Every bug gets a repro script (a test, a Playwright script, a curl call) that exits non-zero while the bug is there
and 0 once it is fixed.

- The fixer runs it before the fix (fails) and after (passes).
- For demo-critical bugs, a different worker reruns it against the merged code; the fixer's own run doesn't count.
- The fix is checked against the original repro, not a neighbouring case.
- A bug nobody can reproduce is held, not marked fixed.
- Repro scripts for real bugs become regression tests in the suite.

Each QA worker's brief (template in TEAM-AGENTS.md §10.3a) also says: read `docs/KNOWN.md` before filing, and keep a
notes file (`.agents/qa/<area>-notes.md`) current so a fresh agent can take over mid-round.

## 7. QA rounds against the deadlines

Times are Europe/Helsinki. Final submission is Sun 15 Nov 10:00; aim to submit by 09:30.

1. **Fri ~22:00, plan review** (right after the challenge pick). A second agent spends 30 minutes reviewing the
   idea, the demo plan and the interfaces. Each finding is checked against the brief or the code before it counts.
   Golden path (§1) drafted.
2. **Fri 23:59, preliminary submission.** Project registered; the README says what it is.
3. **Sat ~14:00, first end to end.** The golden path runs end to end on the fakes, even if it looks rough. From here
   on, every merge keeps it working.
4. **Sat ~20:00, full QA round.** QA workers on the production build (§3), findings filed (§5), one fix round,
   repros rerun by a different worker (§6).
5. **Sat night, fresh-clone rehearsal.** Someone who didn't write the code follows the README and the golden path on
   a clean checkout. Fix what that turns up.
6. **Sun 06:00, feature freeze.** Demo build tagged. After this, only bug fixes with a repro, each one through the
   smoke checklist. A nicer look is not a reason to change the demo build.
7. **Sun 08:00, final run.** Smoke checklist (§2) in full on the tagged build, offline fallback included; the
   golden-set script (ENGINEERING.md §2) if we have scored output; README and submission text checked against what
   runs.
8. **Sun ~09:30, submit.** Submission form, with the pre-existing work list (ENGINEERING.md §10).
9. **Sun morning, peer review, then the pitch.** Demo from the tagged build only, with the offline fallback ready on
   the demo machine.

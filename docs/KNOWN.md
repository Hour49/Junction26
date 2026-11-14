# Known issues

What we already know, so QA does not re-report it and fixers do not re-investigate it (docs/QA.md §4). One line
per entry; an entry goes when its fix is merged.

## Known issues
- K2 · minor · frontend · The viewer's conflict tags A and B overlap when both methods' boxes start at the same
  corner (flat-b room 1.01) (Sat 05:05)
- K3 · minor · frontend · On a phone the surveyor's drawings and conflicts list is not collapsed; the drawing starts
  below the fold (Sat 05:05)
- K5 · minor · backend · An estimated raster area (RASTER_SCALE=priors) can be far off while printing a narrow band
  when the detector finds the wrong doors: golden colorful-10706 living room +74% at ±24% (13 doors),
  high_quality-17 +100% at ±40% (1 door), colorful-7513 kitchen −37% at ±24% (10 doors, QA R3, before #347). The
  band is a 68% one, honest on val overall. #347 widens it to a fitted ±14.2% only on pages with 5 or more doors
  whose widths disagree (spread >= 0.20); every other door-count group, 1-door pages included, keeps the old band,
  and doors that agree on a wrong width are not caught (Sat 06:45; Sun 01:30)
- K6 · minor · backend · An IFC uploaded with its PDF sheets but without their SVG renderings is not linked to
  them: no sheet-vs-model conflicts (vitoria plan-02-p1.pdf: 4 conflicts beside its SVG, none without; QA R6-c-2).
  Measured 2026-11-15: from the PDF alone the wall, column, slab, railing, beam and stair counts cannot be told
  apart (one drawing style), and comparing the doors, windows and rooms the PDF reader counts would keep 52 of the
  235 dataset conflicts and add 29 false ones, so the link stays SVG-only. Every dataset sheet ships with its SVG;
  only an upload without it is affected. Without the link the sheet has no wall geometry either, so no wall edit can
  be proposed on it and the services follow-up has nothing to follow (#413, read from the code, not run) (Sat 15:10)
- K8 · limit · backend · Sketches: we claim no door counting. On 14 hand-drawn sheets (mostly historical, 2026-11-14
  fail test, `prototypes/handdrawn/`) the door count was in range on 0 of 10 sheets with doors; windows 4 of 10, only on
  clean line drawings. Every door, window, room and WC count asked for a check; the exception is plans on a page, sure
  and wrong 3 of 14 times. The gold is one person's ranges, so there is no hand-drawn accuracy number.
- K9 · cost · backend · The double-check policy asks about many answers: on the CubiCasa test pages 62.1% of
  answers are flagged to catch 97.0% of the wrong ones, with 98.98% of the unflagged ones exact (docs/GOLDEN.md,
  the test certificate; on val 55.1% flagged, 96.0% caught).
- K11 · limit · backend · Evidence text drops a street address's house number and postal code by regex
  (`without_addresses`, decision 0010), firms' too; not caught: a street with no street word in the list (Broadway,
  Esplanadi 5), a -platz/-weg street with no postal code after it (kept so Parkplatz 12, Fluchtweg 2 keep theirs),
  a number before a Nordic/German street, a postal code or ZIP on another line than its street, a ZIP with no state
  before it, an English street followed by a lowercase word (200 dataset PDFs: 52 of 52 changed lines were real
  addresses; #259) (Sat 19:20)
- K12 · limit · backend · Memory on the live host's 8 GB cap: a cold upload of 6 images peaks at 7.43 GB summed over
  the backend's processes in the demo config (#381). #405 holds a big greyscale page once (the image readers' peak
  on a 138 Mpx scan: 11.13 to 2.84 GB cold), but what a reading leaves resident after an upload is not given back
  yet. So
  INGEST_GROUPS_IN_FLIGHT stays 1 on main: at 4, a cold upload under a 10 GB cap swapped twice what main did
  (#395) (Sun 01:30)
- K13 · minor · backend · A services proposal on a services IFC that was set aside at upload carries the first 16
  characters of the file's sha256 as its drawing id: the edit card's picture works, a lookup by drawing name may
  show the bare id (#413) (Sun 01:30)
- K14 · limit · backend · The chat's services tools read only services models built ahead by `app.cli services
  build` (`adapters/services_agent_tools.py` `_ProjectModels`: "never built here"); nothing builds one at upload, so
  a user's own services IFC is not offered to them. The follow-up after a plan edit reads the IFC itself, in a
  capped child process (#399), so it does not depend on the build (Sun 01:30)

## Intended, not bugs
- The engineer's thread lives in memory: a reload or another drawing starts it empty (engineer.md).
- An answer card is a snapshot: after a sign-off, ask again to see "Verified by …" (golden-path.md OP 4).
- "Try the sample project" always starts from scratch (`fresh=true`): it resets the last sample's review edits and
  sign-offs.
- The answer's model score is never shown as a probability or percent; with no keys there is none.
- The sign-off name is what the surveyor types; there is no login (decision 0001).
- The app has a light theme only and does not follow the system's dark mode (#403).
- The pen (draw mode) is greyed out on a drawing that cannot be drawn on, with the reason: a scan or photo, a
  building model with no drawn plan, a sheet with no scale, rooms without outlines or no wall geometry (#407, #416).
- A scan with no detected door gets no area scale from Carbon's door boxes (SCALE_CARBON_DOORS stays off), and
  services drawn on a scan or photo are not read (the picture readers are not switched on). The measured reasons
  are in [PIPELINE.md §4](PIPELINE.md#4-settings-the-demo-config-and-what-stays-off).

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
  high_quality-17 +100% at ±40% (1 door), colorful-7513 kitchen −37% at ±24% (10 doors, QA R3). The band is a 68% one, honest on val overall (Sat 06:45)
- K6 · minor · backend · An IFC uploaded with its PDF sheets but without their SVG renderings is not linked to
  them: no sheet-vs-model conflicts (vitoria plan-02-p1.pdf: 4 conflicts beside its SVG, none without; QA R6-c-2)
  (Sat 15:10)
- K7 · minor · frontend · The project chat lists only the drawings that answered; refused ones are only counted in
  the note, not named (ProjectChat.tsx `answering`; QA R6-c-3) (Sat 15:10)
- K8 · limit · backend · Sketches: we claim no door counting. On 14 hand-drawn sheets (mostly historical, 2026-11-14
  fail test, `prototypes/handdrawn/`) the door count was in range on 0 of 10 sheets with doors; windows 4 of 10, only on
  clean line drawings. Every door, window, room and WC count asked for a check; the exception is plans on a page, sure
  and wrong 3 of 14 times. The gold is one person's ranges, so there is no hand-drawn accuracy number.
- K9 · cost · backend · The double-check policy asks about many answers: 55.1% of val answers flagged to catch
  96.0% of the wrong ones, with 98.95% of the unflagged ones exact (docs/GOLDEN.md, double-check policy; val
  estimates, test certificate still to come).

## Intended, not bugs
- The engineer's thread lives in memory: a reload or another drawing starts it empty (engineer.md).
- An answer card is a snapshot: after a sign-off, ask again to see "Verified by …" (golden-path.md OP 4).
- "Try the sample project" always starts from scratch (`fresh=true`): it resets the last sample's review edits and
  sign-offs.
- The answer's model score is never shown as a probability or percent; with no keys there is none.
- The sign-off name is what the surveyor types; there is no login (decision 0001).

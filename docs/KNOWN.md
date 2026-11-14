# Known issues

What we already know, so QA does not re-report it and fixers do not re-investigate it (docs/QA.md §4). One line
per entry; an entry goes when its fix is merged.

## Known issues
- K2 · minor · frontend · The viewer's conflict tags A and B overlap when both methods' boxes start at the same
  corner (flat-b room 1.01) (Sat 05:05)
- K3 · minor · frontend · On a phone the surveyor's drawings and conflicts list is not collapsed; the drawing starts
  below the fold (Sat 05:05)
- K4 · minor · backend · On a one-storey sheet, settling, keeping or signing a plain row (IFC sheet P1 "window
  count") leaves its storey twin ("window count (storey p1)") disputed; the review lists only the plain row, but a
  question about the storey still shows the dispute (Sat 06:15)
- K5 · minor · backend · An estimated raster area (RASTER_SCALE=priors) can be far off while printing a narrow band
  when the detector finds the wrong doors: golden colorful-10706 living room +74% at ±24% (13 doors),
  high_quality-17 +100% at ±40% (1 door). The band is a 68% one, honest on val overall (Sat 06:45)

## Intended, not bugs
- The engineer's thread lives in memory: a reload or another drawing starts it empty (engineer.md).
- An answer card is a snapshot: after a sign-off, ask again to see "Verified by …" (golden-path.md OP 4).
- "Try the sample project" always starts from scratch (`fresh=true`): it resets the last sample's review edits and
  sign-offs.
- The answer's model score is never shown as a probability or percent; with no keys there is none.
- "Credit: none recorded for this file" on the synthetic sample: it has no licence credit (it is ours).
- The sign-off name is what the surveyor types; there is no login (decision 0001).

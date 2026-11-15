# PDF accuracy research (board #627, 2026-11-15)

Tudor asked Beatrice's agents for in-depth research on raising Vellum's accuracy on PDFs. Three agents, one angle
each; brief in `BRIEF.md`. Builds on `docs/research/lit-campaign/`, doesn't repeat it.

| File | Angle |
| --- | --- |
| `vector-cad.md` | Vector CAD/Revit sheets: views, layers, symbols, SHX text (A-701 at 0/4) |
| `scanned.md` | Scanned/raster PDFs: printed totals, scale arbitration, door prior, OCR |
| `related.md` | Schedules, legends, room-name matching, takeoff tools, VLM benchmarks, sanity checks |

## ADOPT NOW (small, own code or pypdfium2, before the freeze if someone takes them)

1. A printed total that names exactly the asked subject ("48 DORMS") becomes the answer; the drawn count is the
   check (scanned #1, related #3). Carbon already reads it; `printed.py` keeps it only as a second value.
2. Scale arbitration: the T2 ~1.8x area miss matches a 4/3 linear slip ((4/3)^2 = 1.78, neighbouring
   architectural scales). Compare scale candidates by known ratios; a printed area total decides (scanned #2).
   Five-minute check first: log the three m/px values on T2 and divide them.
3. Door prior by unit system: 0.914 m imperial vs 0.794 m (Finnish-fitted) metric (scanned #3).
4. Printed area totals are gross, our rooms net: check summed rooms / printed gross in ~0.6-1.0, outside it the
   answer is disputed; compare a printed gross with the plan outline, not the room sum (scanned #4, related #1-2).
5. Split multi-view sheets: view title = text right above a scale note; type from title words (vector-cad #1, #4).
6. Read AutoCAD "SHX Text" annotations as text; read OCG layer names and count fixture layers (vector-cad #2, #3;
   layers present in 2/7 public sets, never in Revit exports).

## NEXT

Last-noun room-name matching with labels listed (related #4); tiled PP-OCR as second reader, F1 0.81 → 0.89 on
49 engineering drawings (scanned #6); repeated-shape-group counting per view, line-based for Revit (vector-cad #5);
img2table for raster schedules (related #5); dimension strings with RANSAC (scanned #8).

## Not verified

Own-run numbers are from 7 public US bid sets, a few sheets each, not Stoa. The 4/3 explanation is arithmetic only.
The 0.6-1.0 range is a starting guess: set the pass/fail line before testing it and check that the Swiss vector
sheets (20/20) still pass.

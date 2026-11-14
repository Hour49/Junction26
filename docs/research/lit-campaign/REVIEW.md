# Which of our 18 literature reports are good (research orchestrator, 2026-11-14 01:31)

Bogdan, 01:21: "please look in detail at each of the reports and find out which are actually good".
Scope: the 18 angle reports of L1, L4, L6, L7, L10, L12 (`.agents/research/lit-<scope>-<a|b|c>.md`), final versions
of 01:20. Tudor's 18 reports were not audited this way (their session logs are on his machine).

## How each report was checked

1. **Did the worker fetch what it cites?** From the workers' session logs (all sessions of a pane, restarts
   included): every arXiv id a report cites is classed as opened (the id is in the input of a fetching tool call),
   seen only (in a search result or citation list, never opened) or never (nowhere in its sessions).
2. **Are the quoted numbers in the papers?** For every report line that cites exactly one arXiv paper whose full
   text is on disk (arXiv server cache, browser dumps, the workers' own downloads: 447 papers), each decimal number
   on the line is searched in the paper's text, allowing for rounding and for fraction versus percentage.
   Limits: a line that mixes one arXiv paper with numbers from a vendor page or a paper without an arXiv id counts
   those as misses. I read eight flagged lines by hand: all eight were of that kind or rounding (83.69 quoted as
   83.7); none was a wrong number. So the rates below are a floor, not an error rate.
3. **By hand** (sources re-opened by me): Scatteract 89.2 / 83.8 / 70.7 (scale-c) exact; Raster2Seq code MIT,
   weights CC BY-NC 4.0, 88.7 on CubiCasa5K (floorplan-b) exact; arXiv 2608.25608 opening F1 "2.6x" (floorplan-b)
   consistent with 0.25 to 0.64; the SALI-FP numbers 0.630 / 0.763 / 0.661 / 0.207 (rooms-b, rooms-c) are in the
   paper text.
4. **By the mergers**: each scope's merger re-opened the sources of its top 10 (17 to 38 "re-checked" marks per
   merged report read so far) and recorded disagreements between the three reports.

Command: `python3 .agents/bin/review_audit.py <out.json>` (details per report, with every flagged line, in the JSON).

## Result

| Report | KB | Tool calls | arXiv cited | opened | seen only | never | numbers checked | found |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| floorplan-a | 211 | 767 | 70 | 70 | 0 | 0 | 210 | 93% |
| floorplan-b | 135 | 431 | 44 | 37 | 3 | 4 | 59 | 95% |
| floorplan-c | 94 | 748 | 98 | 98 | 0 | 0 | 220 | 95% |
| rooms-a | 171 | 758 | 103 | 58 | 45 | 0 | 79 | 91% |
| rooms-b | 153 | 426 | 47 | 38 | 9 | 0 | 283 | 92% |
| rooms-c | 154 | 544 | 60 | 53 | 7 | 0 | 219 | 82% |
| scale-a | 137 | 559 | 39 | 32 | 7 | 0 | 48 | 98% |
| scale-b | 161 | 455 | 36 | 30 | 6 | 0 | 49 | 82% |
| scale-c | 216 | 651 | 45 | 41 | 4 | 0 | 256 | 92% |
| vlm-a | 46 | 419 | 73 | 70 | 3 | 0 | 289 | 96% |
| vlm-b | 175 | 637 | 78 | 76 | 2 | 0 | 227 | 87% |
| vlm-c | 218 | 558 | 75 | 72 | 3 | 0 | 584 | 95% |
| trust-a | 220 | 511 | 135 | 98 | 37 | 0 | 357 | 94% |
| trust-b | 214 | 634 | 85 | 85 | 0 | 0 | 130 | 90% |
| trust-c | 245 | 515 | 153 | 117 | 36 | 0 | 139 | 94% |
| market-a | 219 | 518 | 23 | 18 | 5 | 0 | 55 | 64% |
| market-b | 185 | 447 | 70 | 64 | 6 | 0 | 261 | 99% |
| market-c | 113 | 369 | 21 | 18 | 3 | 0 | 54 | 78% |

## Reading of it

- **No report invents its sources.** Of 1,255 arXiv citations, 4 appear nowhere in the citing worker's sessions,
  all in floorplan-b: two in a "searched and found only these" sentence, and two low-ranked leads cited as
  "abstract" (Sketch2BIM 2510.20838, GATA2Floor 2605.11863). Treat those two as unverified.
- **Strongest on this evidence** (everything cited was opened or nearly, numbers found at 92% or more, many numbers):
  floorplan-a, floorplan-c, vlm-a, vlm-c, market-b, scale-c, rooms-b, trust-a. vlm-a is the shortest file (46 KB)
  but one of the densest: 73 papers, 289 checked numbers.
- **Good, with a caveat**: scale-a (98%, but only 48 numbers, and it sat ten minutes on a timer; its own source
  count is an estimate), floorplan-b (the 4 unseen ids above), rooms-a, trust-a and trust-c (36 to 45 papers cited
  from search results or citation lists without being opened; in all three they sit below an "Unverified leads"
  heading), trust-b (90%).
- **Not settled by this check**: market-a (64%) and market-c (78%). Their numbers come from vendor pages and
  medical reader studies cited on the same lines as one arXiv paper, which this check cannot tell apart; the
  17 misses of market-a are one such line. Their vendor claims need a hand check of the pages before the pitch
  quotes any of them.
- **Lower floor**: rooms-c and scale-b (82%), vlm-b (87%). The flagged lines I read were multi-source lines, but
  these three are the ones to spot-check first if a number from them carries a decision.

## Two rule breaches found while reviewing

- rooms-c opened three images of the preview dataset under `data/` to see what our sheets look like (its own
  reading log says so: read-only, nothing measured or copied). Its brief said not to open anything under `data/`.
  No split file and no answers were read. Its report is otherwise among the usable ones.
- scale-a's "22 of 50 sampled sheets carry printed areas" comes from a local review note, not from a tracked
  document. The merged scale report does not use it; do not quote it without re-measuring.

Because several angle reports quote dataset file names, only the six merged scope reports are published.

## Not done

- No report was read end to end by me (2.9 MB). The mergers were told to read all three of their scope in full; I read the
  audit and the flagged lines. The merged reports I have only grepped for re-check marks so far.
- Vendor and product claims (market scope) were not re-opened by me.

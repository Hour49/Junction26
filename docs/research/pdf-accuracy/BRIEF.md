# Brief: raise Vellum's accuracy on PDFs (board #627, Tudor asks Beatrice's agents)

Vellum reads building drawings (PDF, scans, IFC) and answers questions (counts, areas, rooms) with the answer marked
on the plan. Stack: Python 3.13 backend. Read `docs/ENGINEERING.md` §1 and `docs/research/lit-campaign/README.md`
first for context.

## Where accuracy stands (Tudor's QA round 4, Stoa preview data)
- Vector PDFs are strong (Swiss sheets 20/20, 6/6, 7/7; IFC counts 16/16).
- They lose on:
  - scanned PDFs/raster pages: CubiCasa 8/12, misses are estimates;
  - typical Revit CAD sheet (A-701 Restrooms) reads nothing: 0/4;
  - IFC exported to PDF: 5/6;
  - printed totals/tables ignored: sheet prints "48 DORMS" and a 26,562 SF area table, we answer 40 bedrooms
    and ~45% of the area;
  - scale on raster pages: scale bar vs door widths vs printed ratio disagree, areas ~1.8x off;
  - room names with partial/plural matches ('classrooms' vs "Secondary Classroom (Severe Needs)") get refused.

## Don't redo / ruled out
- The literature campaign in `docs/research/lit-campaign/` (IDEAS.md, SHORTLIST.md, REVIEW.md, conclusions-*,
  triage-*): skim it, don't repeat it; build on it.
- Not allowed in shipped code (licence or result): PyMuPDF, Ultralytics YOLO, Surya, AlbumentationsX
  (AGPL/GPL); generative super-resolution; deep vectorization of technical drawings (no weights);
  danielmevit/vecto (AGPL). Flag any other GPL/AGPL item as "research only".
- Never touch the Stoa data (`data/stoa/`), especially the sealed eval split.

## How to research
- Primary sources: arXiv papers (read the paper, not just the abstract), their code repos (check LICENSE and
  whether weights exist), vendor/standards docs (PDF 1.7/ISO 32000 for OCGs, text and fonts), commercial tool docs.
- Tools: WebSearch and WebFetch first. Use the Playwright browser only for pages fetch can't read (JS-heavy
  sites, PDFs viewers). The browser is shared with other agents: open your own tab (`browser_tabs` new) and check
  you are on it before each read; close it when done.
- Every finding needs: source URL, licence (code and weights), a measured number on data like ours (floor plans,
  CAD sheets, scanned drawings) with the dataset named, and a "how it would plug into Vellum" line with effort
  (S/M/L). No number found: say so.
- Mark each finding: ADOPT NOW (fits before the 09:00 EET freeze, small), NEXT (worth doing after), or SKIP (why).

## Output
Write ONLY your own file `docs/research/pdf-accuracy/<your-angle>.md` (in this worktree,
`/home/ubuntu/Repo/J26-pdf-research`). Top: 5-line summary and a ranked table (finding, verdict, number,
licence, effort). Then one section per finding. End: sources list. No commits, no board, don't edit other files.

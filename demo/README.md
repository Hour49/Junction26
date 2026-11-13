# demo/: clickable mock of the product

Static HTML, CSS and JS. No build step, no network, no dependencies. Open `index.html` in a browser.

Everything in it is synthetic. The two floor plans are drawn by `app.js` from a small data structure, and the
counts and areas on screen are computed from that same structure, so marks, lists and totals always agree. File
names, timings and costs are illustrative, not measured. Nothing from the Stoa dataset is in this folder.

Screens:

1. **Ingest**: drop a zip (the mock plays a 14-file sample archive whatever you drop). Eight stages; click a stage
   for what it does, how, its output and its failure behaviour; click a file to follow it through every stage and
   see the drawing model it ends as.
2. **Workspace, engineer**: ask a question, get the number with numbered marks on the drawing, the counting rule,
   the query, the second method's result and the cost. Unanswerable questions are refused with the reason.
3. **Workspace, surveyor**: the takeoff table per drawing. Settle marks where the two methods disagree, reject or
   add marks, include or leave out rooms in an area, sign off, export CSV. Signed values show as verified to the
   engineer.

Deep links: `index.html#ingest/done`, `#work/engineer/A`, `#work/surveyor/B`.

Requirements behind it: `../docs/REQUIREMENTS.md`.

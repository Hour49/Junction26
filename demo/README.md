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

4. **Edit my plan** (`#edit`; from the landing link or the **+** in the chat): take a photo or add an image of a
   house plan (the mock always loads one synthetic flat), then ask for changes in the chat: move a window, add a
   bathroom, remove a wall, split a room. The plan redraws with the change in purple and removed parts dashed. A 2D/3D
   switch shows the same plan in 3D (canvas, no libraries; walls cut at 1.5 m; drag to rotate, scroll to zoom). Changes a rule forbids (a load-bearing wall, a bedroom without a window, a
   bathroom without ventilation, a narrower exit door) are refused with the reason. The rules are examples, not
   legal advice.

Deep links: `index.html#ingest/done`, `#work/engineer/A`, `#work/surveyor/B`, `#edit`.

Requirements behind it: `../docs/REQUIREMENTS.md`.

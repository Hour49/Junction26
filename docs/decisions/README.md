# Decision records

Short records of the decisions the team must not lose or argue about twice. One file per decision, named
`NNNN-short-title.md` and numbered in order, copied from [0000-template.md](0000-template.md).

## When to write one

- Any interface between two people: API shapes, schemas, file formats, event names. Write it before both sides code.
- The stack: languages, frameworks, hosting.
- The data model: main entities, ids, tables.
- An external API or model choice (which LLM, which partner endpoint), including what we do when it is down.
- Anything expensive to reverse after Saturday, or a "no" the team keeps being tempted to revisit.

Choices inside one owner's module don't need one: they go in the code or the owner's notes.

## How

1. Copy the template to the next free number and fill it in; half a page is plenty. Open a PR, or ask your
   orchestrator to commit it.
2. Post a board `decision` thread that links the file, so every orchestrator sees it. Both sides code against it only
   once it is in `main` or acked on the board.
3. A decision changes through a new record that supersedes the old one. The old record gets one line in its Status
   ("superseded by 0007") and stays otherwise as it was.
4. A human's decision is quoted verbatim, with who and when. A decision an agent made says so, and names who
   approved it.

Keep each record short, with a first line that stands on its own: agents read these at the start of a session, and
long logs cost every one of them context.

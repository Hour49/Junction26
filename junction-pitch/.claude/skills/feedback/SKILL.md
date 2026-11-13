---
name: feedback
description: Log messy notes from a talk with a mentor, partner, peer or jury member into 03-research/feedback/log.md as a structured entry with an ID (F-001, F-002...), turn every point into a follow-up action naming the skill to run, start up to 3 quick background checks on named competitors or factual questions, and propose core.md changes as a diff. Also "/feedback summary" (open items, what 2+ people said, top 3 changes) and "/feedback close F-012 <outcome>". Use whenever Madalina reports what someone said about the pitch or the idea.
when_to_use: 'mentor said, the partner thinks, jury asked, peer feedback, got feedback, they told me, log this feedback, what did people say, feedback summary, close F-012'
argument-hint: "<who>: <messy notes>  |  summary  |  close F-012 <outcome>"
allowed-tools: Read Write Edit Grep Glob Agent Bash(TZ=Europe/Helsinki date *)
---

# /feedback

Input: `$ARGUMENTS`
Now (Helsinki): !`TZ=Europe/Helsinki date '+%Y-%m-%d %H:%M'`
(If the line above is empty, run `TZ=Europe/Helsinki date '+%Y-%m-%d %H:%M'` once.)

Templates: [templates.md](templates.md). Log: `03-research/feedback/log.md`. Follow-ups: `03-research/feedback/followups/`.

Pick the mode from the first word of the input:
- `summary` → [Mode B](#mode-b-summary).
- `close` → [Mode C](#mode-c-close).
- anything else → Mode A (log new feedback). Empty input → ask "Who did you talk to, and what did they say?" and stop.

## Rules (all modes)
- **Speed first.** In Mode A the entry must be in the log within about 1 minute. Do not search the web, read
  playbooks or read `03-research/**` before the entry is written.
- **Ask at most one question, only when blocked** (no idea who it was AND no content). Otherwise guess and mark
  the guess with `(?)`. Madalina fixes it later.
- **Privacy:** who = role + company only (e.g. "Mentor, Valio Aimo", "Jury, Lifeline Ventures", "Peer, other team").
  Drop personal names, phone numbers, emails, LinkedIn handles, even if she typed them.
- **Never invent.** Write only what is in her notes. Keep her meaning; fix spelling only. Claims they made
  (e.g. "Picnic already does substitutions") are logged as *their claim*, UNVERIFIED until checked.
- **Never edit `04-pitch/core.md`.** Propose changes as a diff block inside the entry.
- Only the main agent edits `log.md`. Subagents write only their own follow-up file.
- Plain, common English. Short lines.

## Mode A: log new feedback

### A1. Read (one parallel step, small files only)
- `03-research/feedback/log.md`: do not read it whole. Grep it for `^## F-` (IDs) and `- \[ \]` (open actions).
  If the file is missing, create it from "Log file header" in [templates.md](templates.md) first.
- `04-pitch/core.md` (short): note its `Last updated:` value and the fields relevant to the notes.

New ID = highest existing ID + 1, three digits (`F-001` if none). Do not reuse IDs.

### A2. Parse the notes
Text before the first `:` is usually who (e.g. "valio mentor" → "Mentor, Valio Aimo"). Sort each fragment into
one bucket:

| Bucket | Typical signals |
|---|---|
| Liked | likes, loved, good, strong, "wow" |
| Concerns | worried, doubts, "won't work", "too hard", risk, objection |
| Similar products named | a company or product name, "X already does…" |
| Questions they asked | "asked…", "wants to know…", "wants <number>", "how do you…" |
| Research requests | "check…", "look into…", "find out…" |
| Suggested idea changes | "you should…", "focus on…", "drop…", "add…" |

One fragment may go into two buckets (e.g. "Picnic already does substitutions" is both a similar product and a
concern). Empty bucket → `—`.

Also note the **signal** (Mom Test, market-research §2.3): compliments are weak; a commitment (offers data, an
intro, time, "come to our table Sunday") is strong. Write `compliments only` if there was no commitment.

### A3. Actions (one per item, numbered F-012.1, F-012.2...)
Each action names the next skill or the human step:

| Item type | Action |
|---|---|
| Similar product / competitor named | `/market-scan <name> <what they do>`; if quick: background check (A5) |
| Factual question or claim to verify (a number, "do pickers have phones") | `/fact-check <claim>`; if quick: background check (A5) |
| Does the user really feel this pain? | `/pain-points <problem> <user>` |
| A question a judge could ask on stage | `/jury-drill` add the question; note the answer we need |
| Wording, slide, story, demo moment | `/pitch`, `/easy-pitch`, `/pro-pitch` or `/deck` |
| Needs a person (partner data, a booth question) | "Ask <role> at <place>: <exact question>" (Madalina does it) |
| The person is a real user (picker, shift lead, customer) | Also add 3 facts + 1 quote to `03-research/users/interviews.md` (`/pain-points` uses it) |
| Idea change | "Decide: <change>" → see the diff in A4; after the decision, update core.md, then regenerate the pitch |

Mark which actions run now in the background: `(running → followups/F-012-<topic>.md)`.
- One action per item from her notes. Do not add extra research she did not ask for; suggest it in chat instead.
- If the same question is already an open action in an earlier entry (from the grep in A1), write
  `same as F-009.2` instead of a new check. That repeat is what `/feedback summary` counts as a pattern.

### A4. Write the entry, then reply
Insert the entry at the top of the entries (just under the line `<!-- entries: newest first -->`) using
"Log entry" in [templates.md](templates.md). Include the proposed core.md diff:
- Use only lines that exist in core.md now (`-` old line, `+` new line). Name the F-ID that backs the change.
- If core.md is still the template, propose filling the relevant field with what the feedback suggests,
  marked `(to verify: F-012.n)`.
- If nothing in the feedback changes the idea, write `No core.md change proposed.`

Status starts as `OPEN`, or `RESEARCHING` if background checks start.

### A5. Background checks (optional, max 3, launch in ONE message)
Only after the entry is written. Pick at most 3 items that a web search can answer in ~5 minutes: named
competitors and factual questions. Skip if none qualify, or if she wrote "no research" / "log only".

Launch all of them in ONE message so they run at the same time, each as a background `feedback-followup`
subagent (`.claude/agents/feedback-followup.md`). Each gets a distinct item and its own file. Use the prompt
template "Subagent prompt" in [templates.md](templates.md). File name: `03-research/feedback/followups/F-012-<topic>.md`
(kebab-case topic, e.g. `F-012-picnic-substitutions.md`).

Do not wait for them. Reply in chat right away (A6).

### A6. Chat reply (short)
```
Logged F-012 (Mentor, Valio Aimo) → 03-research/feedback/log.md
Liked: … | Concerns: … | Asked: …
Next: F-012.1 /market-scan Picnic (running) · F-012.2 /fact-check … · F-012.3 /jury-drill …
core.md: 1 change proposed (see entry) | none
```
Flag anything she must do herself (questions for a partner, a decision).

### A7. When a background check finishes
Read its file. In the log entry, under the action, add `→ <one-line answer> ([file](followups/F-012-<topic>.md))`
and tick it `[x]`. When all running checks are done, set status to `RESEARCHED` (keep `OPEN` items open) and add
a line to its status log. If the result changes the core.md diff, update the diff in the entry (never core.md).
Tell Madalina in 2 lines: the answer and whether it changes the pitch.

## Mode B: summary
1. Read all of `03-research/feedback/log.md` and the `followups/` files it links. Read `04-pitch/core.md`.
2. Write `03-research/feedback/summary-YYYYMMDD-HHMM.md` from "Summary file" in [templates.md](templates.md):
   - **Open items:** every action not ticked, grouped by skill to run, oldest first, with its F-ID.
   - **Patterns:** a point counts as a pattern only if 2+ *different* people (different who lines) said it.
     Show the count and the F-IDs. Single mentions go in "Said once" (one line each).
   - **Top 3 changes to consider:** rank by (number of people) × (weight: jury or partner of our challenge = 2,
     mentor = 1.5, peer = 1) and by fit with the challenge rubric. Each change gives the F-IDs, the evidence
     from follow-ups, and a core.md diff. If fewer than 3 are backed by feedback, list fewer. Do not pad.
3. Reply with the top 3 in one line each, the count of open items, and the file path.

## Mode C: close
Input: `close F-012 <outcome>` (or `close F-012.2 <outcome>` for one action).
1. Find the entry. If the ID is missing, say so and list the 5 newest IDs.
2. Status from the outcome words: "applied", "changed", "updated core" → `APPLIED`; "rejected", "ignore", "no",
   "not doing" → `REJECTED` (keep the reason); otherwise `DONE`.
3. Whole entry: change the status in its heading and add `- <now> <STATUS>: <outcome>` to its status log.
   One action: tick it and append `→ closed <now>: <outcome>`; the entry stays open while other actions are open.
4. If the outcome is `APPLIED` and core.md was not updated yet, remind her: "Update core.md (diff in F-012),
   then run /pitch to regenerate." Do not edit core.md yourself.
5. Reply in one line.

## Additional resources
- Templates (log header, entry, follow-up file, subagent prompt, summary): [templates.md](templates.md)
- Feedback and rehearsal context: `01-playbooks/pitching.md` §4.1, §4.3; interviews: `01-playbooks/market-research.md` §2.3

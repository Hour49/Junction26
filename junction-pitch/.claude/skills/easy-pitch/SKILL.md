---
name: easy-pitch
description: Write the plain-English pitch for peers and non-experts from 04-pitch/core.md into 04-pitch/scripts/easy-pitch.md - 8-10 hooks/taglines, 10-second and 30-second versions, the timed 2-minute peer-review table demo with [DEMO] cues, everyday analogies, a grandma (jargon) test with a readability check, a table-sign line and what peers ask. "/easy-pitch test" gives 3 hooks to A/B test on different peers. Use for the peer-review table, talking to other hackers, or any "explain it simply" pitch.
when_to_use: easy pitch, simple pitch, explain it simply, pitch for peers, peer review table, table demo, 2 min demo script, hooks, tagline, catchy line, elevator for non-tech people, grandma test, too much jargon, laptop sticker, table sign, test hooks, which hook works
argument-hint: "[test] [optional note: what changed or what to focus on]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python3 *)
---

# /easy-pitch: the pitch anyone gets in 10 seconds

Input from Madalina: `$ARGUMENTS` (may be empty, short or messy; that is fine).

**Who hears it:** other hackers and non-experts. Friday night chats, and above all Sunday's face-to-face peer review: about 2 minutes per table, and the visitor compares us with the table they just saw. So we must be **easier to get and easier to remember** than the table next to us (pitching.md §0 point 5, §1b).

**Mode:** if the first word of `$ARGUMENTS` is `test`, go to **Test mode** at the bottom. Otherwise run **Full mode**.

## Rules (from CLAUDE.md; they always hold)
- **Real data only.** Every number comes from `04-pitch/core.md` or a line in `03-research/sources.md`, with its label: measured / reported / assumed. Single-source → add UNVERIFIED. No source → no number; use a hook style without a number. Never invent users, quotes, companies or results. Example personas get a made-up first name and the tag "(example)".
- **Plain, common English.** Short words, short sentences. Target about grade 6–8: avg sentence ≤ 12 words, long words (3+ syllables) ≤ 10 %.
- **Never claim what the demo can't show** or what wasn't built this weekend.
- Don't edit `core.md`. If it is wrong or missing something, say so in §9 "Gaps" and in chat.
- Ask at most 1–2 questions, and only when truly blocked. Otherwise make a sensible choice and note it in §9.

## Full mode

### Step 1: read the inputs (in this order, skip what's missing)
1. `04-pitch/core.md`: the single source. Note its "Last updated" date and status.
2. `03-research/sources.md`: which numbers are allowed and their labels.
3. `03-research/feedback/log.md`: what peers and mentors said (confusion = jargon to remove; words they used = words to steal; earlier hook test results = which hooks to keep).
4. `03-research/users/` and `03-research/pain-points/` (skim): the user's own words for the problem.
5. Existing `04-pitch/scripts/*.md` (skim): stay consistent with the other scripts' one-liner.
6. [hook-guide.md](hook-guide.md) (styles + what 2025 winners said), [plain-words.md](plain-words.md) (grandma test + swap list), [template.md](template.md) (output format).

Background, only if you need it: `01-playbooks/pitching.md` §0, §1b, §3; transcripts in `02-reference/pitch-transcripts/` (the two `*-submission-video.md` files are the 2-minute ones).

**If core.md is still the empty template:**
- If Madalina's note in `$ARGUMENTS` (or the conversation) describes the idea → write a **DRAFT** from it. Put "status: DRAFT from Madalina's note; core.md not filled" in the header, and list in §9 what core.md needs. Use no numbers unless she gave a source.
- If there is nothing to go on → ask one question: "What's the idea in one sentence, and who is it for?" Then stop.

### Step 2: find the plain core (think, don't write the file yet)
Answer these in ≤ 10 plain words each:
- **Who** has the problem? (one person you could point at: "the person packing your groceries")
- **What goes wrong** for them, as a scene you can picture?
- **What does our thing do**, as a verb a child knows (warns, finds, fixes, tells, swaps)?
- **The wow**: what appears on screen in the demo that makes people say "oh"? (core.md "Demo wow moment")
- **The one number** (with label) — or "none yet".

### Step 3: write the output
- Path: `04-pitch/scripts/easy-pitch.md`. **If it already exists, don't overwrite it:** write `easy-pitch-v2.md` (or the next free `-vN`) unless Madalina said "overwrite" or "replace".
- Follow [template.md](template.md) exactly: sections 1–9, header with the date line and the "Based on core.md" line.
- **Every spoken line starts with `> `** (also inside table cells), so the checker can find it.
- Content checklist:
  - [ ] §1 Table sign: ≤ 8 words, says what + for whom. One backup.
  - [ ] §2 8–10 hooks, at least 4 styles from hook-guide.md (question, X for Y, surprising number, everyday scene are required if there's a sourced number; otherwise replace "number" with another style and say why). 3 marked ★ A/B/C from 3 different styles, with one line on why.
  - [ ] §3 10-second version, 20–25 words.
  - [ ] §4 30-second version, about 65 words.
  - [ ] §5 2-minute table demo: timed rows, [DEMO] cues, visitor's hands on the laptop by 0:20–0:30, **the WOW by 0:30**, ≤ 200 spoken words, a "demo broke" line, and the "what would you use this for?" question.
  - [ ] §6 2–3 analogies from everyday life (not other software). Mark the best one.
  - [ ] §7 Grandma test table: every jargon word or hard phrase you removed, and its plain replacement.
  - [ ] §8 What peers ask: one-line spoken answers. Honest ("we haven't measured that yet").
  - [ ] §9 Gaps: missing core.md fields, numbers without a sources.md line, demo steps that must exist for the script to be true.

### Step 4: grandma test + readability check (always run it)
```bash
python3 "${CLAUDE_SKILL_DIR}/readability.py" 04-pitch/scripts/easy-pitch.md
```
(If `${CLAUDE_SKILL_DIR}` is empty, use `.claude/skills/easy-pitch/readability.py`.)
- It checks only `> ` lines and prints, per section: avg sentence length, long-word %, a rough grade, long sentences, very long words, and jargon from [plain-words.md](plain-words.md).
- **Fix every SIMPLIFY section, every jargon hit and every sentence over 15 words**, then run it again. Two rounds at most. Names, the partner's words, and a tech word said *right after* its plain version (for techies who ask "how?") may stay; list them in §7. Grade below 6 is fine for speech; only above 8 needs fixing.
- Then do the human grandma test yourself: read each `> ` line and ask "would a non-tech person get this first time, in a loud room?" Fix what fails, log it in §7.
- Put the final OVERALL numbers from the last run in the header "Readability" line (never estimate them).

### Step 5: reply in chat (short)
- File path, and whether it is FILLED or DRAFT.
- The table-sign line and the 3 test-first hooks (A, B, C), so she can use them right away.
- Readability: grade / avg sentence / long-word %.
- Top 1–3 gaps (from §9).
- Next: "Try the hooks with `/easy-pitch test`, then log reactions with `/feedback`." Other skills when relevant: `/pitch` (other formats), `/fact-check` (if numbers are unsourced), `/jury-drill` (Q&A practice).

## Test mode (`/easy-pitch test`)
Goal: Madalina tries 3 hooks on different peers and finds the one that lands.

1. Read the newest `04-pitch/scripts/easy-pitch*.md` (highest `-vN`). If none exists, run Full mode first, then continue.
2. Read `03-research/feedback/log.md` for earlier hook tests. Keep a hook that already worked; drop hooks that got "what?" twice; add a fresh one from §2 to keep three.
3. Pick **3 hooks from 3 different styles** (default: the ★ A/B/C ones). If `$ARGUMENTS` has more after `test` (e.g. "test shorter", "test funny"), adapt the choice or reword a hook in that direction (still plain and sourced).
4. Reply in chat with this card (don't write a file; she reads it on her phone):

```
HOOK TEST — <date>
A (<style>): "<hook>"
B (<style>): "<hook>"
C (<style>): "<hook>"

How: say only the hook, then wait 2 seconds. Rotate A → B → C → A.
Try each on 3–5 different people (mix techies and non-techies).
Worked = they ask "how?", repeat it, laugh, or lean in.
Failed = "sorry, what?", blank face, or "so what is it?".

After each person (or each batch), log it:
/feedback peer, hook <A/B/C>, <their reaction in a few words>, <techie or not>
```

5. Then stop. Do **not** log results yourself: tell her to run `/feedback`. Next time `/easy-pitch` runs, it reads those results (Step 1.3) and moves the winning hook to the top of §2 and onto the table sign if it fits.

## Files in this skill
- [template.md](template.md): output format for `easy-pitch.md`.
- [hook-guide.md](hook-guide.md): hook styles, rules, real 2025 openings, analogy tips, A/B test signs.
- [plain-words.md](plain-words.md): grandma-test rules and the jargon swap list (also read by the checker).
- [readability.py](readability.py): stdlib readability + jargon check. `python3 readability.py FILE` (spoken lines) or `--all`.

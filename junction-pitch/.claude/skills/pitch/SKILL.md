---
name: pitch
description: Write timed spoken scripts for the formal Junction pitches from 04-pitch/core.md - the 3-min stage pitch to the jury (the 2026 rule is exactly 3 min), the partner/challenge judging pitch (mapped to that partner's rubric), and a 30-second elevator pitch - with per-section time and word budgets, [CLICK] [DEMO] [PAUSE] cues and an over-time warning. Also makes printable cue cards and a self-check list for rehearsal. Use when Madalina asks for a stage pitch, jury pitch, final pitch, partner pitch, challenge pitch, elevator pitch, 30-second pitch, pitch script, "how long is my pitch", "time my pitch", cue cards, or "help me rehearse".
when_to_use: Trigger phrases - write the stage pitch, 3 minute pitch, pitch for Valio, partner judging pitch, elevator pitch, is my script too long, rehearse stage-3min, cue cards. Not for the 2-min peer table demo (use /easy-pitch) or talks with mentors and partners (use /pro-pitch).
argument-hint: "stage | partner [partner-name] | elevator | all | rehearse <stage-3min|stage-5min|partner-pitch|elevator-30s>"
allowed-tools: Read Write Edit Glob Grep Bash(python3 *)
---

# /pitch: timed scripts for the formal pitches

Input: `$ARGUMENTS` (may be short and messy, e.g. "stage", "partner valio", "all", "rehearse 3min", "stage but shorter demo").

Related skills, do not duplicate them:
- /easy-pitch: the 2-min peer-review table demo, peers and non-experts.
- /pro-pitch: talks with mentors and partners (questions, rubric intel).
- /deck: the slides that [CLICK] moves through. /jury-drill: Q&A practice after the script. /fact-check: before the number goes on stage.

## Pick the mode

| Argument (loose match) | Writes to `04-pitch/scripts/` |
|---|---|
| `stage`, "jury", "final", "3 min" | `stage-3min.md` (2026 rule: exactly 3 min, mic killed at time, then 3 min of jury Q&A) |
| `stage-5min`, "5 min" (only if Madalina asks) | `stage-5min.md` |
| `partner [name]`, "challenge", "<partner name>" | `partner-pitch.md` |
| `elevator`, "30s", "30 seconds" | `elevator-30s.md` |
| `all` | stage-3min, partner, elevator |
| `rehearse <format>`, "cue cards", "practise" | `<format>-cards.md` (see Rehearse mode) |
| empty | `stage` (the 3-min one is the script that must survive a mic cut) |

Extra words in the argument ("shorter demo", "more on the team", "jury said X") are edit requests: apply them, still from core.md.

**Never overwrite.** If the output file exists, write the next free version: `stage-3min-v2.md`, `-v3`... Madalina may have edited the old one by hand.

## Step 1. Read the inputs

1. `04-pitch/core.md`: the only source of the message. Needed fields: name, one-liner, target user, problem, problem number, solution, demo wow moment, ask. Useful: why now, difference, proof, market, how it works.
   - Still "Status: TEMPLATE", or 3+ needed fields empty: **stop**. List the missing fields and ask Madalina for them in one message (or to run the skill that fills core.md). Do not write a script from guesses.
   - 1-2 needed fields empty: write the script with `<TODO: field>` in their place and list them in the summary.
   - Note core.md's "Last updated" value and its file date for the header.
2. `03-research/sources.md`: find the line behind the problem number and the proof number. Missing line: keep the number but mark it `sources.md line: MISSING` in the header and in Checks, and suggest /fact-check.
3. `03-research/feedback/log.md` (if it exists): entries with status "applied", jury or partner quotes, and anything like "didn't understand", "too long", "who is the user". Fix those in the script. Partner quotes may be used only as logged, word for word, with the role (no private names).
4. `04-pitch/deck/` (if a slide outline exists): put one [CLICK] per slide change, in the deck's order. No deck yet: follow the slide order in `01-playbooks/pitching.md` §2.
5. Partner mode only: `03-research/challenges/<partner>-<challenge>/brief.md` (+ `partner.md`, `fit.md`; written by /challenge-pick; older flat `03-research/challenges/<partner>-*.md` also accepted) for the rubric (criteria, weights, pitch length, data given, rep's words).
   - No file: use the partner's past rubric from `00-event/junction-info.md` §2C if there is one, marked "[2025 rubric, check the 2026 brief]", and ask Madalina once for the real rubric.
   - Pitch length unknown: 3 min, marked UNVERIFIED (pitching.md §1c).
6. Rehearse mode only: the newest version of the script being rehearsed.
7. Team line (stage scripts): core.md has no team field. Use `01-playbooks/pitching.md` §2 "Presenting the team credibly" (shipped-proof line, one credential each); "who did what" stays a `<TODO>` until Sunday.

Do not read the whole playbook each run. The rules below already hold what matters from pitching.md §0, §1a, §1c, §1d, §2, §4.

## Step 2. Draft the script

Use the structure in [templates.md](templates.md) for the format. Write every line in [plain-words.md](plain-words.md) English.

**Time and words.** Pace 140 words per minute (Madalina chose it on 2026-11-10; the playbook says 130-140 for clear speech). Keep 10% of the time free. Targets:

| Format | Slot | Target words | Hard limit |
|---|---|---|---|
| elevator-30s | 0:30 | 63 | 75 |
| stage-3min, partner (default) | 3:00 | 378 | 450 |
| stage-5min | 5:00 | 630 | 750 |

Demo sections get about 75 words per minute: the jury watches, you narrate only what they cannot see.

**Order rules (from the 2025 finals):**
- **The number early.** Say the one number by 0:40 (3-min), 0:55 (5-min), 0:15 (elevator), followed by [PAUSE]. In 2025, λpump's cost number came only at about 1:43 and its demo near 2:53; do better.
- **The demo wow early.** The wow happens on screen by 1:05 (3-min) or 1:30 (5-min). Write a wow line that lands exactly then, followed by [PAUSE].
- **Open with the user and the moment**, not "Hi, we are team...". λpump: "Right now, beneath our feet..."; Walkthrough named the cost ("half an hour") by 0:33.
- **Close by 2:45 in a 3-min slot** (by 4:40 in 5-min). The host cut Walkthrough at about 5:05; the mic is cut at time. The last sentence before the cut must already be the one-liner + the name.
- **Ask:** the close always holds the ask (stage: pilot with the partner, or "try it at table N"; partner: what we need to pilot).
- **Demo is a silent embedded video** with burned-in captions; Madalina narrates live. Add a `> ` fallback line under [DEMO]: "The live version is at table N. Come and try to break it." (WAVELET lost about 40 s waiting for a cold GPU; audio failed for 2 of 5 teams.)
- **Speak the jury's words** where true: "a problem worth solving" (Kanninen), "where it fails and how we check it" (Raghuvanshi), "why people come back" (Söderlund). Only in the stage scripts.
- **One speaker.** Madalina says everything; a teammate runs the clicker. Write `> ` notes for the clicker where a [DEMO] or [CLICK] timing is tight.
- **Do not oversell.** Anything not built this weekend is called "vision" out loud. Claims about results must match core.md's "Proof" field and its label.

**Partner pitch:** start with the rubric map table (template). Name each criterion out loud in the partner's own words when the script hits it. Use their unit for the impact number (FTE, euros, minutes).

**Elevator:** a 30-second product pitch for "so what are you building?". For a two-way mentor or partner conversation, point Madalina to /pro-pitch instead.

**5-min (only on request; not used on the 2026 stage):** the 3-min script plus HARD CASE, HOW IT WORKS and MARKET AND PATH. Keep the same opening and closing lines, so she learns them once.

## Step 3. Check the time

Run the counter on the file you wrote:

```
python3 ${CLAUDE_SKILL_DIR}/count_words.py 04-pitch/scripts/<file>.md
```

- Any section OVER, or a total WARNING: cut words (not content order), rewrite, run again. Cut adjectives and the second example first; never cut the number, the wow line, the one-liner or the ask.
- Paste the final counter output into the file's `## Checks` section, inside a code block.
- If it still fails after two cuts, keep it but say so at the top of the Checks and in the chat.

Then add to `## Checks`:
- the number: where (m:ss), label, sources.md line found or MISSING;
- the wow: at m:ss;
- (estimate a line's time as: section start + words before it in the section ÷ section words × section length);
- user named: yes/no; ask said: yes/no; close starts at m:ss;
- plain-words scan: words replaced, words still risky;
- open `<TODO>`s and UNVERIFIED items.

## Rehearse mode (`/pitch rehearse stage-3min`)

1. Read the newest version of `04-pitch/scripts/<format>.md`. None: write the script first (Steps 1-3), then the cards.
2. Write `04-pitch/scripts/<format>-cards.md` from the "Rehearsal cards" template:
   - the opening (first 30 s) and closing (last 10 s) word for word: Madalina memorises only these;
   - one table row per beat (a cue or a new idea): time, cue, 3-6 key words. The number appears exactly, in full;
   - the self-check list with this script's real times filled in (wow by m:ss, limit m:ss);
   - the drill steps, ending with /jury-drill.
3. Keep it printable: no long paragraphs, one beat per line, under one A4 page for 3 min.

## Step 4. Reply in chat (short)

- File path(s) written, and each total: "stage-3min.md: 318 words, about 2:33, OK".
- The number and the wow time, one line.
- What is missing or UNVERIFIED (TODO fields, sources.md lines, the partner rubric, the pitch length).
- Next: `/pitch rehearse <format>`, /deck to match the [CLICK]s, /jury-drill for Q&A, /fact-check for the number.

## Sources for these rules
- `01-playbooks/pitching.md` §0, §1 (formats, word budget), §1c, §1d, §2 (deck order), §4.1 (delivery), §4.2 (demo fallbacks).
- `02-reference/pitch-transcripts/2025-*-stage-pitch.md`: the five 2025 top-5 stage pitches. Measured from the auto-captions (approximate): about 740-1,130 words before the Q&A in about 5 min, so 145-200 words per minute. That is fast native speech; we use 140 so a non-native speaker stays clear.

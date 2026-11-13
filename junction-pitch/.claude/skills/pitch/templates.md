# /pitch templates

Fill every `<...>` from `04-pitch/core.md`. A field that core.md does not have stays as `<TODO: field>`; never invent it.

## File rules (the word counter depends on them)
- Timed section heading: `## NAME [m:ss-m:ss] budget Nw`. The budget is the word budget for that section.
- Spoken text: plain lines, short sentences, no bullets (lines that start with `-` are not counted).
- Stage notes for Madalina or the teammate on the clicker: lines that start with `> `.
- Cue marks inside spoken lines: `[CLICK]` next slide · `[DEMO]` the demo video starts (teammate presses play or it autoplays) · `[PAUSE]` stop for one full second (always after the number and after the wow).
- After the last timed section, add `## Checks`. It stops the word count.

Pace: 140 words per minute (plain, clear English), with 10% of the time left free for clicks and applause. Demo sections get fewer words, because the jury is watching, not listening.

## Header (every output file)

```markdown
# <Format title>: <Project name>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Written by /pitch
- Based on: 04-pitch/core.md, "Last updated: <value in core.md>" (file changed <mtime>)
- Slot: <length> · Pace: 140 wpm · Target: <N> words (hard limit <M>)
- The number: "<number sentence>" (<measured|reported|assumed>; sources.md line: <yes / MISSING>)
- Wow moment: <what the jury sees>, at <m:ss>
```

## stage-3min.md (target ≤ 378 words, hard limit 450)

```markdown
## HOOK [0:00-0:15] budget 34w
<Person + moment + the number, in one or two sentences. Not "Hi, we are team...".> [PAUSE]

## PROBLEM [0:15-0:40] budget 56w
[CLICK] <Who exactly. What it costs them, in their words. Why now.>

## SOLUTION [0:40-0:50] budget 22w
[CLICK] <Name> <one-liner>.

## DEMO [0:50-1:45] budget 70w
[CLICK] [DEMO] <Narrate only what they cannot see. One short line per screen.>
<The wow line, said exactly when it happens on screen, by 1:05.> [PAUSE]
> If the video does not play: "The live version is at table <N>. Come and try to break it." Then narrate the 3 screenshots.

## WHY IT HOLDS [1:45-2:10] budget 56w
[CLICK] <The one hard thing, in plain words. Where it fails and how we check it: eval number, one hard case caught.>

## PROOF [2:10-2:30] budget 45w
[CLICK] <The number again, measured vs a baseline. Why the user comes back: trigger, value, again.>

## TEAM AND WHO PAYS [2:30-2:45] budget 34w
[CLICK] <Four engineers from Cluj, one shipped-proof line. Who pays, first customer.>

## CLOSE [2:45-3:00] budget 28w
[CLICK] <Callback to the hook. The one-liner. The ask.> <Name>. Thank you.
> Close starts at 2:45, so a mic cut at 3:00 still hears the one-liner.
```

## stage-5min.md (target ≤ 630 words, hard limit 750)

Same opening as the 3-min version, plus a second demo beat, the architecture, and the market path. Add content; do not slow down.

```markdown
## HOOK [0:00-0:20] budget 45w
## PROBLEM [0:20-0:55] budget 78w
## SOLUTION [0:55-1:10] budget 34w
## DEMO [1:10-2:30] budget 100w        (wow by 1:30)
## HARD CASE [2:30-3:10] budget 78w     (an edge case or failure being caught, on screen)
## HOW IT WORKS [3:10-3:40] budget 67w  (3 boxes; models and why; eval)
## PROOF [3:40-4:05] budget 56w
## MARKET AND PATH [4:05-4:25] budget 45w (who pays, rough size with source, pilot with the partner)
## TEAM [4:25-4:40] budget 34w
## CLOSE [4:40-5:00] budget 39w
```

## partner-pitch.md (default 3 min; use the partner's real length if known)

Start the file with the rubric table, then the script. Use the criteria names exactly as the partner wrote them.

```markdown
## Rubric map
| Criterion (their words) | Weight | Where we hit it (section, m:ss) | Evidence we show |
|---|---|---|---|

## FOR YOU [0:00-0:15] budget 34w
For <partner>'s <challenge>, we built <Name>. <One-liner.>

## YOUR PROBLEM [0:15-0:40] budget 56w
<Their problem in THEIR words: "<quote from the Friday talk, logged in feedback/log.md>". The data of theirs we used.> [PAUSE]

## DEMO ON YOUR DATA [0:40-1:50] budget 90w
[DEMO] <Demo on their data or API. Name each criterion as you hit it: "That is the <criterion> part.">

## HOW IT FITS YOU [1:50-2:25] budget 78w
[CLICK] <How it plugs into their systems tomorrow. Cost to run. What is still missing, said honestly.>

## IMPACT [2:25-2:45] budget 39w
[CLICK] <The number in their unit (FTE, euros, minutes, error rate), with its label.> [PAUSE]

## ASK [2:45-3:00] budget 34w
<What we need to pilot: data access, two weeks, one contact.> <Name>. Thank you.
```
- Rubric weights usability most: keep the problem first, but give the demo the most time and show the user flow before the tech.
- Rubric is metric-gated (an accuracy gate): say the number already in FOR YOU.
- Split the section budgets in proportion to the rubric weights where you can.

## elevator-30s.md (target ≤ 63 words, hard limit 75)

A 30-second product pitch for anyone who asks "what are you building?" (jury in the corridor, a visitor, a partner who has 30 seconds). For a two-way talk with mentors and partners, use /pro-pitch.

```markdown
## WHO [0:00-0:05] budget 11w
We are Hour49. We built <Name>.

## PROBLEM AND NUMBER [0:05-0:15] budget 22w
<User> <problem>. <The number.> [PAUSE]

## WHAT IT DOES [0:15-0:25] budget 18w
<What it does, and the wow in one line.>

## ASK [0:25-0:30] budget 11w
<Come to table N / what we need.>
```

## Rehearsal cards: `<format>-cards.md`

```markdown
# Cue cards: <format> · <Project name>
- Date · Based on: <script file> (<date line of the script>) · Total <N> words, about <m:ss>

## Say these word for word
Opening (first 30 s): "<exact text>"
Closing (last 10 s): "<exact text>"

## Cards (one line per beat; print this, big font)
| Time | Cue | Say (key words only) |
|---|---|---|
| 0:00 | — | <3-6 key words> |
| 0:15 | [CLICK] | <...> |
| 0:22 | [PAUSE] | <the number, exact> |

## Self-check after each run (tick, out loud)
- [ ] Did I name the user (one specific person or role)?
- [ ] Did I say the number, exactly, and pause after it?
- [ ] Did the demo wow happen before <m:ss>? Did I say the wow line on time?
- [ ] Did I say the ask?
- [ ] Did the one-liner come before the last 15 seconds?
- [ ] Time on the timer: ____ (limit <m:ss>). Over? Cut, do not speed up.
- [ ] Words I tripped on: ____ → replace them in the script.
- [ ] Did I face the room, mic close to the chin, one speaker?
- [ ] Could a listener repeat the one-liner back? (Ask one.)

## Drill
1. Read once from the script with a timer. 2. Twice from the cards only. 3. Once with the slides and a teammate on the clicker. 4. Record on the phone, watch once. 5. /jury-drill for the Q&A.
```

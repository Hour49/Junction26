# /deck outline format and skeleton

`build_mock.py` reads this format, so keep the keys exactly as written. One field per line: `- Key: value`.
Notes and other long fields continue on the next lines, **indented by 2 spaces**. A line that is not indented and starts with `- Key:` starts a new field.

## Rules for every slide

- **On screen:** at most 12 words. Plain words. One idea.
- **One number per slide**, in `Number:` (shown huge). Every number has a `Source:` line, at most about 15 words: publisher, year, label (measured / reported / assumed), UNVERIFIED if single-source. The full URL lives in `03-research/sources.md`, not on the slide.
- **No number yet?** Write `[[need: what number, from where]]`. The mock shows it in yellow. Never invent a number, a quote, a user or a company.
- **Notes:** what Madalina says, in plain spoken English, short sentences. Budget about 2.3 words per second (130–140 words per minute). The generator warns when notes are too long.
- **Seconds:** one number per slide; the deck totals 180 s (2026 stage pitch: exactly 3 min). Only for an optional 5-min version: `core / 5-min`, 5-min cut totals 300 s.
- **Cut:** `both` (every slide of the 3-min deck). `5-min` only for an optional 5-min version. Backup slides use `## Backup X:` headings and need no Cut or Seconds.
- **Layout:** `hook`, `statement`, `big-number`, `image`, `demo`, `team`, `close`. `image` and `demo` show the file in `Image:` / `Video:` / `Fallback:` or a dashed placeholder naming the expected path. `close` shows the QR code from `Image:` (default `assets/qr.png`).
- **Image paths** are relative to the mock HTML: `assets/<file>` = `04-pitch/deck/mock/assets/<file>`.
- **Badge:** `Built this weekend` or `Live` for real footage; `Vision` for concept art (playbook §2 "Do not oversell").
- **Videos:** muted MP4, captions burned in, she narrates live. Every video slide has a `Fallback:` GIF or screenshot.

## Optional fields

- `Extra for 5-min:` only for an optional 5-min version: what she adds to this slide (shown in yellow in presenter view).
- `Team:` for `Layout: team`: `Name — role — one credential; Name — …` (4 people, `;` between people).

## Skeleton (copy, then fill from core.md)

```markdown
# Deck outline: <Name from core.md>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: /deck
- Based on core.md: <"Last updated" value of 04-pitch/core.md>
- Version: v1 (previous: none)
- Cut: 3 min = 180 s (2026 rule: exactly 3 min, mic killed, then 3 min Q&A)
- Changed since last version: <one line, or "first version">

## Slide 1: <Hook title>
- Cut: both
- Seconds: 12
- Layout: hook
- On screen: <≤8 words: a person + a moment>
- Number:
- Visual: <full-bleed photo or one big word>
- Image:
- Source:
- Notes:
  <Speak before you click. A person, a moment, a number. Never "Hi, we are team…".>

## Slide 2: Problem
- Cut: both
- Seconds: 23
- Layout: big-number
- On screen: <what the number means, ≤10 words>
- Number: <the one sourced number>
- Visual: <the number, huge>
- Source: <name, label, sources.md line>
- Notes:
  <Who, what it costs, why now.>

## Slide 3: User
- Cut: both
- Seconds: 10
- Layout: statement
- On screen: <persona role + their own words, short>
- Visual: <persona card or real quote (only real, sourced quotes)>
- Source: <interview / feedback log line, or [[need: real quote]]>
- Notes:
  <...>

## Slide 4: Solution
- Cut: both
- Seconds: 15
- Layout: image
- On screen: <Name: one-liner>
- Visual: <screenshot of the HTML app mock-up>
- Image: assets/app-home.png
- Badge: Built this weekend
- Notes:
  <...>

## Slide 5: Demo
- Cut: both
- Seconds: 50
- Layout: demo
- On screen: <≤6 words, the wow moment>
- Visual: silent screen recording, captions burned in, 40–50 s; wow by 15 s in
- Video: assets/demo.mp4
- Fallback: assets/demo.gif
- Badge: Built this weekend
- Notes:
  <Narrate live, beat by beat. The video has no sound.>

## Slide 6: Why it holds
- Cut: both
- Seconds: 25
- Layout: big-number
- On screen: <metric vs baseline, plain words>
- Number: <measured result from our demo, or [[need: eval number]]>
- Visual: 3-box diagram + one bar: ours vs baseline
- Source: <measured, how>
- Notes:
  <The one hard thing, the eval, a failure we catch.>

## Slide 7: Proof
- Cut: both
- Seconds: 15
- Layout: statement
- On screen: <why they come back: trigger → value → memory>
- Visual: loop diagram
- Notes:
  <...>

## Slide 8: Market
- Cut: both
- Seconds: 10
- Layout: big-number
- On screen: <who pays + first customer (the partner)>
- Number: <bottom-up number with arithmetic in notes>
- Source: <...>
- Notes:
  <...>

## Slide 9: Team
- Cut: both
- Seconds: 10
- Layout: team
- On screen: <one track-record line, ≤12 words>
- Team: [[Name — role — what they built here]]; [[…]]; [[…]]; [[…]]
- Visual: 4 photos (assets/team-1.jpg … team-4.jpg)
- Notes:
  <PLACEHOLDER until the team intro is defined (TODO.md, /team-intro).>

## Slide 10: Close
- Cut: both
- Seconds: 10
- Layout: close
- On screen: <Name. One-liner.>
- Visual: name + QR code to the live demo (assets/qr.png); leave up during Q&A
- Notes:
  <Callback to the hook. "<Name>. Thank you.">

## Backup A: Demo screenshots
- Layout: image
- On screen: <if the video fails: 3 key screens>
- Image: assets/demo-backup.png
- Notes:
  <Narrate as if it played. "The live version is at table <N>. Come break it.">

## Backup B: Built this weekend vs before
- Layout: statement
- On screen: <what we built here; what existed before (declared)>
- Notes:
  <For "was it all built this weekend?" (asked of 2 of 5 finalists in 2025).>

## Backup C: Who did what
- Layout: statement
- On screen: <one line per person>
- Notes:
  <For "who did what?" (asked of 3 of 5 finalists in 2025).>
## Backup D: Edge case (for Q&A)
- Layout: demo
- On screen: <what happens when it goes wrong>
- Video: assets/demo-edge.mp4
- Fallback: assets/demo-edge.gif
- Notes:
  <A failure case and how we catch it (Raghuvanshi: "why an agent fails").>

## Backup E: How it works (for Q&A)
- Layout: image
- On screen: <3 steps, ≤9 words>
- Visual: architecture, 3 boxes
- Image: assets/architecture.png
- Notes:
  <...>

## Backup F: Next 48 hours (for Q&A)
- Layout: statement
- On screen: <the next concrete step with the partner>
- Notes:
  <...>

```

Timing check of the skeleton: 12+23+10+15+50+25+15+10+10+10 = 180 s.
Slides may be merged or dropped when core.md has nothing for them; keep the totals, the demo slide and the team slide.

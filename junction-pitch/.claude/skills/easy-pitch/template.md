# Output template: 04-pitch/scripts/easy-pitch.md

Convention: **every line Madalina says out loud starts with `> `** (a blockquote; also `1. > ` in lists and `> ` at the start of a table cell). `readability.py` checks only those lines. Anything in (round brackets) or [square brackets] is a note or cue, not spoken, and is skipped.
Word budget at 130–140 words/min (pitching.md §1): 10 s ≈ 20–25 words, 30 s ≈ 65 words, 2 min ≈ 260 words, but at the table the visitor drives the demo, so aim for **≤ 200 spoken words** in the 2-min script.

```markdown
# Easy pitch: <Name>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: /easy-pitch
- Based on: 04-pitch/core.md, last updated <date from core.md> (status: <FILLED | DRAFT from Madalina's note>)
- Readability (spoken lines): grade <x>, avg sentence <y> words, long words <z>% — <OK | SIMPLIFY> (readability.py)
- For: peers and non-experts. Friday-night chats and Sunday peer review (about 2 min per table; visitors compare us with the table they just saw).

## 1. Table sign / laptop sticker
**<NAME>: <one line, ≤ 8 words, says what it does for whom>**
(Backup: <second option>.) Print big. Add the table number and a QR code to the demo/video.

## 2. Hooks (say them out loud; ★ = test first)

| # | Style | Hook | Words | Test |
|---|---|---|---|---|
| 1 | Question | > … | 7 | ★ A |
| 2 | X for Y | > … | 6 | ★ B |
| 3 | Surprising number | > … (number: <label>, sources.md line) | 9 | ★ C |
| 4 | Everyday scene | > … | 10 | |
| … 8–10 rows, ≥ 4 styles … | | | | |

Why these three first: <one line each>.

## 3. 10-second version (≈ 20–25 words)
> <Name> <does what> for <who>. <One proof or wow in a few words>.

## 4. 30-second version (≈ 65 words)
> <hook>
> <problem in one everyday sentence + one number>
> <what we built, plain>
> <what they will see / try>
> <close: name + table>

## 5. 2-minute table demo (timed; visitor's hands on the laptop by 0:30)
Before they arrive: demo open on the start screen, inputs pasted on the clipboard, backup video on the desktop.

| Time | Do | Say |
|---|---|---|
| 0:00–0:10 | Point at the screen | > <hook>. <identity line> |
| 0:10–0:20 | | > <problem: one person, one number> |
| 0:20–0:30 | [DEMO] hand them the laptop / mic | > Try it: <exact thing to type or say>. |
| 0:30 | [DEMO] **WOW**: <what appears on screen> | > <one line that names the wow> |
| 0:30–1:20 | [DEMO] they keep driving | > <narrate only what they can't see: 1–2 short lines> |
| 1:20–1:40 | Show the proof (poster / second screen) | > <measured result vs what people do today, with label> |
| 1:40–2:00 | Hand them the sign / QR | > If you remember one thing: <one-liner>. We're table <N>. |

If the demo breaks: > <one calm line>, then play the backup video.
Ask at the end, when there's time: > What would you use this for? (write the answer down → /feedback)

## 6. Everyday analogies
1. > It's like <everyday thing>: <why it fits>.
2. …
3. …
(Best one for the table: #<n>.)

## 7. Grandma test
Result: <PASS | n sentences fixed>. Every spoken line above was checked.

| Was (jargon or hard) | Now (plain) | Where |
|---|---|---|
| … | … | §5 0:30 |

Long sentences split: <n>. Words kept on purpose (and why): <e.g. the partner's name>.

## 8. What peers ask (one-line answers)

| They ask | We say |
|---|---|
| So what is it, in one line? | > … |
| Who is it for? | > … |
| How does it work? | > <plain first, then the tech word> |
| Did you build this here, this weekend? | > <true answer; matches the submission's declaration> |
| Is that live or recorded? | > … |
| How is this different from <ChatGPT / the obvious alternative>? | > … |
| Does it really work? How do you know? | > <measured number + label, or "we haven't measured that yet; our guess is…"> |
| What's the hardest part? | > … |
| What breaks first? | > <honest weakness> |
| Would anyone pay for it? / Who pays? | > … |
(Sources for these questions: pitching.md §1b, §3.4, §4.3. Peer-specific ones are our guess, not observed.)

## 9. Gaps to fix before Sunday
- <missing field in core.md, number without a sources.md line, demo step not built yet, …>
```

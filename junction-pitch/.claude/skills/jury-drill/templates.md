# Jury-drill templates

## 1. Questions file (`04-pitch/scripts/qa-prep.md`, written by analyse mode)

```markdown
# Likely jury questions: <project name from core.md>

Date: <YYYY-MM-DD HH:MM> (Helsinki)
Based on: 04-pitch/core.md, <Last updated value>
Evidence: 02-reference/jury-questions.csv (17 questions, 2025 top 5), pitch-analysis.md, junction-info §2A
Format: 3-min stage pitch, then 3 min of jury questions (about 3–4 questions).

## The idea, judged as the jury would
| Lens | Verdict | Why (file / field) |
|---|---|---|
| Problem worth solving | strong / weak / missing | ... |
| What is real (live, built this weekend) | | |
| Technical choices | | |
| Where it fails, how we measure quality | | |
| Real user, coming back | | |
| Who pays, next step with the partner | | |
| Partner rubric fit | | |
| Team: who did what | | |

Strongest point: <one line>. Most dangerous weak spot: <one line>.

## Top 5 (most likely on stage)
1. "<question as spoken>" — High — <why: e.g. "asked of 3/5 teams in 2025", "Kanninen's stated criterion + no
   problem number in core.md">

## All likely questions
| # | Question | Likelihood | Why likely | Weak spot it hits |
|---|---|---|---|---|

## Gaps to close before Sunday
- <fact or demo measurement we lack> — needed for Q<n> — how to get it (/market-scan, /pain-points,
  /fact-check, measure in the demo, ask the partner)
```

Likelihood: High = asked of 3+ of 5 teams in 2025, or a jury criterion that hits a weak lens; Medium = asked
once in 2025, or a weak lens; Low = plausible, no evidence. Questions only: add model answers only when
Madalina asks ("with answers"), then ≤75 words each, answer first, facts only from core.md or 03-research.

## 2. Live scoring card (shown after each answer)

```text
Score  clarity <n>/5 · directness <n>/5 · length <n>/5 (<words> words ≈ <s> s) · evidence <n>/5 · honesty <n>/5
Best part: <one line, quote her words>
Fix: <one line: the single biggest change>
Better version (your words, <words> words ≈ <s> s):
"<rewritten answer>"
```

Scoring guide (1 = poor, 5 = strong):
- **Clarity:** plain words, one idea, a non-native listener follows it first time. 1 = jargon or two ideas tangled.
- **Directness:** the first sentence answers the question asked. 1 = the answer never comes; 3 = it comes late.
- **Length:** spoken time at 150 words/min (assumed rate, about 2.5 words/s). Live mode target ≤20 s (≤50 words):
  5 = 10–20 s, 4 = 20–30 s, 3 = 30–40 s, 2 = 40–60 s, 1 = over 60 s or under 4 s with no content.
  Rapid mode target 15 s (≤38 words).
- **Evidence:** one concrete fact, number, user quote or demo result that exists in core.md or 03-research/**.
  1 = none; 3 = vague ("users told us"); 5 = specific and sourced. An invented-sounding number with no source
  scores 1 and gets flagged.
- **Honesty:** admits limits plainly, no overclaiming, no bluff. 1 = claims something core.md contradicts or
  cannot support; 5 = "we have not measured that; our guess is X because Y".

Better version rules: keep her words and phrases wherever they work; reorder to answer first; cut filler; add
evidence only from core.md or 03-research/**, otherwise insert [GAP: need ...]. Never add facts she did not
give and the files do not hold.

## 3. Weak-spots log (`04-pitch/scripts/qa-weak-spots.md`)

Create the file with this header if it does not exist. Insert each new session section directly under the
header (newest first). Never edit or delete older sections.

```markdown
# Q&A weak spots

Newest session first. Written by /jury-drill live and /jury-drill rapid.

## <YYYY-MM-DD HH:MM> — <live <persona> | rapid> — based on core.md <Last updated>
Average: clarity <x> · directness <x> · length <x> · evidence <x> · honesty <x>
| Question | Persona | Lowest scores | What went wrong | Better version (short) | Fix outside the pitch |
|---|---|---|---|---|---|
Patterns: <1–3 bullets, e.g. "starts with background, answer comes at 15 s">
Next drill: <persona or question to repeat>
```

"Fix outside the pitch" = a missing fact to research, a demo number to measure, or a core.md field to fill.

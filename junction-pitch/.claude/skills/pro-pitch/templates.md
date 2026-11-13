# /pro-pitch output template

Copy this for each variant. Replace everything in `<>`. Keep the headings so the files look the same.

```markdown
# Pro pitch: <technical | business | partner: Partner Name>

- Date: YYYY-MM-DD HH:MM (Helsinki) · Author: /pro-pitch
- Based on core.md: <"Last updated" value of 04-pitch/core.md, or "core.md not filled; input was: <user's words>">
- For: <audience, e.g. "engineers and the AI / infrastructure partners (Verda, Modal…)" or "Valio Aimo challenge team">

## Pocket card (read just before you walk up)
- They care about: <one line: their goal or their rubric, in their words if we have them>
- Say this: <the one sentence you want them to remember>
- Learn this: <the one thing you need from them, e.g. "which rubric line weighs most">

<technical only:>
Architecture in 3 boxes:
`[<input / data>] → [<model or agent + tools>] → [<output / action + check>]`

## Spoken version (60–90 s · <N> words · ~<T> s)
<plain speech, 140–210 words, short sentences, no bullets.
 Structure: who we are (1 line) → their problem in their words → what we built → how it works / what it is worth
 (variant-specific) → the honest limit → one question back to them.>

## 3-minute conversation guide

**Open (≤20 s)**
<greeting + one-line context + permission: "Do you have three minutes? I would value your view.">

**Listen**
- Ask: <first open question from the list below>
- Then stop talking. Write down their exact words (you will quote them later with permission).

**Adapt**
- If they say <likely reaction 1> → <what you say, 1–2 sentences>
- If they say <likely reaction 2> → <...>
- If they say <a concern or objection> → <thank them, say what we know, say what we will check>
- If they are short on time → <the one question to ask before leaving>

**Close**
- <one line that repeats what you heard: "So if I understand, the key is …">
- **"What would make this useful for you?"**
- <ask to come back: "Can I show you the progress tomorrow morning?">

## 5 questions to ask them
1. <question> — why ask: <what we learn>
2. <question> — why ask: <...>
3. <question> — why ask: <...>
4. <question> — why ask: <...>
5. <question> — why ask: <...>
End with: **"What would make this useful for you?"**

## If they ask you (answer in 20 s: answer, evidence, stop)
- **<question>** → <answer>. <evidence with label>.
- ...

> **After the talk** (within 5 minutes, while you remember the words):
> `/feedback <name or role, company> <what they said, their exact words if possible>`
> Note: similar products they named, what they want to see, any rubric hint.

## Sources
- <number or fact> — <measured | reported | assumed> — <URL, accessed YYYY-MM-DD, or file path>

## Gaps (fill before the next talk)
- [TO FILL: <what>] — answer from: team | partner | research
```

## Spoken-version skeletons (pick the one for the variant, then write it as natural speech)

**Technical (~170 words)**
1. "Hi, I'm Madalina from Hour49. We are building <name> for <challenge>."
2. "The problem: <user> <problem in their words>. <number with label>."
3. "It works in three parts: <box 1>, <box 2>, <box 3>."
4. "We use <data>. We chose <model> because <one reason: speed, cost, accuracy, on-device>."
5. "The hard part is <one thing>."
6. "Where it fails today: <one known failure>. We measure quality by <metric on held-out cases>."
7. "What would you test first if you wanted to break it?"

**Business (~160 words)**
1. "Hi, I'm Madalina from Hour49. We are building <name> for <user>."
2. "Today <status quo>, which costs <time or money, with label>."
3. "With <name>, <the change>. For one <site/team/customer> that is about <saving, with arithmetic and label>."
4. "The buyer is <role>, because <budget or pain owner>."
5. "The first step inside the company is <small pilot>, then <integration>, then <roll-out>."
6. "The main risk is <risk>. We plan to <reduce it>."
7. "Who in a company like yours would need to say yes to a pilot?"

**Partner (~170 words)**
1. "Hi, I'm Madalina from Hour49. We chose your <challenge> because <honest reason>."
2. "Our understanding: <partner> wants <their goal, from their own words or site>. Is that right?"
3. "For <their user>, the pain is <problem>. <their number or ours, with label>."
4. "We built <name>: <one-liner>. It uses your <data / API>."
5. "It hits <rubric criterion 1> by <...> and <criterion 2> by <...>."
6. "What we do not know yet: <gap>."
7. "Which of your criteria matters most to you personally?"

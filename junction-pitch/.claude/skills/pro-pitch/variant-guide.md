# /pro-pitch variant guide

## 0. Language rules

### Banned words → plain swap
| Do not say | Say instead |
|---|---|
| revolutionary, game-changer, disruptive, groundbreaking | say what changes, with a number |
| seamless, frictionless | "in one step", "without re-typing" |
| leverage, utilize | use |
| cutting-edge, state-of-the-art, next-gen | name the model or method |
| AI-powered, smart, intelligent (as praise) | say what the model does |
| unlock, supercharge, empower, transform | "lets X do Y", "saves Z" |
| robust, scalable (without proof) | "tested on N cases", "runs on X" |
| synergy, ecosystem, holistic, paradigm | drop it |
| solution (as filler) | the product name, or "the tool" |
| "we are the first", "no one else does this" | "we found no tool that does X" + source, or drop it |

Grep the output for these words before saving.

### Honest gap lines (use instead of guessing)
- "We have not measured that yet. Our plan is to test it on <N> cases by <time>."
- "That number is our estimate, based on <cited number>. We would like to check it with your data."
- "We do not know that yet. What have you seen in your work?"
- "Today it fails when <case>. We catch that with <check>, or a person decides."

### Respect lines
- Ask permission: "Do you have three minutes? I would value your view."
- Thank and credit: "Thank you, that is useful. May I mention your point in our pitch?"
- Disagreeing: "That is a fair concern. Here is what we see so far … What would convince you?"

## 1. Technical variant (engineers, AI and infrastructure partners)

Must cover, in this order (spoken version: one sentence each; conversation guide: details on demand):
1. **Architecture in 3 boxes.** Draw it as one text line in the file:
   `[input / data] → [model or agent + tools] → [output / action + check]`. Name the real components.
2. **Data used.** Whose data, how much, what period. Partner raw data never goes in this folder: describe it, do not copy it.
3. **Models and why.** The model name and one reason against one alternative (speed, cost, accuracy, latency, on-device).
   Jury asked "Which models and why?" to 3 of 5 finalists in 2025 (pitching.md §0).
4. **What is hard.** One sentence on the technical core.
5. **Known limits and failure cases.** A short failure list with rates if measured (wrong tool choice, made-up values,
   long-task drift, unclear voice input, prompt injection from retrieved text, missing data). If not measured, say so.
6. **How we measure quality.** Held-out test cases (how many), the metric, the baseline it beats.
   Check: does the metric check the *outcome* (the final state, the right item) and not the surface form
   ("an LLM says it looks right")? Can it be gamed? Which hacks did we test (confident-sounding wrong answer, skipped
   steps with correct format, test-set leakage)?
7. Latency (p50/p95) if voice or real time; on-device or cloud; cost per run if known.

Pick the "If they ask you" items from: models and why; where does it fail; how do you evaluate, can it be gamed;
is the eval set held out, how many cases; live or recorded; prototype to production, what is missing; latency.

## 2. Business variant (business people, VCs, managers)

Must cover:
1. **Value in money or time saved.** One number, with the arithmetic shown in the file and every input labelled
   (e.g. "minutes saved per order (assumed) × orders per day (reported, source) × cost per hour (reported, source)").
   If an input is missing, write `[TO FILL]`, never a made-up figure.
2. **Who pays.** The buyer role and the budget it comes from. If different from the user, say both.
3. **Adoption path inside the partner's (or a similar) company:** pilot (scope, length, data needed) → integration
   (which system it plugs into) → roll-out (who signs off). Keep each step one line.
4. **Risks.** 2–3 honest risks (data access, accuracy, staff acceptance, regulation, a big vendor shipping it) and
   what we do about each.
5. **Next step.** One concrete ask: a pilot contact, data access, a second meeting, an introduction.

Pick the "If they ask you" items from: who pays and how much; is this a company, would you keep building it; what is
the moat; how big can it get; who has this problem and how do you know; is this just a feature a big company will ship.

## 3. Partner variant (one partner, tailored)

Must show we understand their business:
1. **Their goal**, in their words: from the partner file, the challenge brief, or their public site (cited).
2. **Their rubric**, mirrored verbatim, with weights if known. Name each criterion where we hit it.
   Past rubric for the same partner: junction-info §2C. Pattern across partners: §2D "Rubric patterns".
3. **Their data / API / hardware** we used, and how.
4. **How it plugs into their stack tomorrow**: system, format, effort, what is missing.
5. **What we need from them to pilot.**
6. Any feedback already given by their people (feedback/log.md), quoted with "you told us…" only if it was this person,
   or "your colleague <role> told us…".

Pick the "If they ask you" items from pitching.md §1c and §4.3 general questions ("what was built this weekend",
"next 48 h", "why this problem"), plus their rubric lines.

## 4. Question bank (questions to ask THEM)

Pick 5 for the audience, adapt them to our idea, keep them open. Never ask what feedback/log.md already answers.

**Technical**
- "Where do you think this would break first?"
- "How would you measure if it works? What baseline would you compare it to?"
- "If you tried to game our metric, what would you do?"
- "Would you pick a different model or setup for this? Why?"
- "What would worry you about running this in production?"
- "What latency or cost would be acceptable for you?"

**Business**
- "Who in a company like yours owns this problem today?"
- "What does this problem cost you now, roughly, in time or money?"
- "What would a first pilot need to show to be worth it?"
- "What has stopped similar tools from being adopted?"
- "Who would need to say yes, and what would they ask?"
- "Which similar products have you seen? What did they miss?"

**Partner**
- "Which of your criteria matters most to you personally?"
- "What does a good result look like for your team after this weekend?"
- "Which part of the process hurts most for your people today?"
- "Is our reading of your data right? What are we missing?"
- "What would make it easy to plug into your systems?"
- "Can we come back tomorrow morning to show progress?"

**Always last:** "What would make this useful for you?"

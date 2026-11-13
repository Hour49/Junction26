---
name: pro-pitch
description: Write the professional walk-up pitch for mentors, partner representatives and judges, in three variants (technical, business, partner), each with a 60–90 s spoken version, a 3-min conversation guide and 5 questions to ask them. Writes 04-pitch/scripts/pro-pitch-<variant>.md from 04-pitch/core.md and 03-research/**. Use when Madalina is about to talk to a mentor, partner rep, engineer, VC, manager or judge; she picks the variant, no names needed.
when_to_use: 'pro pitch, pitch to a mentor, talk to the partner, talk to the judge, "what do I say to the Valio person", technical pitch for the engineers, business pitch for the VC, walk-up pitch, mentor round'
argument-hint: "[technical | business | partner <name>] (empty = all)"
allowed-tools: Read Write Edit Glob Grep WebSearch WebFetch
---

# /pro-pitch: the professional walk-up pitch

Madalina walks up to a mentor, partner representative or judge. She needs something short she can say, a guide
for the next 3 minutes, and good questions so she leaves with useful feedback. This skill writes that.

Input: `$ARGUMENTS`. It may be short and messy ("partner valio", "tech for the verda guy", "biz", empty).

## Tone rules (apply to every line written)
- Diplomatic and respectful. She is asking for their view, not selling to them.
- Plain, common words. Short sentences (max ~15 words). Many listeners are not native English speakers.
- Precise: say the number, the unit, the source. No hype. Banned words and the plain swap are in
  [variant-guide.md](variant-guide.md) §0.
- Honest about limits. "We have not measured that yet" is better than a guess dressed as a fact.
- Real data only. Every number comes from core.md, `03-research/sources.md` or a 03-research file, and keeps its label
  (measured / reported / assumed). Never invent people, quotes, numbers, customers or companies.

## Step 1. Parse the argument (no questions unless blocked)
| Input looks like | Variant(s) |
|---|---|
| `technical`, `tech`, `engineer`, `infra`, `AI`, a tech partner name (Verda, Modal, NVIDIA, Featherless, DeepMind…) without "partner" | technical |
| `business`, `biz`, `VC`, `investor`, `manager`, `money` | business |
| `partner <name>`, or just a challenge-partner name (Valio Aimo, S-Pankki, AstraZeneca…) | partner, for that name |
| anything else (a person's name, "mentor", "judge") | ask ONE question: "Technical, business, or partner <company>?" Do not look the person up |
| empty or `all` | technical + business + partner (for the partner in core.md "Challenge / partner") |

"Partner" = someone from the company that sponsors our challenge (or another challenge we talk to). Technical and
business are for anyone else: pick by what the listener cares about, not by who they are.

Make a slug from the partner name: lower case, kebab-case (`Valio Aimo` → `valio-aimo`).

## Step 2. Read the inputs
Read in this order. Skip any file that does not exist; do not stop.
1. `04-pitch/core.md`. Note its "Last updated" value for the header line.
2. `03-research/sources.md` (the numbers you may use).
3. `03-research/feedback/log.md`: newest entries first. Use what mentors already told us. Do not repeat a question that
   was already answered; ask the follow-up instead.
4. Partner variant: the partner file. Look for, in order:
   `03-research/challenges/<slug>/partner.md`, then `03-research/challenges/<slug>*.md` and
   `03-research/challenges/*<slug>*.md` (older flat layout; /challenge-pick writes `<partner>-<challenge>/`).
   Also read the partner's past-edition lines in `00-event/junction-info.md` §2C and §2D (grep the partner name).
5. Other research: Glob `03-research/**/*.md`, skip the READMEs, and read files whose names match the idea, the user,
   the market or the competitors. Grep for numbers (`€`, `%`, `min`, `FTE`, `hours`).
6. Technical variant: also grep 03-research and 04-pitch for `architecture`, `model`, `eval`, `latency`, `accuracy`.

**If core.md is still the TEMPLATE** (Status: TEMPLATE, or most fields are "—"):
- If `$ARGUMENTS` or the chat holds an idea, use it and mark every derived line `[from chat, not in core.md]`.
- Otherwise ask ONE question: "What is the idea in one sentence, and which challenge?" Then continue.

**If a fact is missing** (no eval numbers, no pricing, no architecture), do not fill it with a guess. Write
`[TO FILL: <what> — ask the team]`. Anyone on the team, Madalina included, may fill it; never assign a gap to one person.
Then write the honest spoken line for that gap (variant-guide.md §0 "Honest gap lines").

## Step 3. Partner research (partner variant only, only if the partner file is missing or has no business goals)
- At most 3 web calls in total (WebSearch or WebFetch). Look for the partner's own public goals: strategy page, annual report, press release,
  the challenge brief. Prefer the partner's own site.
- Cite each fact with URL and access date in the output's Sources section. Mark single-source facts UNVERIFIED.
- If two sources disagree (e.g. two product counts on the partner's own site), do not use that number in speech;
  list both in Sources.
- Company self-reported figures (own surveys, NPS) are "reported, company's own"; avoid them in speech unless needed.
- Append one line per new fact to `03-research/sources.md` (format in `03-research/README.md`). Only append; never
  edit existing lines. Create the file with a header line if it does not exist.
- In the chat summary, suggest creating the partner file properly (/challenge-pick or /market-scan).

## Step 4. Write each variant
Use the template in [templates.md](templates.md) and the content checklist for the variant in
[variant-guide.md](variant-guide.md) §1–§3.

Every file has, in this order:
1. Date line and "Based on core.md" line.
   Technical variant only: the 3-box architecture line goes right after the Pocket card.
2. **Pocket card**: 3 lines to glance at just before walking up (who they are, the one thing to say, the one thing to learn).
3. **Spoken version, 60–90 s**: 140–210 words (speaking speed 140 words per minute, same as /pitch). Count the words (every
   whitespace-separated token) and write the count and the time (words ÷ 140 × 60 s) in the heading. Write it as speech: "we", "you", short sentences, no bullet points, no
   abbreviations she would stumble on.
4. **3-min conversation guide**: Open (≤20 s) → Listen (ask, then stop talking) → Adapt (3–4 "If they say… → you say…"
   branches) → Close. She talks less than half the time.
5. **5 questions to ask them**: chosen for this audience, from the bank in variant-guide.md §4, adapted to our idea.
   Each question gets a short "why ask" note. The conversation always ends with:
   **"What would make this useful for you?"**
6. **If they ask you**: 4–6 likely questions with 20-second answers (answer, evidence, stop), taken from
   `01-playbooks/pitching.md` §4.3 for this audience.
7. **After the talk** box: the /feedback reminder (exact text in templates.md).
8. **Sources**: every number used, with its label and URL or source file.
9. **Gaps**: every `[TO FILL]` item, and where the answer is: the team, the partner, or research.

## Step 5. Save
- Path: `04-pitch/scripts/pro-pitch-technical.md`, `04-pitch/scripts/pro-pitch-business.md`,
  `04-pitch/scripts/pro-pitch-partner-<slug>.md`.
- If the file already exists, do not overwrite it (Madalina may have edited it). Write the next free version:
  `-v2`, `-v3`… Say in the chat which version is newest.

## Step 6. Check before you reply
- Spoken version is 140–210 words. Count again.
- No banned word from variant-guide.md §0. Grep the file for them.
- Every number in the file appears in the Sources section with a label. No number without a source.
- No invented name, quote, customer or company. Quotes only from feedback/log.md or a cited source.
- The 5 questions are questions to THEM, open (not yes/no), and the last line of the guide is
  "What would make this useful for you?".

## Step 7. Chat reply (short)
- One line per file written, with its path and the spoken version's word count.
- The top 2–3 gaps (`[TO FILL]`) and where the answer is (team, partner, research).
- The reminder: **"After each talk, log it: `/feedback <who, role> <what they said>`."**
- Next skills: /feedback after the talk; /jury-drill to practise the questions; /pitch or /deck when core.md changes;
  /fact-check before a number goes on a slide.

## Additional resources
- Output template and the /feedback reminder text: [templates.md](templates.md)
- Per-variant checklist, banned words, honest gap lines, question bank: [variant-guide.md](variant-guide.md)
- Source playbook sections: `01-playbooks/pitching.md` §0, §1a, §1c, §4.3.

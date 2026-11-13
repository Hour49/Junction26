# Human voice: last check for anything Madalina will say out loud

Status: DRAFT, not wired into any skill yet. Bogdan reviews and decides (TODO.md "For Bogdan to review").

Use it as the last step of every skill that writes spoken words: /pitch, /easy-pitch, /pro-pitch, /deck (notes),
/jury-drill (answers), /team-intro. The word swaps stay where they are (`pitch/plain-words.md`,
`easy-pitch/plain-words.md`, `pro-pitch/variant-guide.md` §0). This file checks what those lists miss:
**patterns** that make a script sound written by a machine, and what makes it sound like a person.

Facts never change in this pass. Only wording. No new numbers, people or quotes.

## 1. Remove: patterns that sound machine-written

| Pattern | Example | Fix |
|---|---|---|
| "Not just X, it's Y" / "It's not about X, it's about Y" | "It's not just an app, it's a safety net." | Say Y plainly: "It warns the picker before the order leaves." |
| Everything in threes | "Faster, cheaper, and smarter." | Keep the one that is true and measured. |
| "Imagine a world where…" / "In today's fast-paced world…" | | Start with the real person and moment. |
| Stacked questions | "What if…? What if…? What if…?" | One question at most, then the answer. |
| Big empty closers | "Together, we can change the future of retail." | End with the ask and the name. |
| Dramatic dashes and colons in speech | "One thing changed — everything." | Two plain sentences. |
| Every sentence the same length | 10 sentences of 9–11 words | Mix: some 4 words, some 14. A short one after the number. |
| Abstract people | "users", "stakeholders", "customers" | The role: "a picker", "a parent ordering food". |
| Hedge stacks | "This could potentially help to possibly reduce…" | One honest hedge: "We think it cuts errors. We have not measured it yet." |
| Praise for ourselves | "Our innovative, powerful tool…" | Show it in the demo; say what it does. |
| Signposting | "Let me walk you through…", "It's worth noting that…" | Cut it; just say the thing. |

## 2. Add: what makes it sound like a person

- **One real moment.** A person, a place, a time: "Last Tuesday a picker in <city> told us…". Only from
  `03-research/feedback/log.md` or a cited source; otherwise describe the situation without claiming a conversation.
- **Contractions.** we're, it's, don't, they've. Written English drops them; spoken English uses them.
- **First person, specific.** "We tried X. It failed when Y. So we did Z." Better than "the system uses Z".
- **Numbers with units people feel.** "10 minutes a day", "1 in 20 orders". Say the key number twice: once in the
  problem, once in the close.
- **One small honest or light line.** "It still gets this wrong sometimes. Here's how we catch it." Humour only if it
  came up naturally in rehearsal.
- **Words the users used.** Reuse "Words people actually use" from `03-research/pain-points/*/summary.md`.

## 3. The out-loud test (always)

1. Read the script aloud once, at pitch speed (140 words/min).
2. Mark every place you stumble, breathe in the middle of a sentence, or sound like you are reading.
3. Rewrite only those lines. Do not practise a hard line; replace it.
4. Ask: "Would I say this to a friend at the table?" If not, rewrite it.

## 4. How a skill would use this (proposal)

Last step before saving: check the script against §1 and §2, fix lines, and add a short
"Human-voice check" note at the end of the file: what was changed (max 5 lines). Facts and word counts are
re-checked after the rewrite (the timing script for /pitch, `readability.py` for /easy-pitch).

## 5. Open points for the reviewer

- Wire it into all six skills, or only /pitch and /easy-pitch first?
- Merge the three word lists into this file (one list), or keep them separate?
- Should `readability.py` also flag some §1 patterns automatically ("not just", "imagine a world", 3+ questions in a row)?

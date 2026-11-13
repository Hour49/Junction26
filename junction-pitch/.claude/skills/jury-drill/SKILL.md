---
name: jury-drill
description: Judge our idea the way the Junction 2026 stage jury will, and list the questions most likely to come up in the 3 minutes of jury Q&A after the stage pitch, ranked, each with why it is likely (real 2025 jury questions in 02-reference, the 2026 jurors' stated criteria, weak spots in our idea). Writes 04-pitch/scripts/qa-prep.md. No answers and no quiz by default. Practice modes (live, rapid) run only when Madalina asks for them by name.
when_to_use: what will the jury ask, likely questions, jury questions, Q&A prep, stage questions, judge my idea, weak spots of the idea, prepare for Q&A. Practice only on explicit request - "jury-drill live", "jury-drill rapid", "test me", "quiz me", "drill me".
argument-hint: "(empty) = analyse idea + likely questions | live [persona] | rapid"
---

# /jury-drill

Input: `$ARGUMENTS`. Madalina types short and messy. Map it to a mode:
- **Default: analyse.** Empty, "questions", "bank", "prep", "what will they ask", an idea in a few words, or
  anything unclear → **analyse** (below). Never start a quiz unless she asks for one.
- `live`, "test me", "drill me", "quiz me", "ask me", "grill me" → **live** (Mode 2). Only on these words.
- `rapid`, "rapid fire", "10 fast questions" → **rapid** (Mode 3). Only on these words.

Personas, aliases and the 2025 evidence table (used by live and rapid): [personas.md](personas.md).
File format and the scoring guide: [templates.md](templates.md).

## Rules for every mode
- Follow the project CLAUDE.md: real data only, plain common English, short sentences.
- What we claim comes only from `04-pitch/core.md` and `03-research/**`. Never invent a number, user, quote,
  result or teammate fact.
- Never present a real judge's words as a quote unless they are in `00-event/junction-info.md` §2A with a source.
  Anything about how a judge thinks is "assumed from public role".
- Questions are for the whole team. Never say who should answer.
- Output files start with a `Date:` line and a `Based on: 04-pitch/core.md, <Last updated value>` line
  (core.md still a template → `Based on: core.md TEMPLATE; idea from chat: "<her one line>"`).

## Step 0 (all modes): load the idea
1. Read `04-pitch/core.md`. Note its "Last updated" value and the "Challenge / partner" line.
2. Read `03-research/feedback/log.md` if it exists: questions already heard from mentors, partners or jury are
   high-likelihood.
3. If core.md is still the TEMPLATE (most fields "—"): use the idea from her input or the chat and label the output
   "idea from chat, not yet in core.md". If there is no idea anywhere, ask once: "Type the idea in one line."
4. Partner: the matching folder in `03-research/challenges/` (Glob `*<partner>*`): take the rubric word for word.
   No file → the partner's row in `00-event/junction-info.md` §2B/§2C, labelled with its year.

## Mode 1: analyse (default)

No subagents: this is one careful reading pass.

1. **Read the evidence** (all of it; about 6k words):
   - `02-reference/jury-questions.csv`: the 17 real questions the 2025 stage jury asked, with categories.
   - `02-reference/pitch-analysis.md` §1, §3, §5 (what the top 5 did; question types and counts; lessons).
   - `02-reference/pitch-breakdown.csv`: per team, what was shown and what failed (live vs recorded, concept video).
   - `00-event/junction-info.md` "How judging and pitching work" (2026 stage rules: exactly 3 min, then 3 min Q&A) and §2A (2026 jurors and
     their stated criteria).
   - Skim the transcript of the 2025 team closest to our idea in `02-reference/pitch-transcripts/`.
2. **Judge the idea** as the jury would. For each lens, one line: strong, weak or missing, and why (cite the
   core.md field or research file):
   problem worth solving (who, how many, how we know) · what is real (live demo, built this weekend) ·
   technical choices (models, stack, why) · where it fails and how we measure quality · real user and coming back ·
   who pays / next step with the partner · partner rubric fit · team (who did what).
3. **List the likely questions.** 15–20 questions, as a judge would say them out loud: short, plain.
   - Always include the 2025 patterns that fit any team (asked again and again): who did what; built this weekend
     or brought code; live or recorded; which models/stack and why; next 48 hours or most valuable use case.
   - Add questions from the 2026 jurors' stated criteria (§2A) that hit our idea.
   - Add questions aimed at every **weak or missing** lens from step 2. These are the most dangerous ones.
   - Make each question specific to our idea ("Why would a picker trust it over the scanner?", not "Why would users
     trust it?").
4. **Rank** by likelihood: High = asked of 3+ of the 5 teams in 2025, or a jury criterion that hits a weak lens;
   Medium = asked once in 2025, or a weak lens; Low = plausible, no evidence. Mark the **top 5** (realistic: the
   jury asks about 3–4 questions in 3 minutes).
5. **Write** `04-pitch/scripts/qa-prep.md` in the format of [templates.md](templates.md) §1. Questions only:
   no model answers unless Madalina asked for answers. If the file exists, write the next free `qa-prep-vN.md`.
6. **Reply in chat** (≤12 lines): the file path, the idea verdict in one line (its strongest and weakest lens),
   the top 5 questions, and the gaps to close. Do not ask her to answer them.

## Mode 2: live [persona]

Interactive. One question per message. Never ask two questions at once.

1. Persona: the slug or alias from the input (personas.md table). `mixed` = rotate through all seven, starting with
   the one the 2025 evidence and core.md gaps make most dangerous.
2. Questions: take the ones that fit that persona's lens from `04-pitch/scripts/qa-prep.md` (latest `-vN`) if it
   exists, most likely first; else write them yourself from the persona card, core.md and the 2025 evidence table. Default length
   6 questions; Madalina can say "more", "stop", "skip" or "switch to <persona>" at any time.
3. Open with one line: "Playing <name>'s angle (<style, assumed>). 6 questions. Type or paste your answer; 'stop'
   ends it." Then ask **Q1** in the persona's voice: short, spoken, one sentence or two.
4. **Wait for her answer.** Typed or pasted voice-to-text is fine; ignore typos and filler when judging clarity of
   meaning, but count every spoken word for length.
5. Score with the card and guide in [templates.md](templates.md) §2: clarity, directness, length, evidence,
   honesty, each 1–5 with the word count and seconds. Then the best part, the one fix, and a better version **in
   her own words**: reuse her phrases, answer first, cut filler, add evidence only from core.md or `03-research/**`,
   otherwise mark `[GAP: need ...]`.
6. **Follow-up when she dodges:** directness ≤2, or the answer is about something else, or it claims a fact with
   no source. Ask one sharp follow-up in persona ("You did not say who pays. Who pays?") before the better version.
   At most one follow-up per question; score the pair together.
7. Next question. Keep it moving: the score card stays under 12 lines.
8. **At the end** (after the last question or "stop"):
   - Write the session to `04-pitch/scripts/qa-weak-spots.md` in the format of [templates.md](templates.md) §3:
     every question with any score ≤3, the patterns, and the next drill. Create the file if needed; add the new
     section under the header; never edit older sessions.
   - Chat summary (≤8 lines): average per dimension, the 2 weakest questions, the one habit to fix, the file path,
     and next: `/jury-drill live <persona>` again, `/fact-check` or research for any GAP, `/pitch` if the gap
     belongs in the script.

## Mode 3: rapid

Ten fast questions, 15-second answers. The goal is speed and directness, not depth.

1. Pick 10: the top 10 from `qa-prep.md` if it exists; else 5 from the 2025 evidence table (who did what, live or
   recorded, which models and why, built this weekend, next use case) and 5 from core.md's weakest fields across
   different personas. Shuffle the order.
2. Say once: "Rapid: 10 questions, 15 s each (≈38 words). Answer one at a time, or type 'all' to get the list and
   paste numbered answers."
3. One at a time: ask "Q<n>/10 (<persona>): <question>". After each answer reply in **3 lines max**:
   `<words> words ≈ <s> s · direct <n>/5 · evidence <n>/5` / `Fix: <6–10 words>` / `Try: "<≤38-word version>"`.
   No follow-ups in rapid mode. Then the next question at once.
4. `all` option: list the 10, take her numbered answers in one paste, then give the 3-line score for each.
5. End: total time estimate, how many answers were ≤15 s and answered in the first sentence, the 3 slowest.
   Save every answer with directness or length ≤3 to `04-pitch/scripts/qa-weak-spots.md` (section title
   "rapid"). Chat summary with the file path and the next drill.

## Additional resources
- [personas.md](personas.md): the 7 personas, aliases, probes, assumed styles, and the 2025 Q&A evidence table.
- [templates.md](templates.md): the qa-prep format, live scoring card and guide,
  weak-spots log format.
- Evidence: `02-reference/jury-questions.csv`, `pitch-analysis.md`, `pitch-breakdown.csv`, `pitch-transcripts/`;
  `01-playbooks/pitching.md` §0 point 2 and §4.3.

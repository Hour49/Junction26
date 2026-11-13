---
name: team-intro
description: Writes how team Hour49 is presented, built on how the four of us complement each other (not on past hackathon wins). Pitch mode (default) gives the 10-second team line for the 3-min stage pitch, the team slide text, the "who did what this weekend?" answer and a 30-second team intro for mentors and partners. Description mode gives written team descriptions (one line, short, medium) for forms, the submission, the website or LinkedIn. Use when Madalina says "team intro", "introduce the team", "who are we", "team slide", "who did what", "team description", "about us".
argument-hint: "[description] [notes, e.g. 'Bogdan built the agent, Bea the app'] [angle: past wins | agent workflow]"
---

# /team-intro

Input: `$ARGUMENTS`. Short and messy is fine.
- First word `description` → **Description mode**. Anything else (or empty) → **Pitch mode**.
- Notes about who did what this weekend → use them in "Who did what". Without notes, leave `[fill in]`.
- `angle: past wins` or `angle: agent workflow` → add that angle (see "Optional angles"). Default: no angle.

## Sources (the ONLY sources for team facts)
- `05-team/hour49.md` §0 "How we complement each other": what each person brings, what to keep in mind, and the
  website voice. This comes first.
- `05-team/hour49.md` §1: employers and the track record (only for an angle that asks for it).
- `04-pitch/core.md`: the idea name and the one-liner, if filled. Still the TEMPLATE → write `[IDEA NAME]`.
- `00-event/junction-info.md` "How judging and pitching work": the 2026 stage rules (3 min, one person on stage advised).

## Rules
- **Lead with how we complement each other**: problem and people (Madalina) → AI and backend (Bogdan, Tudor) →
  frontend and design (Tudor, Beatrice) → organising (Beatrice). Every line answers "why these four for this idea?".
- **Not about hackathons.** No track record, no list of past events, unless the `past wins` angle is asked.
- **Keep-in-mind facts stay out of the pitch.** The "Keep in mind" column of §0 (finance interest, Madalina's own
  dev/AI knowledge) is never written into the stage pitch, the team slide or the descriptions. Use it only to
  suggest things in chat, e.g. "this is a FinTech challenge: Bogdan and Tudor's finance interest is worth
  mentioning to the partner, if you agree".
- Never invent a person, role, skill, award or weekend task. Weekend tasks are only known from Madalina's notes.
- Plain, common English. Short sentences. Spoken timing at 140 words/min (10 s ≈ 23 words, 20 s ≈ 47, 30 s ≈ 70).
- Questions are for the whole team: never say who answers. One person on stage is advised (2026 rules).
- Tone: warm and a little playful, like the website ("We live in the 49th hour"); never jokes about the jury.
- Never overwrite: if the output file exists, write the next free `-vN`.

## Pitch mode (default) → `04-pitch/scripts/team-intro.md`
File header: `Date: <YYYY-MM-DD HH:MM> (Helsinki)` and `Based on core.md: <Last updated value or "TEMPLATE">`.

1. **Team line for the stage pitch (10 s, ≤23 words).** Fits the 10-second team slide of the 3-min deck. One
   sentence on how we complement each other, linked to the idea. Give 2 options.
2. **Team slide text.** Four lines, `Name — what they bring` (≤8 words each), from §0. This matches `Team:` in
   the /deck outline.
3. **"Who did what this weekend?"** The most asked jury question in 2025 (3 of 5 teams; 02-reference/
   jury-questions.csv). A 20-second spoken answer (≤47 words), plus a table: person · what they bring · what they
   built this weekend (`[fill in]` unless Madalina's notes say). Add one line: what was built from scratch this
   weekend and anything reused (juries asked "built this weekend?" of 4 of 5 teams).
4. **30-second team intro** (≤70 words) for a mentor or partner who asks "who are you?". Same complement story,
   one sentence per person.
5. **Facts used:** each fact with its section in `05-team/hour49.md`.

## Description mode → `04-pitch/submission/team-description.md`
Written text, not speech. Same complement story, in the website voice.
1. **One line** (≤20 words): e.g. for a form field or a slide footer.
2. **Short** (≤50 words): submission form "about the team".
3. **Medium** (~100 words): website, LinkedIn post, or a partner email. May open with the website's
   "48 hours / the 49th hour" line.
4. **Per person** (≤20 words each): for member cards.
5. **Facts used**, as in pitch mode.

## Reply in chat (short)
File path, the two stage team-line options, what Madalina must fill in (weekend tasks), and any keep-in-mind
suggestion that fits the chosen challenge. Next: `/deck` (team slide), `/pitch stage`.

## Optional angles (only when asked)
- `past wins`: one line, at most one win: "Done won first place in AppDev at PoliHack Cluj" (§1). Never a list.
- `agent workflow`: one sentence: we run AI coding agents while we talk to users and partners (§2). Only in the
  30-second intro or descriptions, never in the 10-second line.

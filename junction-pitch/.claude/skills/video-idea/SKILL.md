---
name: video-idea
description: Write 3-5 distinct concept ideas for the ~2-minute Junction submission video, with hook, timed shot list, narration outline, where the one number appears, demo moment, what can be filmed at the venue, effort, risk, and a recommendation. IDEAS ONLY, no production or editing. Use when Madalina says "video idea", "video concepts", "what should our video be", "submission video", "2-minute video", "demo video ideas".
argument-hint: "[optional notes, e.g. 'we have a voice demo', 'make it funny']"
allowed-tools: Read Write Glob Grep
---

# /video-idea: concepts for the 2-minute submission video

Ideas only. No scripts to record, no editing, no tools. Real video work is on hold (see TODO.md). Output is a menu of concepts plus one recommendation, so the team can pick in 5 minutes.

Input: `$ARGUMENTS` (optional, short and messy is fine) plus `04-pitch/core.md`.

## Steps

1. **Read core.md** (`04-pitch/core.md`). Note its "Last updated" value.
   - If it is still the empty template (fields are "—"), ask ONE question: "What is the idea, the user, and the one number?" and use her answer. Mark every output "based on: user's words, core.md not filled".
   - If the problem number is missing, write "[number: pending]" in its place. Never invent one.
2. **Read optional notes**: `$ARGUMENTS`, and the last entries of `03-research/feedback/log.md` if it exists (jury or mentor comments about the pitch can shape the angle).
3. **Learn from real examples** (read quickly, do not copy):
   - `02-reference/pitch-transcripts/2025-wavelet-submission-video.md` (1st): hook in 5 s, shows real build, honest "we did 10x more".
   - `02-reference/pitch-transcripts/2025-loredash-submission-video.md` (2nd): relatable hook (Wikipedia rabbit hole), then product.
   - `02-reference/junction-videos.md` "Winners' submission videos" and "Other team demos" (note short ones, e.g. 0:20 and 1:30, are fine).
   - `01-playbooks/pitching.md` section 1e (video timeline, target 1:50-2:00, burned-in captions) and the audio-failure rule (2 of 5 finalists in 2025).
   - Fact: the 2024 winner used an AI-generated rap video (junction-info.md section 2C). Cite it only as such.
4. **Write 3-5 concepts**, each a different style. Mix at least 3 of these:
   - Problem-scene story
   - Live product walkthrough
   - "Day in the life" before/after
   - Fun or entertaining angle (rap, parody, game-show, mock ad)
   - Data-reveal (the number is the star)
   Fit the styles to the idea. Drop one that does not suit it and say why in one line.
5. **Pick a recommendation** and say why in 3-4 bullets (fit to jury criteria, effort at the venue, risk, memorability).
6. **Save** to `04-pitch/video/ideas.md`. If it exists and was edited by a human, write `ideas-v2.md` instead. Never overwrite.
7. **Chat summary**: concept names in one line each, the recommendation, the file path, and next steps. Suggest: `/pitch` or `/easy-pitch` for the spoken script, `/deck` for the stage slides, `/fact-check` for the number.

## Hard rules for every concept

- **Silent-first.** The video must work with no sound. Every spoken line is also a burned-in caption, in short plain lines. Music is optional and never carries meaning. (Audio failed for 2 of 5 finalists in 2025.) Any funny or rap concept must be readable as captions.
- **Hook in the first 5 seconds.** Name the exact first frame and first caption.
- **The one number appears on screen, big, with its label** (measured / reported / assumed) and a small source line. It comes from core.md. Never invent it.
- **The real demo moment is on screen by 0:40** (pitching.md 1e), as a real screen recording of the real product (or clearly labelled mock-up if the product is not ready, say so). Do not fake it.
- **Total about 2:00** (target 1:50-2:00). Shot seconds must add up.
- **Only what can be filmed or recorded at the venue** (Hype Areena, Espoo; a phone, a laptop, teammates, a whiteboard, the product on screen). No paid actors, no studio, no drone. Name any needed asset and where it comes from. Stock or AI-made footage must be labelled as such.
- **Plain, common English.** Short sentences. No buzzwords. No invented people, quotes, companies or numbers. If a persona appears, say it is a role played by a teammate.
- Real people on screen: use teammates only. Never use partner raw data or secrets in frames.

## Output template (`04-pitch/video/ideas.md`)

Start with:

```
# Video ideas: <idea name or "untitled">
Date: YYYY-MM-DD HH:MM (Helsinki)
Based on core.md: <Last updated value, or "not filled; used user's words">
One number used: <number> (<measured|reported|assumed>), source: <line in 03-research/sources.md or "pending">
Rules: silent-first, burned-in captions, about 2:00, ideas only.
```

Then a one-line table of all concepts (name, style, effort, risk), then each concept using the block in [concept-template.md](concept-template.md). End with `## Recommendation` and `## Open questions` (max 3, only real blockers).

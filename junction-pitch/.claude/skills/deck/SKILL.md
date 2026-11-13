---
name: deck
description: Build the stage deck mock-up from 04-pitch/core.md - a slide-by-slide outline (04-pitch/deck/outline.md - title, very few words on screen, one number per slide, the visual, plain-English speaker notes, seconds per slide; a 3-min core cut and a 5-min cut) and a self-contained offline HTML slideshow (04-pitch/deck/mock/index.html - 16:9, arrow keys and click, presenter view with notes, per-slide and total timers, placeholders for app screenshots). On re-run it writes -v2, -v3 files and keeps the old ones. '/deck slides' builds or updates the real Google Slides deck (link in 04-pitch/deck/slides-link.md), '/deck export' saves PDF + pptx, '/deck canva' makes optional visuals. Use on Friday night after core.md is filled, and again whenever the idea, a number or the demo changes.
when_to_use: deck, slides, google slides, export the deck, deck pdf, canva visual, slide deck, stage deck, deck mock-up, outline the slides, make the slides, update the deck, regenerate the deck, present from laptop, slideshow, 3 min deck, 5 min deck, speaker notes, presenter view, practice with timer
argument-hint: "[slides | export | canva | optional note on what changed, e.g. 'new number from Valio mentor']"
allowed-tools: Read Write Edit Glob Grep Bash(python3 *) Bash(~/.cache/deck-venv/bin/python *) Bash(sha256sum *) Bash(jq *) Bash(base64 *) Bash(TZ=Europe/Helsinki date *) Bash(ls *) Bash(mkdir *) mcp__claude_ai_Google_Drive__create_file mcp__claude_ai_Google_Drive__read_file_content mcp__claude_ai_Google_Drive__download_file_content mcp__claude_ai_Google_Drive__get_file_metadata mcp__claude_ai_Google_Drive__search_files mcp__claude_ai_Canva__search-designs mcp__claude_ai_Canva__generate-image mcp__claude_ai_Canva__get-generate-image-job mcp__claude_ai_Canva__create-design mcp__claude_ai_Canva__get-create-design-async-job mcp__claude_ai_Canva__get-export-formats mcp__claude_ai_Canva__export-design
---

# /deck

Input (may be empty or messy): `$ARGUMENTS`
Now (Helsinki): !`TZ=Europe/Helsinki date '+%Y-%m-%d %H:%M'`

Goal: a deck Madalina can present from her laptop tonight, then keep in step with core.md. The real deck goes to Google Slides with `/deck slides` (see the last section).

## 1. Read (only what exists; skip missing files silently)

1. `04-pitch/core.md`. If it still says `Status: TEMPLATE` and `$ARGUMENTS` gives no idea, stop and ask one question: "What is the idea in one sentence, and which challenge?" If the input gives the idea, go on and mark every field you had to guess as `[[need: …]]`.
2. `03-research/sources.md`: the only allowed source of numbers. Also skim `03-research/market/`, `03-research/users/` and `03-research/feedback/log.md` for a sourced number, a real user quote, and feedback that should change a slide.
3. `04-pitch/deck/`: list it. Find the newest outline (`outline.md`, `outline-v2.md`, …) to see what changed.
4. `04-pitch/deck/mock/assets/`: list it to know which screenshots exist.
5. Method (already distilled; open the playbook only if you need more): [finalist-patterns.md](finalist-patterns.md) and `01-playbooks/pitching.md` §2 (slide table) and §1(d) (3-min script skeleton).
6. Team facts for the team slide: `05-team/hour49.md` §1 and any `04-pitch/scripts/team-intro*.md`.

## 2. Decide the file names (never overwrite)

```bash
python3 .claude/skills/deck/build_mock.py --next 04-pitch/deck
```
It prints `outline.md` on the first run, then `outline-v2.md`, `outline-v3.md`, …
The mock follows the outline name: `outline-v2.md` → `mock/index-v2.html`. Old files stay.

## 3. Write the outline

Follow [outline-format.md](outline-format.md) exactly (the generator parses it). Start from its skeleton.
- Header: date line, `Based on core.md: <its "Last updated" value>`, version, and one line "Changed since last version".
- One cut: the 3-min stage pitch, 180 s in total (2026 rule: exactly 3 min, mic killed at time, then 3 min of jury Q&A; 00-event/junction-info.md). All slides are `Cut: both` with `Seconds: <n>`, plus backup slides for the Q&A. Add `Cut: 5-min` slides or `Extra for 5-min:` only if Madalina asks for a longer version.
- Map core.md to slides: hook ← demo wow / problem in their words; problem ← problem number; user ← target user; solution ← name + one-liner + how it works; demo ← demo "wow" moment; why it holds ← proof; market ← market + ask; close ← one-liner + ask.
- **On screen:** ≤12 words, one idea, one number per slide. Speaker notes carry the rest.
- **Numbers:** only from `sources.md` or core.md, with their label (measured / reported / assumed) and source in `Source:`. Mark single-source as UNVERIFIED. No number → `[[need: …]]`. Never invent a number, a quote, a user or a company.
- **Quotes:** English only on slides (Madalina, 2026-11-10). A Finnish or other non-English quote goes on the slide as our
  English translation; the original stays in the `03-research/` file it came from, and `Source:` links to it.
- **Notes:** what she says, in plain spoken English, short sentences, no buzzwords ("revolutionise", "leverage", "seamless"). About 2.3 words per second.
- **Demo slide (required):** `Layout: demo`, `Video: assets/demo.mp4` (silent, captions burned in, 40–50 s, wow in the first 15 s) and `Fallback: assets/demo.gif` (or a screenshot). Plus `Backup A` with 3 key screenshots. She narrates live.
- **Team slide (required):** `Layout: team`. Until the team intro is defined (TODO.md "Team presentation", /team-intro), fill `Team:` with names and site roles from `05-team/hour49.md` and `[[what they built here]]`, and say in the notes that it is a placeholder.
- **Badges:** `Built this weekend` on real footage, `Vision` on concept art.
- **Screenshots:** the teammate's HTML app mock-up goes in `04-pitch/deck/mock/assets/`. Name files after the slide (`app-home.png`, `demo.gif`, `team-1.jpg`, `qr.png`). Missing files show as dashed placeholders with the expected path, so she knows what to capture.
- Keep the backup slides (demo screenshots, built this weekend vs before, who did what).

## 4. Build the HTML mock-up

```bash
python3 .claude/skills/deck/build_mock.py 04-pitch/deck/<outline file>
```
- It writes `04-pitch/deck/mock/index[-vN].html` and creates `mock/assets/`. Python stdlib only, no internet. `--google-fonts` adds the Hour49 fonts (Michroma, Space Mono) but needs internet; leave it off for offline use.
- Read the `WARN` lines. Fix the outline (too many words, more than one number, notes too long, 3-min total not 180 s, number without source) and rebuild. `[[placeholder]]` warnings may stay: list them in the summary as "still needed".
- Sanity check: `python3 -c "import html.parser,sys; html.parser.HTMLParser().feed(open(sys.argv[1]).read()); print('ok')" <html file>`.

How she uses the mock (tell her the short version):
- Open the HTML file in Chrome or Edge (on Windows: `\\wsl$\Ubuntu\home\madi\junction-pitch\04-pitch\deck\mock\`). Works offline.
- → / Space / click: next. ←: back. **C**: 3-min / 5-min / all + backup. **P**: presenter view (notes, next slide, timers). **N**: notes over the slide. **T**: start or pause the timer (the first "next" also starts it). **R**: reset. **F**: full screen. **B**: black screen. **?**: help.
- Timers turn yellow at 80 % of a slide's budget and red when over.

## 5. Reply in chat (short)

- Paths of the new outline and mock (and the version they replace).
- The 3-min total, and the slide list in one line.
- "Still needed": every `[[need: …]]` and every missing asset file, with who could get it (research → /market-scan or /fact-check; screenshot → teammate).
- Suggested next skills: /pitch (spoken script for the same cuts), /jury-drill (Q&A), /fact-check (numbers on slides), /video-idea (the demo video).

## Files in this skill
- [outline-format.md](outline-format.md): the outline format the generator reads, and a skeleton to copy.
- [finalist-patterns.md](finalist-patterns.md): how the 2025 finalists built their decks.
- [build_mock.py](build_mock.py): outline → HTML, with checks. `--next DECK_DIR` gives the next file name.
- [mock-template.html](mock-template.html): the slideshow page (CSS + JS). Change the look here, then rebuild.
- [slides-steps.md](slides-steps.md): `/deck slides`, `/deck export`, `/deck canva`, step by step, with the tool names and limits.
- [build_slides.py](build_slides.py): outline → .pptx for Google Slides (`build`), and the merge for re-runs that keeps human edits (`merge`). Needs python-pptx in `~/.cache/deck-venv`.
- [test_build_mock.py](test_build_mock.py): offline test of the 3-min timing checks (`python3 .claude/skills/deck/test_build_mock.py` → `ok`).
- [test_build_slides.py](test_build_slides.py): offline test of build + merge (`~/.cache/deck-venv/bin/python .claude/skills/deck/test_build_slides.py` → `ok`).

## Rules
- Real data only, plain English, files not chat (CLAUDE.md).
- Never edit core.md, sources.md or the playbooks. If the deck shows core.md is weak (no number, vague user), say so in the reply and suggest the core.md change.
- Never overwrite an older outline or mock; write the next version.
- Embedded videos are silent with burned-in captions. Every video slide has a GIF or screenshot fallback.

## Google Slides, export and Canva (`/deck slides`, `/deck export`, `/deck canva`)

If `$ARGUMENTS` starts with `slides`, `export` or `canva`, skip steps 1–5 and follow
[slides-steps.md](slides-steps.md). Short version:
- `/deck slides`: newest `04-pitch/deck/outline*.md` → .pptx (`build_slides.py`) → uploaded to Google Drive, which
  converts it to a Google Slides deck (16:9, speaker notes kept). The link and file ID go to `04-pitch/deck/slides-link.md`.
- On a re-run, the script exports the live deck, keeps every slide a teammate edited (it puts the new outline text in
  that slide's notes as "Proposed:"), and updates the other slides. **Limit:** only the Google Drive connector
  is available, and Drive cannot change the contents of an existing deck. So the updated deck is uploaded as a NEW
  Google Slides file (new link), and only after Madalina says yes. Editing the same deck needs the Google Slides
  connector (see slides-steps.md §5).
- `/deck export`: the current deck as PDF and .pptx in `04-pitch/deck/export/`.
- `/deck canva`: optional. Canva can make a concept image or a separate Canva presentation from the outline. It
  cannot edit the Google Slides deck.
- Never share, change permissions, move, trash or delete anything in Drive or Canva.

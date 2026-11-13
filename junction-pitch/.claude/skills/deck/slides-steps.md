# /deck slides · /deck export · /deck canva

Tested 2026-11-10 with the claude.ai connectors in Claude Code (TEST decks, practice outline).
Before any call that creates a Google file, load the `anthropic-skills:google-workspace` skill (Skill tool) and follow it.
Deferred tools: load them first with ToolSearch, e.g. `select:mcp__claude_ai_Google_Drive__create_file,...`.

## 0. What the connectors can do (checked 2026-11-10)

| Need | Tool | Works? |
|---|---|---|
| Create a Google Slides deck from a .pptx | Drive `mcp__claude_ai_Google_Drive__create_file` (pptx upload, Drive converts it) | Yes. 16:9, text and speaker notes survive. |
| Read the deck's text | Drive `read_file_content` | Yes, slide text only. **No speaker notes.** Slides are separated by `-----`. |
| Read the deck with notes and layout | Drive `download_file_content` with `exportMimeType` pptx | Yes. The result (about 115 KB for 16 slides) is saved to a file. |
| PDF | Drive `download_file_content` with `exportMimeType: application/pdf` | Yes (about 200 KB, saved to a file). |
| **Edit the existing deck in place** | needs the Google Slides connector (`update_presentation`, `read_presentation`) | **No. That connector is not available.** Drive `update_file` changes only the title and other metadata. |
| Images from `mock/assets/` | embedded in the .pptx by `build_slides.py` | Yes (png/jpg/gif, fitted to the box). Videos: no; insert them by hand. |
| Share, change permissions, move, trash | `share_file`, `update_file parentId`, `trash_file` | Do not use. Never. |

Canva tools (`mcp__claude_ai_Canva__*`): see §4.

## 1. One-time setup (each machine)

```bash
python3 -m venv ~/.cache/deck-venv && ~/.cache/deck-venv/bin/pip install python-pptx
~/.cache/deck-venv/bin/python .claude/skills/deck/test_build_slides.py     # prints: ok <tmp dir>
```

## 2. `/deck slides`: first time (no `04-pitch/deck/slides-link.md` yet)

1. Newest outline: `ls 04-pitch/deck/outline*.md`, take the highest version (`outline-v3.md` > `outline-v2.md` > `outline.md`).
2. Build:
   ```bash
   ~/.cache/deck-venv/bin/python .claude/skills/deck/build_slides.py build 04-pitch/deck/<outline> \
     --out 04-pitch/deck/slides/deck-v1.pptx
   sha256sum 04-pitch/deck/slides/deck-v1.pptx
   ```
   It writes `deck-v1.pptx` and `deck-v1.state.json`, the exact text on every slide. Keep the state file:
   the next re-run needs it to see what a person changed. Read the `WARN` lines, as for the mock.
3. Upload. Do not type base64. Use a file reference:
   `create_file(title="Hour49 deck: <Name>", contentMimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation", base64Content="sha256:<hex>:<absolute path>")`.
   The result is `mimeType: application/vnd.google-apps.presentation` with `id` and `viewUrl`.
4. Verify: `read_file_content(id)` shows one `-----` block per slide, with the same text as the outline.
   To check the layout, export a PDF (§3) and look at 2–3 pages (`pymupdf` in the venv:
   `~/.cache/deck-venv/bin/pip install pymupdf`, then render pages to PNG and Read them).
5. Write `04-pitch/deck/slides-link.md`:
   ```markdown
   # Google Slides deck
   - Title: Hour49 deck: <Name>
   - URL: <viewUrl>
   - File ID: <id>
   - Built from: 04-pitch/deck/<outline>
   - State file: 04-pitch/deck/slides/deck-v1.state.json
   - Created: <Helsinki time> · Updated: <Helsinki time>
   - Older decks (superseded, not deleted): none
   ```
   Not shared with anyone. Madalina shares it herself if she wants teammates to edit it.

Layout: white background, near-black Arial text, one red accent for the number and the badge. Small grey kicker
(the slide title) at the top left, the on-screen line large, the number huge, the source at 10 pt at the bottom, and the slide number at the bottom right.
`[[need: …]]` text is amber, so gaps show. Missing images show as a dashed box `insert: assets/<file>`.
Speaker notes: cut and seconds, the notes, `Extra for 5-min:`, the visual, and the media to insert by hand. Backup slides come last.

## 3. `/deck slides` again (slides-link.md exists): keep human edits

1. Export the live deck: `download_file_content(<File ID>, exportMimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation")`.
   The result is saved to a file. Decode it:
   `jq -r .content <saved file> | base64 -d > 04-pitch/deck/slides/live-<YYYYMMDD-HHMM>.pptx`
2. Dry run:
   ```bash
   ~/.cache/deck-venv/bin/python .claude/skills/deck/build_slides.py merge 04-pitch/deck/<newest outline> \
     --current 04-pitch/deck/slides/live-<…>.pptx --state <State file from slides-link.md> \
     --out 04-pitch/deck/slides/deck-v<N+1>.pptx --dry-run
   ```
   For each slide it says: `same`, `update` (outline changed and nobody touched the slide), `human` (a person
   changed or added text: the slide is kept as it is, and the new text goes into its notes as "Proposed:"),
   `new` (added at the end) or `extra` (in the deck but not in the outline: left alone). For notes, the rule is the
   same: edited notes are kept and get "Proposed notes" added.
3. **Ask Madalina before going on.** Drive cannot write into the existing deck. Tell her the plan and the two choices:
   - (a) Turn on a Google Slides connector (§5). Then the same deck and the same link are updated.
   - (b) Upload the merged deck as a NEW Google Slides file "Hour49 deck: <Name> v<N+1>". It gets a new link, so
     teammates must switch to it. The old deck stays (never trash it). Edits made in the old deck after the
     export in step 1 are not in the new one.
4. If she picks (b): run the merge without `--dry-run`, then upload as in §2 step 3 and verify as in step 4. Then update
   slides-link.md: new URL, ID, state file and Updated time. Move the old deck to "Older decks", with its link and ID.

## 4. `/deck export`

1. Deck ID from `04-pitch/deck/slides-link.md`.
2. `download_file_content(id, exportMimeType="application/pdf")` and `(…, exportMimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation")`.
   Each result is saved to a file. Decode each one into `04-pitch/deck/export/`:
   `jq -r .content <saved> | base64 -d > 04-pitch/deck/export/<kebab-title>-<YYYYMMDD-HHMM>.pdf` (and `.pptx`).
3. Check: `file <out>` says PDF / Microsoft OOXML. For the pptx, `~/.cache/deck-venv/bin/python -c "from pptx import Presentation as P; import sys; p=P(sys.argv[1]); print(len(p.slides))" <out>`.
4. Videos are not in the pptx. Re-insert each MP4 in PowerPoint (Insert → Video → This Device, Start: Automatically)
   and test it on a second machine with Wi-Fi off (pitching.md §5.1). For a 3-min copy, skip the `Cut: 5-min` slides there.

## 5. In-place editing later (the Google Slides connector)

If `update_presentation` and `read_presentation` appear in ToolSearch, use them to edit the same deck. Same rules as §3:
compare the live text with the state file. For `update` slides, use `replaceAllText` limited to that slide's
`pageObjectIds`, old box text → new text. For `human` slides, insert "Proposed: …" into the notes shape
(`slideProperties.notesPage`, `speakerNotesObjectId`). Guard every batch with `writeControl.requiredRevisionId`
(google-workspace skill, `references/slides.md`). This path is UNTESTED. Test it on a TEST deck first, then update this file.

## 6. `/deck canva` (optional)

Checked 2026-11-10: the Canva connector answers (`search-designs` returned designs). Nothing was generated during
the test, because each generation can use Canva AI credits. Run a generation only when Madalina asks for it.

What can help the deck:
- **A concept image for a slide** (hook photo, background): `mcp__claude_ai_Canva__generate-image` (prompt, `aspectRatio: "LANDSCAPE_16_9"`)
  → `get-generate-image-job` until SUCCESS → it returns the image and an "Open generated image" Canva link.
  It is AI art, so the slide gets `Badge: Vision`, never "Built this weekend", and it never stands in for a real user or real footage.
  To use it in Slides, download it from Canva into `04-pitch/deck/mock/assets/<name>.png` (by hand if the tool gives
  no direct file URL; UNTESTED). Then set `Image:` in the outline and rebuild.
- **A designed alternative deck in Canva**: `create-design` with `outline.sections` (title + description per slide)
  → `get-create-design-async-job` → a Canva presentation. Then `get-export-formats` + `export-design` (`pdf` or `pptx`)
  give a download URL; save the file to `04-pitch/deck/export/`. This is a separate design: it does not update the
  Google Slides deck, and teammates' edits do not sync between the two. It is UNTESTED whether speaker notes come across.
  Use it only for look ideas. The Google Slides deck stays the deck we present.

What Canva cannot do here:
- Edit or restyle the Google Slides deck.
- Import our deck: `import-design-from-url` needs a public URL, and we never make the deck public.
- Use the Hour49 brand kit: `create-design` cannot apply one. The legacy `request-outline-review` → `generate-design-structured`
  path can, but it needs an approval click in a claude.ai widget, so it does not work from Claude Code (UNTESTED).
- Do not use `merge-designs` (it can delete pages), `move-item-to-folder`, or the comment and brand-template tools.

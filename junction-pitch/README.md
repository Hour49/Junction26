# Junction 2026 pitch kit: team Hour49

Start here. This folder holds everything for the business, research and pitch side of Junction 2026 (Espoo, Fri 13 – Sun 15 Nov 2026). It is not a git repo. The code lives elsewhere.

Last updated: 2026-11-10.

**Quick manual of all 12 skills and how to type them: [MANUAL.md](MANUAL.md).**

## Your toolkit (slash commands) — open Claude Code in this folder: `cd ~/junction-pitch && claude`

Every skill reads `04-pitch/core.md` (the current idea) and writes files; nothing is ever overwritten (`-v2`, `-v3`).

| When | Command | What you get |
|---|---|---|
| Fri 18:00, after the challenge videos | `/challenge-pick <names or pasted briefs>` | more than 3 challenges: a triage run → shortlist, reply "go"; then 5 agents on the top 3 → `03-research/challenges/ranking.md` + questions for partner reps |
| Fri, idea chosen | fill `04-pitch/core.md`, then `/market-scan` (or `--quick`) | competitors, similar ideas, user, market size, problem size → `03-research/market-scan-summary.md` |
| Fri | `/pain-points` | 5 agents find real people with this problem → quotes + validation verdict |
| Fri night | `/deck`, `/easy-pitch`, `/pitch stage` | slide outline + HTML slideshow mock-up; peer hooks + 2-min table demo; timed stage script |
| Walking around | `/pro-pitch partner <name>` · `/pro-pitch technical` · `/pro-pitch business` | 60–90 s pitch + 5 questions to ask them |
| After every talk | `/feedback <messy notes>` · `/feedback summary` | logged entry, next actions, quick background research |
| Sat | `/jury-drill` (practice only if you ask: `live otto`, `rapid`) | your idea judged + the likely stage questions, ranked |
| Before showing anything | `/fact-check` (or `--quick`) | every number checked → `04-pitch/fact-check-report.md` |
| Sat/Sun | `/pitch rehearse stage-3min` · `/team-intro` · `/video-idea` | cue cards; team intro (mock); video concepts |

Loop: talk to people → `/feedback` → research skill it suggests → update `core.md` → re-run `/deck`, `/pitch`, `/easy-pitch` → `/fact-check`.
Held items and later work: [TODO.md](TODO.md). Project rules for agents: [CLAUDE.md](CLAUDE.md).

## Reading order

1. [00-event/junction-info.md](00-event/junction-info.md) §0 "Quick facts" and §0.2 to-do: dates, deadlines, judging, rules (stage pitch exactly 3 min + 3 min Q&A).
2. [01-playbooks/pitching.md](01-playbooks/pitching.md) §0 "Ten things to know": how the pitch is judged and what won.
3. [02-reference/pitch-analysis.md](02-reference/pitch-analysis.md): what the 2025 winners did on stage, then [02-reference/junction-videos.md](02-reference/junction-videos.md) "Watch first (top 10)" to see it.
4. [01-playbooks/market-research.md](01-playbooks/market-research.md) §0 and §8: research rules and the one-page checklist.
5. During the weekend, work in `03-research/` and `04-pitch/`, following each folder's README.

## Folders

| Folder | Purpose | Status |
|---|---|---|
| `00-event/` | Facts about the event: logistics, rules, judging, partners, past challenges and winners | Done (re-check UNVERIFIED items on Friday) |
| `01-playbooks/` | How-to guides: research method, pitching method, Claude Code tooling | Done |
| `02-reference/` | Evidence from past editions: video catalogue, channel index, pitch transcripts, pitch analysis and its data | Done |
| `03-research/` | Our weekend research output, by topic | Empty, with READMEs and a file template |
| `04-pitch/` | Our scripts, deck, video and submission text | Empty, with READMEs |
| `05-team/` | Team Hour49: people, roles, track record, prep tooling | Done |

## Files

| File | What it is |
|---|---|
| [00-event/junction-info.md](00-event/junction-info.md) | Info pack: §0 quick facts and to-do, §1 event facts and logistics, §2 challenges, partners and past winners (2C past editions, 2D patterns, 2E tips for an AI-agent team). §3 moved to `05-team/` |
| [01-playbooks/pitching.md](01-playbooks/pitching.md) | Pitching playbook: every format (30 s to stage pitch, video, written submission), deck, what won at Junction, rehearsal, demo backups, Q&A, tooling |
| [01-playbooks/market-research.md](01-playbooks/market-research.md) | Hackathon-speed research playbook: competitors, users, market and problem size, one-liners, what juries reward, a weekend schedule, checklist |
| [01-playbooks/claude-tooling.md](01-playbooks/claude-tooling.md) | Claude Code reference for a no-coding research and pitch workflow: skills, subagents, CLAUDE.md, settings, permissions, output styles |
| [02-reference/junction-videos.md](02-reference/junction-videos.md) | Curated catalogue of 88 verified Junction videos by year, with placement, type and why to watch; top-10 list and gaps |
| [02-reference/junction-channel-index.md](02-reference/junction-channel-index.md) | Raw index of all 136 items on the official Junction YouTube channel |
| [02-reference/pitch-analysis.md](02-reference/pitch-analysis.md) | **What winning pitches do**: common traits, the 7-step structure, jury questions, how the product was shown, presentation lessons (from 9 pitch videos) |
| [02-reference/pitch-breakdown.csv](02-reference/pitch-breakdown.csv) | One row per analysed pitch (9): placement, timings, opening, numbers, demo mode, slide style, failures |
| [02-reference/jury-questions.csv](02-reference/jury-questions.csv) | All 17 jury questions from the 2025 top 5, categorised, with answer summaries |
| [02-reference/pitch-frames/](02-reference/pitch-frames/) | One contact sheet per 2025 video (7): timestamped frames of what was on screen |
| [02-reference/raw-data/](02-reference/raw-data/) | Unprocessed inputs: video metadata (JSONL), raw YouTube search hits (TSV), original caption files (VTT). See its README |
| [02-reference/pitch-transcripts/](02-reference/pitch-transcripts/) | Auto-caption transcripts of 9 winning or finalist pitches: the five 2025 top-5 stage pitches, the 2025 winners' 2-minute submission videos, two 2026 Defence Hackathon pitches |
| [03-research/README.md](03-research/README.md) | Rules (sources required; numbers labelled measured/reported/assumed), `sources.md` format, file template |
| `03-research/{challenges,competitors,users,market}/README.md` | What goes in each research subfolder |
| [04-pitch/README.md](04-pitch/README.md) | Pitch folder guide; `core.md` is the single source for the message |
| `04-pitch/{scripts,deck,video,submission}/README.md` | What goes in each pitch subfolder, with the matching playbook section |
| [05-team/hour49.md](05-team/hour49.md) | Team and roles, track record, prep repo and agent workflow, board CLI, team website, decisions and open tasks |

Transcript files in `02-reference/pitch-transcripts/`:

| File | Pitch |
|---|---|
| `2025-wavelet-stage-pitch.md` | Wavelet, 1st overall 2025, stage pitch + Q&A |
| `2025-loredash-stage-pitch.md` | LoreDash, 2nd overall 2025 (solo), stage pitch + Q&A |
| `2025-dronestalker-stage-pitch.md` | Drone stalker, top 5 2025 |
| `2025-walkthrough-stage-pitch.md` | Walkthrough, top 5 2025 (Wolt) |
| `2025-lambda-pump-stage-pitch.md` | λpump, top 5 2025 (HSY & Valmet) |
| `2025-wavelet-submission-video.md` | Wavelet's 2-minute submission video |
| `2025-loredash-submission-video.md` | LoreDash's 2-minute submission video |
| `2026-defence-17tech-winner-pitch.md` | Junction x Aalto Defence Hackathon 2026, main prize winner (side event) |
| `2026-defence-are-ya-winning-son-pitch.md` | Same event, finalist (side event) |

## Conventions

- **File names:** kebab-case, lower case. Folders are numbered in reading and workflow order.
- **Paths:** paths in backticks are relative to this folder (`/home/madi/junction-pitch`), e.g. `03-research/sources.md`. Markdown links are relative to the file they are in.
- **Sources and labels:** every claim has a source. Tags used across the files: **[2026]** confirmed this year; **[2025]/[2024]** earlier editions; **UNVERIFIED** single-source or inferred; numbers are **measured/reported/assumed**.
- **Times:** Europe/Helsinki (UTC+2).
- **Section references** such as "junction-info §2C" mean the numbered heading in that file.
- **Move, don't copy:** each fact lives in one file; other files link to it.
- **No secrets and no partner raw data** in this folder.

## Known loose ends

- `01-playbooks/claude-tooling.md` (§4 example CLAUDE.md and "Quick file map") proposes a different layout (`research/`, `drafts/`, `sources/`, `.claude/`). It was written before this reorganisation and left unchanged. Reconcile it with the numbered folders when the Claude Code toolkit for this folder is built.
- The "Junction Challenge Archive" artifact could not be read (junction-info §0.1).
